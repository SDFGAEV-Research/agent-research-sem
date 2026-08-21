# Managed server connections

This is the non-secret inventory and operating contract for managed servers.
The actual host address, SSH key path and any interactive password stay in the
process environment or the local SSH agent; they are not recorded in this
repository.

## `sem-ubuntu`

| Field | Value |
|---|---|
| Logical server ID | `sem-ubuntu` |
| OS | Ubuntu 22.04.5 LTS |
| Kernel | Linux 6.8.0-136-generic |
| CPU | 256 logical CPUs |
| RAM | 503 GiB |
| Root storage | 917 GB total, about 843 GB available at last inventory |
| Data storage | 102 TB total, about 92 TB available at last inventory |
| Remote SSH port | `60320` |
| Remote user | `ubuntu` |
| Research platform root | `/data/research-platform/agent-research-platform-system` |
| Active release link | `current` under the research platform root |
| Persistent operator shell | remote tmux session `research-platform-shell` |

The inventory was verified by the repository server-health route and a
read-only remote inventory on 2026-08-21. At that time the host had Python
3.10.12, Git 2.34.1, tmux 3.0a, Node.js 12.22.9 and no Java executable in
`PATH`. The current project requires Python >=3.11, the MC bridge requires
Node >=22, and the server requires Java >=21; these are deployment blockers,
not reasons to weaken the project requirements.

## Environment binding

Use the example profile at
`configs/server_profiles/sem-ubuntu.example.env` as the variable contract:

```text
RP_SERVER_SEM_UBUNTU_HOST
RP_SERVER_SEM_UBUNTU_PORT
RP_SERVER_SEM_UBUNTU_USER
RP_SERVER_SEM_UBUNTU_KEY_PATH       # recommended for unattended runs
RP_SERVER_SEM_UBUNTU_KNOWN_HOSTS    # optional
RP_SERVER_SEM_UBUNTU_SSH_CONFIG     # optional
RP_SERVER_SEM_UBUNTU_SSH            # optional
RP_SERVER_SEM_UBUNTU_SCP            # optional
```

The connection identity is composed by
`research_platform/runtime/server/identity`; projects must not construct
SSH/scp arguments or keep a second server registry.

## Persistent operator connection

The operator helper is:

```bash
python scripts/server_session.py ensure sem-ubuntu --interactive
python scripts/server_session.py status sem-ubuntu --interactive
python scripts/server_session.py attach sem-ubuntu
```

`ensure` creates the named remote tmux shell if it does not exist. The shell
survives an SSH disconnect; `attach` reconnects to the same remote tmux
session. This is only a persistent operator shell. It is not evidence that a
model, Minecraft server or scientific run is healthy. Those continue to use
the exact server/model/runtime health authorities.

For unattended use, configure an SSH key or agent and omit `--interactive`.
The local Windows OpenSSH permission issue has been repaired by removing the
stale `UNKNOWN` SID from `C:\\Users\\25676\\.ssh\\config` while preserving
the owner, current-user, SYSTEM and Administrators access. The normal profile
therefore leaves `RP_SERVER_SEM_UBUNTU_SSH_CONFIG` unset. If another machine
has the same permission problem, set that variable to the absolute path of the
tracked empty template `configs/server_profiles/empty.ssh_config` (or another
explicitly readable empty file). Do not use the Windows device name `NUL`:
OpenSSH treats it as an invalid configuration source on this route.
