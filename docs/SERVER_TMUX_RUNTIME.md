# Server tmux runtime policy

The production server uses **tmux for terminal/controller persistence**, not as a replacement for the platform's runtime authorities.

## Authority split

```text
tmux session
  └─ keeps the outer exact RuntimeManager command alive across SSH disconnects

RuntimeManager
  └─ owns exact verification / reconciliation / start ordering

Service OS
  └─ owns exact PID + process-start identity + readiness + stop semantics

Checkpoint / effect journals
  └─ own scientific and external-effect recovery truth

Forensics
  └─ owns durable causal evidence
```

A tmux session existing does **not** mean a model service or Study is healthy. `tmux has-session` must never replace exact process reconciliation or runtime status.

## Immutable code updates

Active runs execute from content-addressed release directories:

```text
SERVER_ROOT/
  releases/
    <release_sha256>/
      ... frozen code ...
```

Do not edit the code inside an active release directory. A code change must produce:

```text
new source tree
→ new release digest
→ new release directory
→ new FrozenRuntimeManifest
→ new tmux session binding
```

The tmux session name includes the runtime manifest digest. The durable session binding also freezes the full controller argv/cwd and tmux transport identity. Reusing the same session name with different code/command/transport is a hard drift error.

## Recommended server entry

The transport helper is intentionally thin:

```bash
python scripts/tmux_runtime_session.py ensure \
  --release-root /srv/research-platform \
  --release-digest <RELEASE_SHA256> \
  --runtime-manifest-digest <RUNTIME_MANIFEST_SHA256> \
  --control-id paper1-prod \
  --binding-root /srv/research-platform/runtime/tmux-bindings \
  --home "$HOME" \
  --tmpdir /tmp \
  -- /usr/bin/python3 -m <exact-runtime-entry>
```

The command inside tmux must still invoke the exact RuntimeManager composition. The helper does not select models, change precision/context, modify method/environment identity, or perform recovery itself.

To inspect the tmux transport:

```bash
python scripts/tmux_runtime_session.py status \
  --binding-root /srv/research-platform/runtime/tmux-bindings \
  --home "$HOME" \
  --tmpdir /tmp \
  <SESSION_NAME>
```

Use the returned `attach_argv` to attach. Runtime/service health should be checked with the normal operator/runtime status commands, not inferred from tmux.
