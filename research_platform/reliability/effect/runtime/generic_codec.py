from __future__ import annotations

import base64
import json

from research_platform.reliability.effect.api import PreparedEffectHandle
from research_platform.platform.kernel import EffectCertainty, EffectClass, EffectReceipt, canonical_digest

from research_platform.reliability.effect.api import EffectCompletionEvidence, EffectIntent, EffectIntentPhase, EffectIntentRecord
from .persistence import EncodedEffectIntentRecord


class EffectJournalDocumentCodec:
    """Provider-agnostic durable document codec for generic effect intents."""

    DOCUMENT_SCHEMA = "effect-intent.v1"

    @staticmethod
    def _handle_payload(handle: PreparedEffectHandle | None) -> dict[str, object] | None:
        if handle is None:
            return None
        return {
            "request_id": handle.request_id,
            "request_digest": handle.request_digest,
            "provider_schema": handle.provider_schema,
            "opaque_payload_b64": base64.b64encode(handle.opaque_payload).decode("ascii"),
            "payload_sha256": handle.payload_sha256,
            "provider_instance_id": handle.provider_instance_id,
        }

    @staticmethod
    def _decode_handle(row: object) -> PreparedEffectHandle | None:
        if row is None:
            return None
        if not isinstance(row, dict):
            raise ValueError("invalid prepared effect handle document")
        return PreparedEffectHandle(
            str(row["request_id"]),
            str(row["request_digest"]),
            str(row["provider_schema"]),
            base64.b64decode(str(row["opaque_payload_b64"]).encode("ascii")),
            str(row["payload_sha256"]),
            None if row.get("provider_instance_id") is None else str(row["provider_instance_id"]),
        )

    def encode_intent(self, intent: EffectIntent) -> tuple[str, str]:
        payload = {
            "document_schema": self.DOCUMENT_SCHEMA,
            "intent_id": intent.intent_id,
            "request_id": intent.request_id,
            "operation_id": intent.operation_id,
            "request_digest": intent.request_digest,
            "provider_component_digest": intent.provider_component_digest,
            "run_id": intent.run_id,
            "trace_id": intent.trace_id,
            "study_id": intent.study_id,
            "lifetime_id": intent.lifetime_id,
            "task_id": intent.task_id,
            "decision_cycle_id": intent.decision_cycle_id,
            "checkpoint_id": intent.checkpoint_id,
            "source_generation": intent.source_generation,
            "recovery_handle": self._handle_payload(intent.recovery_handle),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")), canonical_digest(payload)

    def decode_intent(self, text: str) -> EffectIntent:
        row = json.loads(text)
        if row.get("document_schema") != self.DOCUMENT_SCHEMA:
            raise ValueError(f"unsupported effect intent document schema: {row.get('document_schema')}")
        return EffectIntent(
            row["intent_id"], row["request_id"], row["operation_id"], row["request_digest"],
            row["provider_component_digest"], row["run_id"], row["trace_id"], row.get("study_id"),
            row.get("lifetime_id"), row.get("task_id"), row.get("decision_cycle_id"),
            row.get("checkpoint_id"), row.get("source_generation"), self._decode_handle(row.get("recovery_handle")),
        )

    @staticmethod
    def encode_effect(effect: EffectReceipt | None) -> str | None:
        if effect is None:
            return None
        payload = {
            "effect_id": effect.effect_id,
            "request_digest": effect.request_digest,
            "effect_class": effect.effect_class.value,
            "certainty": effect.certainty.value,
            "provider_instance_id": effect.provider_instance_id,
            "verification_required": effect.verification_required,
            "before_artifact": effect.before_artifact,
            "after_artifact": effect.after_artifact,
            "provider_receipt": effect.provider_receipt,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def decode_effect(text: str | None) -> EffectReceipt | None:
        if text is None:
            return None
        row = json.loads(text)
        return EffectReceipt(
            row["effect_id"], row["request_digest"], EffectClass(row["effect_class"]),
            EffectCertainty(row["certainty"]), row.get("provider_instance_id"),
            bool(row.get("verification_required", False)), row.get("before_artifact"),
            row.get("after_artifact"), row.get("provider_receipt"),
        )

    @staticmethod
    def completion_digest(consumption: EffectCompletionEvidence | None) -> str | None:
        if consumption is None:
            return None
        return canonical_digest({
            "completion_key": consumption.completion_key,
            "completion_operation_id": consumption.completion_operation_id,
            "consumer_component_digest": consumption.consumer_component_digest,
            "consumer_generation": consumption.consumer_generation,
        })

    @staticmethod
    def encode_consumption(consumption: EffectCompletionEvidence | None) -> tuple[str | None, str | None]:
        if consumption is None:
            return None, None
        payload = {
            "completion_key": consumption.completion_key,
            "completion_operation_id": consumption.completion_operation_id,
            "consumer_component_digest": consumption.consumer_component_digest,
            "consumer_generation": consumption.consumer_generation,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")), EffectJournalDocumentCodec.completion_digest(consumption)

    @staticmethod
    def decode_consumption(text: str | None, expected_digest: str | None) -> EffectCompletionEvidence | None:
        if text is None:
            if expected_digest is not None:
                raise ValueError("effect completion digest exists without payload")
            return None
        row = json.loads(text)
        payload = {
            "completion_key": row["completion_key"],
            "completion_operation_id": row["completion_operation_id"],
            "consumer_component_digest": row["consumer_component_digest"],
            "consumer_generation": row.get("consumer_generation"),
        }
        if canonical_digest(payload) != expected_digest:
            raise ValueError("effect completion document checksum mismatch")
        return EffectCompletionEvidence(**payload)

    def encode_record(self, record: EffectIntentRecord) -> EncodedEffectIntentRecord:
        intent_json, intent_digest = self.encode_intent(record.intent)
        consumption_json, completion_digest = self.encode_consumption(record.consumption)
        if record.consumption_digest is not None and record.consumption_digest != completion_digest:
            raise ValueError(f"effect completion digest mismatch: {record.intent.intent_id}")
        return EncodedEffectIntentRecord(
            record.intent.intent_id, intent_json, intent_digest, record.intent.request_digest,
            record.intent.run_id, record.intent.lifetime_id, record.phase.value,
            self.encode_effect(record.effect), record.effect_digest,
            consumption_json, completion_digest,
        )

    def decode_record(self, encoded: EncodedEffectIntentRecord) -> EffectIntentRecord:
        raw = json.loads(encoded.intent_json)
        if canonical_digest(raw) != encoded.intent_digest:
            raise ValueError(f"effect intent document checksum mismatch: {encoded.intent_id}")
        return EffectIntentRecord(
            self.decode_intent(encoded.intent_json), EffectIntentPhase(encoded.phase),
            self.decode_effect(encoded.effect_json), encoded.effect_digest,
            self.decode_consumption(encoded.consumption_json, encoded.consumption_digest),
            encoded.consumption_digest,
        )


__all__ = ["EffectJournalDocumentCodec"]
