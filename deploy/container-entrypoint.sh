#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=/opt/research-platform
MC_VERSION="${MC_SERVER_VERSION:-1.21.8}"
MC_JAR="${MC_SERVER_JAR:-/var/lib/minecraft/server.jar}"
MC_WORKDIR="${MC_WORKDIR:-/var/lib/minecraft/t2b-gate}"
BRIDGE_DIR="${MC_BRIDGE_DIR:-$ROOT/research_platform/environment/minecraft/providers/assets/mineflayer_bridge}"

die() { echo "container-entrypoint: $*" >&2; exit 2; }

ensure_server_jar() {
  if [[ -f "$MC_JAR" ]]; then return 0; fi
  mkdir -p "$(dirname "$MC_JAR")"
  python - "$MC_VERSION" "$MC_JAR" <<'PY'
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

version, target_text = sys.argv[1:]
target = Path(target_text)
hosts = {"piston-meta.mojang.com", "piston-data.mojang.com", "launcher.mojang.com"}

def read_json(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise RuntimeError(f"untrusted Mojang URL: {url}")
    with urlopen(Request(url, headers={"User-Agent": "research-platform-docker/1"}), timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

manifest = read_json("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
entry = next((row for row in manifest["versions"] if row.get("id") == version), None)
if not entry:
    raise RuntimeError(f"Minecraft version not found: {version}")
server = read_json(entry["url"])["downloads"]["server"]
url = server["url"]
parsed = urlparse(url)
if parsed.scheme != "https" or parsed.hostname not in hosts:
    raise RuntimeError(f"untrusted server URL: {url}")
expected = server["sha1"].lower()
partial = target.with_name(target.name + ".partial")
with urlopen(Request(url, headers={"User-Agent": "research-platform-docker/1"}), timeout=180) as source, partial.open("wb") as sink:
    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        sink.write(chunk)
digest = hashlib.sha1(partial.read_bytes()).hexdigest()
if digest != expected:
    partial.unlink(missing_ok=True)
    raise RuntimeError(f"Minecraft server SHA-1 mismatch: expected {expected}, got {digest}")
partial.replace(target)
print(json.dumps({"version": version, "target": str(target), "sha1": digest}, sort_keys=True))
PY
}

doctor() {
  python --version
  java -version 2>&1 | head -1
  node --version
  npm --version
  python - "$BRIDGE_DIR" <<'PY'
from pathlib import Path
import json
import subprocess
import sys

bridge = Path(sys.argv[1])
package = json.loads((bridge / "package.json").read_text())
if not (bridge / "node_modules").is_dir():
    raise SystemExit("Mineflayer dependencies are not installed")
subprocess.run(["npm", "--prefix", str(bridge), "test"], check=True)
print(f"bridge={package['name']} dependencies=ready")
PY
  if [[ -f "$MC_JAR" ]]; then
    sha256sum "$MC_JAR"
    echo "minecraft_server_jar=ready version=$MC_VERSION"
  else
    echo "minecraft_server_jar=missing version=$MC_VERSION (run bootstrap or run)"
  fi
}

run_t2b() {
  ensure_server_jar
  mkdir -p "$MC_WORKDIR"
  exec python "$ROOT/scripts/t2b_local_gate.py" \
    --server-jar "$MC_JAR" \
    --workdir "$MC_WORKDIR" \
    --bridge-dir "$BRIDGE_DIR" \
    --java java \
    --node node \
    --version "$MC_VERSION" \
    --timeout-s "${MC_T2B_TIMEOUT_S:-180}"
}

case "${1:-doctor}" in
  doctor) doctor ;;
  bootstrap) ensure_server_jar ;;
  run) run_t2b ;;
  test)
    doctor
    exec python -m unittest discover -s "$ROOT/tests" -p 'test_*.py'
    ;;
  shell)
    shift
    exec "${@:-bash}"
    ;;
  *) die "unknown command '$1' (expected doctor, bootstrap, run, test or shell)" ;;
esac
