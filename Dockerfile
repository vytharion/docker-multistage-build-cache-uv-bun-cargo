# syntax=docker/dockerfile:1.7
#
# Naive single-stage build for the polyglot monorepo.
# Everything — Python, TypeScript, and Rust toolchains plus every workspace
# source file — lives in one image, baked in one COPY layer. This is the
# baseline we will improve against in the rest of the tutorial.

FROM debian:12-slim

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

COPY . .

RUN uv sync \
    && bun install \
    && cargo fetch
