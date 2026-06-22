# Contributing to Cortical Peaks Challenge 2026

Thanks for your interest in improving the project! This guide covers how to set up your environment, the conventions we follow, and how to propose changes.

## For Maintainers & Contributors

For anything beyond a trivial change (typo fixes, small doc tweaks, or obvious one-line bug fixes), **please open a GitHub issue before starting work**. A short discussion up front lets us agree on the approach, avoid duplicated effort, and make sure the change fits the direction of the project. Once we have aligned on the issue, go ahead and open a pull request that references it.

Trivial changes can go straight to a PR.

## For Participating Teams

If you run into any bugs or have any feature requests, please open an issue right here in the repository. It's the best way for us to track requests and discuss them with you!

## Requirements

Python 3.14 is required. [`uv`](https://docs.astral.sh/uv/) manages the interpreter automatically, so no manual install is needed.

## Development workflow

```bash
uv run just setup    # install dependencies + pre-commit hooks (run once)
uv run just check    # format, lint, type-check, test - must pass before pushing
```

`just check` runs `ruff format`, `ruff check`, `ty check`, and `pytest` in sequence. Pre-commit hooks enforce formatting and lockfile consistency on every commit.

You can list all available recipes with `uv run just --list`.

## Commit conventions

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

Types: feat, fix, chore, test, style, docs, refactor
Scope: optional, usually the game or module name (e.g. dino, server, pong)
```

Example: `feat(dino): widen zone markers to show the action window`

## Pull requests

1. Make sure the related issue is linked (for non-trivial changes).
2. Run `uv run just check` and confirm it passes before pushing.
3. Keep PRs focused; smaller, single-purpose changes are easier to review.

## Continuous integration and releases

GitHub Actions runs two pipelines:

- **CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every pull request and on pushes to `main`. It checks formatting, linting, types, and the test suite across Ubuntu, macOS, and Windows (only when Python-relevant files change). CI must be green before a PR can be merged; running `uv run just check` locally first is the fastest way to keep it that way.
- **Release** ([`.github/workflows/release.yml`](.github/workflows/release.yml)) is triggered by pushing a `v*` tag. It builds the self-contained server and spectator binaries for all three platforms and publishes them as a GitHub Release. The full procedure is documented in [`docs/release-process.md`](docs/release-process.md).

A merged change does not automatically ship. **Versions are currently published at the maintainers' discretion**: the maintainers decide when to cut a release and push the corresponding tag.

## Protocol references

If your change touches networking, game state, or how clients talk to the server, read the relevant protocol document first. The two protocols are intentionally kept separate:

- [`PROTOCOL.md`](PROTOCOL.md) - the **public BCI Client / Game Server protocol**. This is the contract that competing teams implement against. Changes here are breaking for every team, so treat it as a stable public API.
- [`docs/internal-wire-protocol.md`](docs/internal-wire-protocol.md) - the **internal wire protocol** used by spectator (renderer) clients, including the binary game-state formats carried inside `STATE` messages. Read this when adding a new game or changing how game state is serialized and rendered.
