# Docker Compose runtime

This is the Linux-first runtime for Linux servers and Windows Docker Desktop/WSL2.
The application image is always Linux and is the authoritative reusable environment.
It contains Python 3.12, Java 21, Node 22 and the lockfile-pinned Mineflayer bridge.

## Storage policy

Server deployments must keep project checkout, image archives and persistent runtime
state on a selected data HDD. `PLATFORM_HOST_DATA_ROOT` is an explicit bind-mount
root, so persistent state does not silently follow Docker's daemon data-root.

Current fleet roots:

- `node-118-190-202-247`: `/data1/research-platform`
- `node-121-48-164-241`: `/data/hdd1/research-platform`

Runtime state lives below `<root>/runtime/{minecraft,platform-state}`.
The container image itself is immutable; only the bind-mounted state is mutable.

## Build once, reuse everywhere

Use the exact Git commit as the image tag. Build on one designated builder only:

```bash
export PLATFORM_IMAGE="research-platform:$(git rev-parse --short=12 HEAD)"
export PLATFORM_HOST_DATA_ROOT=/data/hdd1/research-platform/runtime
docker compose -f deploy/compose.yaml build platform-runtime
docker compose -f deploy/compose.yaml run --rm platform-runtime doctor
```
Export that exact image to HDD when a registry is not configured:

```bash
mkdir -p /data/hdd1/research-platform/images
docker save "$PLATFORM_IMAGE" | gzip -1 > "/data/hdd1/research-platform/images/${PLATFORM_IMAGE/:/_}.tar.gz"
sha256sum "/data/hdd1/research-platform/images/${PLATFORM_IMAGE/:/_}.tar.gz"
```

On another server, load the same image instead of rebuilding it, set that host's
HDD root, and always use `--no-build`:

```bash
gzip -dc research-platform_IMAGE.tar.gz | docker load
export PLATFORM_IMAGE=research-platform:<exact-commit-tag>
export PLATFORM_HOST_DATA_ROOT=/data1/research-platform/runtime
docker compose -f deploy/compose.yaml run --no-build --rm platform-runtime doctor
docker compose -f deploy/compose.yaml up --no-build -d platform-runtime
```

The image digest and archive SHA-256 should be recorded by deployment automation.
Never rebuild a server-local image under the same immutable commit tag.

On Linux/WSL2 without a system Docker installation, the repository also includes
`deploy/install_workspace_docker_engine.sh`. Server fleet machines should use the
host Docker installation and the HDD policy above rather than creating per-project
daemons.
