# Docker Compose runtime

This is the Linux-first runtime for both Linux hosts and Windows Docker
Desktop/WSL2. Native Windows process launch remains a separate compatibility
path; the application image is always Linux.

The image contains Python 3.12, Java 21, Node 22 and the lockfile-pinned
Mineflayer bridge. Minecraft server data is downloaded from the official Mojang
manifest on first `run` and stored in a named volume. Worlds, logs,
checkpoints and evidence survive container recreation.

```bash
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml --env-file deploy/.env build
docker compose -f deploy/compose.yaml --env-file deploy/.env run --rm platform-runtime doctor
docker compose -f deploy/compose.yaml --env-file deploy/.env run --rm platform-runtime run
```

On Linux/WSL2 without a system Docker installation, the repository includes a
workspace-local client/daemon installer. It places Docker storage under the
Linux filesystem by default and never installs a native Windows daemon.

```bash
bash deploy/install_workspace_docker_engine.sh install
export PATH="$PWD/.docker-engine/bin:$PATH"
export DOCKER_CONFIG="$PWD/.docker-engine/config"
bash deploy/install_workspace_docker_engine.sh start
```

The daemon requires rootful Linux namespace/cgroup capabilities. On Windows,
use Docker Desktop WSL integration or run the installer inside WSL2.
