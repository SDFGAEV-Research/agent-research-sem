# syntax=docker/dockerfile:1.7

FROM ubuntu:24.04

ARG NODE_VERSION=22.22.2
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/usr/local/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl openjdk-21-jre-headless python3.12 python3.12-venv xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN cd /tmp \
    && curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
    && curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" \
    && grep " node-v${NODE_VERSION}-linux-x64.tar.xz$" SHASUMS256.txt | sha256sum -c - \
    && tar -xJf "node-v${NODE_VERSION}-linux-x64.tar.xz" --strip-components=1 -C /usr/local \
    && node --version && npm --version \
    && rm -f "node-v${NODE_VERSION}-linux-x64.tar.xz" SHASUMS256.txt

WORKDIR /opt/research-platform
COPY pyproject.toml README.md ./
COPY research_platform ./research_platform
COPY projects ./projects
COPY scripts ./scripts
COPY deploy ./deploy

RUN chmod 0755 /opt/research-platform/deploy/container-entrypoint.sh

RUN python3.12 -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/pip" install --upgrade pip setuptools wheel \
    && "$VIRTUAL_ENV/bin/pip" install . \
    && npm --prefix research_platform/environment/minecraft/providers/assets/mineflayer_bridge ci --omit=dev --ignore-scripts

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin platform \
    && mkdir -p /var/lib/research-platform /var/lib/minecraft \
    && chown -R platform:platform /opt/research-platform /var/lib/research-platform /var/lib/minecraft

USER platform
ENTRYPOINT ["/opt/research-platform/deploy/container-entrypoint.sh"]
CMD ["doctor"]
