#!/usr/bin/env bash
set -euo pipefail

bridge_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../research_platform/environment/minecraft/providers/assets/mineflayer_bridge" && pwd)"
command -v node >/dev/null || { echo 'NODE_NOT_EXECUTABLE' >&2; exit 2; }
command -v npm >/dev/null || { echo 'NPM_NOT_EXECUTABLE' >&2; exit 2; }
node --version
npm --version
cd "$bridge_dir"
npm ci --no-audit --no-fund
node -e "const p=require('mineflayer/package.json'); if(p.version!=='4.37.1') throw new Error('mineflayer version drift: '+p.version)"
node -e "const p=require('mineflayer-pathfinder/package.json'); if(p.version!=='2.4.5') throw new Error('pathfinder version drift: '+p.version)"
echo 'T2B_BRIDGE_DEPENDENCIES_READY'
