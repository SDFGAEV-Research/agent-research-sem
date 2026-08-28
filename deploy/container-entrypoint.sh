#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/research-platform
STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/research-platform}"

die() {
  echo "container-entrypoint: $*" >&2
  exit 2
}

doctor() {
  python --version
  python - <<'PY'
from importlib.metadata import version
import research_platform

print(f"research_platform_import={research_platform.__name__}")
print(f"research_platform_version={version('research-platform')}")
PY
  research-platform-manage --help >/dev/null
  research-platform-architecture-gate --help >/dev/null 2>&1 || true
  mkdir -p "$STATE_DIR"
  test -w "$STATE_DIR"
  echo "platform_state_dir=$STATE_DIR writable=true"
}

case "${1:-doctor}" in
  doctor)
    doctor
    ;;
  verify)
    doctor
    exec python "$ROOT/scripts/architecture_gate.py"
    ;;
  shell)
    shift
    if [[ $# -eq 0 ]]; then
      exec /bin/sh
    fi
    exec "$@"
    ;;
  *)
    die "unknown command '$1' (expected doctor, verify or shell)"
    ;;
esac
