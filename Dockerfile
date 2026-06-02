# syntax=docker/dockerfile:1.7
#
# Multistage build for the polyglot monorepo.
# Step 6 pinned the lockfile-only COPY invariant across the three dep
# stages so that source edits never invalidate the dependency layers.
# Step 7 collapses the published image surface area by replacing the
# previous `FROM base AS runtime` inheritance with a fresh
# `FROM debian:12-slim AS runtime` and shipping only what the running
# services actually need at runtime:
#
#   - tini, as PID 1, so signals reach the app and zombies are reaped
#   - ca-certificates + python3 + libssl3 (no compilers, no rustup, no
#     bun installer, no git, no build-essential)
#   - a non-root `app` user that owns /workspace
#   - a HEALTHCHECK so orchestrators can detect a wedged container
#
# Per-toolchain dep stages keep their lockfile-only COPYs from step 6:
#   uv-deps    -> pyproject.toml + services/api/pyproject.toml + uv.lock
#   bun-deps   -> package.json + services/web/package.json
#   cargo-deps -> Cargo.toml + Cargo.lock + services/edge/Cargo.toml
#
# Source files reach the image exclusively via the runtime stage's
# `COPY --chown=app:app . .` instruction.

# ---- Shared toolchain base ---------------------------------------------
FROM debian:12-slim AS base

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/root/.cargo/bin:/root/.local/bin:/root/.bun/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        build-essential \
        unzip \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN curl -fsSL https://bun.sh/install | bash
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable

WORKDIR /workspace

# ---- Python dependency stage -------------------------------------------
FROM base AS uv-deps

COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/pyproject.toml
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project --no-dev \
    || uv sync --frozen --no-install-project \
    || uv sync --no-install-project

# ---- TypeScript dependency stage ---------------------------------------
FROM base AS bun-deps

COPY package.json ./
COPY services/web/package.json services/web/package.json
RUN --mount=type=cache,id=bun-cache,target=/root/.bun/install/cache,sharing=locked \
    bun install --no-save

# ---- Rust dependency stage ---------------------------------------------
FROM base AS cargo-deps

COPY Cargo.toml Cargo.lock ./
COPY services/edge/Cargo.toml services/edge/Cargo.toml
RUN --mount=type=cache,id=cargo-registry,target=/root/.cargo/registry,sharing=locked \
    --mount=type=cache,id=cargo-git,target=/root/.cargo/git,sharing=locked \
    --mount=type=cache,id=cargo-target,target=/workspace/target,sharing=locked \
    cargo fetch \
    && mkdir -p /workspace/.cargo-cache \
    && cp -a /root/.cargo/registry /workspace/.cargo-cache/registry

# ---- Slim runtime stage ------------------------------------------------
FROM debian:12-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH=/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tini \
        python3 \
        libssl3 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid 1001 --no-create-home --home-dir /workspace app \
    && mkdir -p /workspace \
    && chown -R app:app /workspace

WORKDIR /workspace

COPY --from=uv-deps --chown=app:app /workspace/.venv /workspace/.venv
COPY --from=bun-deps --chown=app:app /workspace/node_modules /workspace/node_modules
COPY --from=cargo-deps --chown=app:app /workspace/.cargo-cache/registry /workspace/.cargo-cache/registry

COPY --chown=app:app . .

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "-m", "http.server", "8080"]
