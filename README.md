# docker-multistage-build-cache-uv-bun-cargo

Companion repository for the article series at <https://monorepo.nicedx.com/docker-multistage-build-cache-uv-bun-cargo/>.

This repo demonstrates how to drive a polyglot monorepo — Python, TypeScript,
and Rust members living together — through the cache-aware Docker build
patterns introduced step by step in the article.

## Layout

```
.
├── pyproject.toml       # uv workspace root (Python)
├── package.json         # bun workspace root (TypeScript)
├── Cargo.toml           # cargo workspace root (Rust)
└── services/
    ├── api/             # Python member, exercised by pytest
    ├── web/             # TypeScript member, exercised by bun test
    └── edge/            # Rust member, exercised by cargo test
```

## Running the tests

Each toolchain runs its own test command from the repository root:

```bash
pytest                    # Python tests for services/api
bun test                  # TypeScript tests for services/web
cargo test --workspace    # Rust tests for services/edge
```

Walk the article step by step by stepping through git commits — each step
has its own commit pair (an intent commit, then a completion commit).
