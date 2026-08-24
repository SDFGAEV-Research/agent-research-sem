from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from research_platform.platform.kernel import canonical_digest


class ConversationState(StrEnum):
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    ACTIVE = "active"
    WAITING = "waiting"


class ConversationKind(StrEnum):
    CHAT = "chat"
    TASK = "task"
    INTERRUPT = "interrupt"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    message_id: str
    peer_id: str
    sender_id: str
    text: str
    turn: int
    metadata: Mapping[str, str] = field(default_factory=dict)
    priority: int = 0
    generation: int = 0
    kind: ConversationKind = ConversationKind.CHAT

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.message_id, self.peer_id, self.sender_id, self.text)):
            raise ValueError("conversation message identity and text are required")
        if self.turn < 0:
            raise ValueError("conversation turn cannot be negative")
        if self.priority < 0 or self.generation < 0:
            raise ValueError("conversation priority/generation cannot be negative")


@dataclass(frozen=True, slots=True)
class ConversationSession:
    peer_id: str
    state: ConversationState = ConversationState.IDLE
    messages: tuple[ConversationMessage, ...] = ()
    next_turn: int = 0
    last_error: str = ""
    pending: tuple[ConversationMessage, ...] = ()

    @property
    def digest(self) -> str:
        return canonical_digest({
            "peer_id": self.peer_id,
            "state": self.state.value,
            "messages": [{"message_id": message.message_id, "sender_id": message.sender_id, "text": message.text, "turn": message.turn, "priority": message.priority, "generation": message.generation, "kind": message.kind.value} for message in self.messages],
            "pending": [message.message_id for message in self.pending],
        })


class AgentConversationManager:
    """One active peer conversation with deterministic per-peer queues."""

    def __init__(self, *, agent_id: str, max_messages: int = 64) -> None:
        if not agent_id.strip() or max_messages < 1:
            raise ValueError("conversation manager identity/limits are invalid")
        self.agent_id = agent_id
        self._max_messages = max_messages
        self._sessions: dict[str, ConversationSession] = {}
        self._active_peer: str | None = None

    def connect(self, peer_id: str) -> ConversationSession:
        if not peer_id.strip():
            raise ValueError("peer id is required")
        session = self._sessions.get(peer_id, ConversationSession(peer_id))
        session = ConversationSession(peer_id, ConversationState.IDLE, session.messages, session.next_turn, "")
        self._sessions[peer_id] = session
        return session

    def disconnect(self, peer_id: str, reason: str = "disconnected") -> ConversationSession:
        session = self._sessions.get(peer_id, ConversationSession(peer_id))
        session = ConversationSession(peer_id, ConversationState.DISCONNECTED, session.messages, session.next_turn, reason, session.pending)
        self._sessions[peer_id] = session
        if self._active_peer == peer_id:
            self._active_peer = None
        return session

    def receive(self, peer_id: str, text: str, *, sender_id: str | None = None, metadata: Mapping[str, str] | None = None, priority: int = 0, generation: int = 0, kind: ConversationKind = ConversationKind.CHAT) -> ConversationMessage:
        session = self._sessions.get(peer_id)
        if session is None or session.state is ConversationState.DISCONNECTED:
            self.connect(peer_id)
            session = self._sessions[peer_id]
        message = ConversationMessage(
            message_id=f"conversation:{peer_id}:{session.next_turn}", peer_id=peer_id,
            sender_id=sender_id or peer_id, text=text.strip(), turn=session.next_turn,
            metadata=dict(metadata or {}), priority=priority, generation=generation, kind=kind,
        )
        if not message.text:
            raise ValueError("conversation text cannot be empty")
        messages = (session.messages + (message,))[-self._max_messages :]
        pending = tuple(sorted((*session.pending, message), key=lambda item: (-item.priority, item.turn)))
        self._sessions[peer_id] = ConversationSession(peer_id, ConversationState.WAITING, messages, session.next_turn + 1, "", pending)
        return message

    def begin(self, peer_id: str) -> ConversationSession:
        session = self._sessions.get(peer_id)
        if session is None or session.state is ConversationState.DISCONNECTED:
            raise ValueError("peer is not connected")
        if self._active_peer not in (None, peer_id):
            raise RuntimeError("another conversation is active")
        self._active_peer = peer_id
        updated = ConversationSession(peer_id, ConversationState.ACTIVE, session.messages, session.next_turn, session.last_error, ())
        self._sessions[peer_id] = updated
        return updated

    def drain(self, peer_id: str, *, limit: int = 8) -> tuple[ConversationMessage, ...]:
        """Return the highest-priority queued messages for a bounded prompt."""
        if limit < 1:
            raise ValueError("conversation drain limit must be positive")
        session = self._sessions.get(peer_id)
        if session is None:
            return ()
        return session.pending[:limit]

    def resume(self, peer_id: str) -> ConversationSession:
        """Reconnect a peer without losing its queued messages or history."""
        session = self._sessions.get(peer_id)
        if session is None:
            return self.connect(peer_id)
        self._sessions[peer_id] = ConversationSession(peer_id, ConversationState.WAITING if session.pending else ConversationState.IDLE, session.messages, session.next_turn, "", session.pending)
        return self._sessions[peer_id]

    def respond(self, peer_id: str, text: str, *, metadata: Mapping[str, str] | None = None) -> ConversationMessage:
        session = self._sessions.get(peer_id)
        if session is None or session.state is not ConversationState.ACTIVE:
            raise RuntimeError("conversation is not active")
        message = ConversationMessage(
            message_id=f"conversation:{peer_id}:{session.next_turn}", peer_id=peer_id,
            sender_id=self.agent_id, text=text.strip(), turn=session.next_turn,
            metadata=dict(metadata or {}), priority=10, generation=session.next_turn, kind=ConversationKind.TASK,
        )
        if not message.text:
            raise ValueError("conversation response cannot be empty")
        messages = (session.messages + (message,))[-self._max_messages :]
        self._sessions[peer_id] = ConversationSession(peer_id, ConversationState.IDLE, messages, session.next_turn + 1)
        self._active_peer = None
        return message

    def session(self, peer_id: str) -> ConversationSession | None:
        return self._sessions.get(peer_id)

    def snapshot(self) -> tuple[ConversationSession, ...]:
        return tuple(self._sessions.values())


__all__ = ["AgentConversationManager", "ConversationKind", "ConversationMessage", "ConversationSession", "ConversationState"]
