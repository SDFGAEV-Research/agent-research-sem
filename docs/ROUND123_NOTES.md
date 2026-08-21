# Round 123 — model asset acquisition boundary repair

## Root cause

The server's Hugging Face CLI rejects a download command that combines
`--local-dir` and `--cache-dir`. The platform model source provider always
emitted both options, so a managed model fetch failed before contacting the
model repository.

## Structural repair

The provider continues to materialize the model into the platform-selected
storage pool and keeps resumable local-directory acquisition. Its explicit
cache root is now passed through `HF_HOME`, which is the CLI-supported cache
boundary, instead of emitting the incompatible `--cache-dir` option. The
provider test now asserts both the absence of the conflicting option and the
resolved cache environment.

The server management configuration was also corrected to use the absolute
`hf` executable from the verified `qwen36-sglang` environment. No model was
registered or downloaded by the failed attempts, and no fallback downloader
was introduced.

## Verification status

The code change is committed separately from unrelated recovery-lease work.
Server-only regression remains required because the local Windows interpreter
does not satisfy the project's Python version contract. After the updated
release is staged on the server, the focused asset-management test and a
platform-managed model fetch will be rerun; only a successful fixed-revision
asset receipt will unlock model deployment.

The first server rerun also caught and corrected a test-fixture path mistake:
the cache path belongs to the nested directory layout value. The production
provider was not implicated; the corrected server rerun is the authoritative
regression check.

A subsequent full traceback exposed one remaining production line that still
appended `--cache-dir`; that line has now been removed. The provider's
`HF_HOME` path is therefore the sole cache injection mechanism.
