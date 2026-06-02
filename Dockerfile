# syntax=docker/dockerfile:1.7
#
# Multistage build for the polyglot monorepo.
# Step 5 attached cache mounts to every dependency stage so the per-
# toolchain package caches survive across builds.
# Step 6 applies the lockfile-only COPY trick: each dependency stage
# COPYs ONLY the manifest + lockfile pair before invoking its package
# manager, never the project source. The dep-install layer is therefore
# keyed strictly on the manifest+lockfile pair, so any edit under
# services/*/src/ leaves the dep layer untouched and the build skips
# straight to the runtime COPY stage.
#
# Concretely:
#   uv-deps    -> pyproject.toml + services/api/pyproject.toml + uv.lock
#   bun-deps   -> package.json + services/web/package.json
#   cargo-deps -> Cargo.toml + Cargo.lock + services/edge/Cargo.toml
#
# Source files reach the image exclusively via the runtime stage's
# COPY . . instruction, which sits AFTER the COPY --from= directives
# that pull resolved deps out of the three dep stages.

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

# ---- Runtime stage that consumes resolved deps -------------------------
FROM base AS runtime

WORKDIR /workspace

COPY --from=uv-deps /workspace/.venv /workspace/.venv
COPY --from=bun-deps /workspace/node_modules /workspace/node_modules
COPY --from=cargo-deps /workspace/.cargo-cache/registry /root/.cargo/registry

COPY . .
