# Round 46 — Environment identity closure and safe deployment inspection

Date: 2026-08-23

## Current platform state

The model-deployment infrastructure now has a complete read-only qualification
path for one concrete host, model artifact and target Python interpreter:

```text
host facts
  -> OS / distribution / kernel / libc / limits / container facts
  -> NVIDIA driver / CUDA API / toolkit / NVRTC / NVML facts
  -> GPU identity / memory / compute capability / PCI-NUMA / power facts
  -> multi-GPU topology / NCCL facts
  -> model config / shards / size / storage and permission facts
  -> target-Python ABI / pip / venv / Torch-CUDA / kernel facts
  -> binary-wheel and PEP 658 metadata observation
  -> fixed-point dependency closure and constraint reconciliation
  -> exact backend and transitive package plan
```

The qualification plan is immutable and content-addressed. It records the
selected backend, exact package versions, source indexes, dependency closure,
and explicit rejection evidence. It does not install packages or start a
serving process. A separate application receipt performs frozen-plan
materialization with `--no-deps --only-binary=:all:` and a separate runtime
qualification checks imports, CUDA extensions, device visibility,
tensor-parallel width, model configuration and endpoint readiness.

The latest full Ubuntu host qualification remains:

- vLLM `0.27.1` accepted with 162 closure nodes and 161 transitive packages;
- SGLang rejected with explicit `cuda-tile==1.6.0rc5`, metadata and SM86
  coverage evidence;
- facts digest:
  `23a10803981db312760d617e5e0bd88650457464eec90e8a7432b38e008d6e2c`;
- plan digest:
  `504f51ea3a48f87b8d05cb03c6b55fe3d7c623003ef2da0ea19a2938c4d56c57`;
- record digest:
  `ea8a9403996d56a21bb35781f544b3fa3343bead81aebab354cef14eefb84de6`.

The real Qwen serving environment is still unmutated. These records are
compatibility and installation-plan evidence, not a serving or scientific
result.

## Environment registry repair

The first platform-managed environment inventory failed closed because two
legacy records lacked the immutable `specification_digest` required by the
current environment identity contract:

- `qwen36-sglang-main`;
- `qwen36-sglang-v517-cu130`.

The root cause was metadata-schema drift from the pre-identity registry, not a
missing Python environment. The actual interpreters were independently checked
as Python 3.11.15. The platform's explicit `env migrate-legacy` operation then
rewrote only those two registry records, preserving their paths, ownership and
packages. Their new digests are:

- `qwen36-sglang-main`:
  `5f1e3fa17dff2c2ab0e6392d8474e1ad313d36bda34c517b029dce65e29385ce`;
- `qwen36-sglang-v517-cu130`:
  `c9a15ccf827bb348569d8da26aef82305796d9a086a845c8a82d6f138f85392c`.

The existing `qwen36-sglang` and `sem-paper` records already contained valid
digests. A subsequent platform `env list` returned all four records as
`ready`, with no package installation, environment replacement or service
effect.

## Operational root cause and permanent rule

One diagnostic attempt searched the whole `/data/research-platform` tree for a
legacy environment ID. That traversed model and cache directories and held the
local SSH wrapper open. Independent inspection confirmed that no remote model
or service process was affected; the local orphaned wrapper was terminated and
the operation ledger was reconciled as `effect_not_applied`.

Future environment audits must use the platform-owned
`state/python-environments` directory only, enumerate bounded JSON records,
and use an explicit operation timeout. Model pools, caches, releases and logs
are never text-scanned by an environment inventory command. If a diagnostic
transport is interrupted, the operation must be reconciled before another
mutation is admitted.

## Verification boundary

This round verifies the registry identity repair and the qualification-system
control path. It does not claim:

- that vLLM has been installed in a new environment;
- that either serving backend has passed import or endpoint readiness;
- that the Qwen model has served a request;
- that the SEM/Minecraft scientific experiment has run.

The next controlled action is to create or select a dedicated isolated target
environment, apply the frozen vLLM plan through the environment package port,
run `pip check`, and then execute runtime qualification. The existing SGLang
environments remain untouched.

## Environment-ID qualification smoke

The new registry-backed entrypoint was exercised on the real server with
`--environment-id qwen36-sglang-v517-cu130`. The resulting evidence record
persisted both the environment ID and its lexical interpreter path:

- plan digest:
  `e19b9201241367771942cf653a7a2ea16c057b2fb35d94df7de59791f9911594`;
- request environment ID:
  `qwen36-sglang-v517-cu130`;
- request interpreter:
  `/data/research-platform/envs/qwen36-sglang-v517-cu130/bin/python`;
- decision: rejected;
- reason: the target-Python PyPI simple-index probe timed out.

The interpreter itself started as Python 3.11.15 and reported pip 24.0. A
server-side `curl` HEAD request to the same PyPI endpoint returned HTTP 200,
while a target-Python HTTPS GET timed out. This separates environment identity
resolution from the remaining Python-network transport issue. The system
therefore retained a rejection with evidence rather than using the controller
Python, silently retrying with a different environment, or accepting an
unverified package plan. The focused server regression after the new field and
CLI entrypoint is **23 passed**. The same server checkout also passed
`ARCHITECTURE_GATE_PASS` and `NO_DEGRADATION_AUDIT_PASS`.

The transport adapter was then corrected to use bounded system `curl` first and
target-Python `urllib` second, while keeping target-Python packaging tags,
markers and metadata-hash checks authoritative. With a 90-second complete
closure budget, the same environment produced a successful vLLM plan:

- facts digest:
  `33fd6893fc321150d99d8275ed205d0c7b25e2f1e5ac0c482df48de88df9edc8`;
- plan digest:
  `24eca0f99856d8b79f420f11abb9647a41d7544e6f4292fe8e6b334d6c26526a`;
- record digest:
  `3d6728b88aef28655234855552b807a6eb30095b61c1fe59f640f57ecf9429ad`;
- vLLM `0.27.1`, 162 closure nodes and 162 frozen packages including the
  backend root.

The 90-second value is now the shared default for the qualification request
and CLI. It is a time-budget correction, not a compatibility relaxation.
