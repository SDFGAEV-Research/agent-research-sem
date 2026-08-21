# Round 114 - server file transfer and immutable release publication

## Root cause

The platform had environment-backed SSH command identity but no independent
file-transfer seam or release publication owner. A future deployment caller
would otherwise need to construct scp arguments, remote paths, upload ordering
and release extraction itself, recreating server authority in the caller.

## Structural change

`runtime/server/identity` now exposes two narrow public ports:

- `ServerConnectionPort` for remote command execution;
- `ServerFileTransferPort` for local-file to remote-file transfer.

The OpenSSH provider implements the second port with scp, requires a regular
local file and an absolute POSIX remote path, and never accepts credentials in
the profile or command arguments. The capability composition plan records the
file-transfer factory separately from the command factory.

Both environment factories now call one provider-local profile materializer;
host, port, user, key, known-hosts and SSH-config parsing therefore have one
authority while SSH and scp remain separate adapters.

The optional executable override is `RP_SERVER_<ID>_SCP`; the repository keeps
no server address, credential or executable value in source control.

`runtime/server/lifecycle` owns `SSHServerReleasePublisher`. It receives both
ports and publishes one release package through:

```text
prepare exact incoming/staging/release paths
  -> upload digest-named archive
  -> verify remote SHA-256
  -> reject ZIP path traversal
  -> require release manifest and evidence
  -> write marker and atomically rename staging directory
```

Existing matching marker reuse is the only idempotent path. Existing conflicting
or stale paths fail; the publisher does not delete old releases or substitute a
different package.

## Verification

- 13 server/transfer/release/path tests passed;
- 25 MC/model/production-root tests passed;
- changed modules compiled successfully;
- architecture gate passed;
- no remote host, server, model or Minecraft process was started.
