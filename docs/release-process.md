# Release Process

This document explains how to publish a new Cortical Peaks Challenge 2026 release. A release produces six self-contained binaries (server + spectator for each of three platforms) and publishes them as a GitHub Release.

## Prerequisites

| Tool                  | Purpose                                      |
| --------------------- | -------------------------------------------- |
| `uv`                  | Build the project wheel                      |
| `cargo` / Rust stable | Local binary builds only (`just build-dist`) |
| Git push access       | Push tags to `origin`                        |

Cargo is only needed if you want to build binaries locally for testing. CI builds all platforms automatically.

## Binary naming

Each release ships the following artifacts:

| Binary                             | Platform              |
| ---------------------------------- | --------------------- |
| `cpc-server-macos-arm64`           | macOS (Apple Silicon) |
| `cpc-spectator-macos-arm64`        | macOS (Apple Silicon) |
| `cpc-server-windows-x86_64.exe`    | Windows               |
| `cpc-spectator-windows-x86_64.exe` | Windows               |
| `cpc-server-linux-x86_64`          | Ubuntu / Debian       |
| `cpc-spectator-linux-x86_64`       | Ubuntu / Debian       |

Each binary embeds three things at build time (~45 MB total):

- **Python 3.14 runtime** (~30 MB, via `PYAPP_DISTRIBUTION_EMBED=true`)
- **Project wheel** (all game code + assets)
- **pygame** (merged into the project wheel as a "fat wheel" by `scripts/fat_wheel.py`)

No internet access is required at any point — not on first launch, not ever.

## Step-by-step release guide

### 1. Pre-release checks

Ensure `main` is clean and CI is green.

```bash
git checkout main
git pull
uv run just check
```

### 2. Bump the version

Update the version in `pyproject.toml`:

```toml
[project]
version = "0.x.y"  # was "0.0.0"
```

Re-lock the project, if necessary.

```bash
uv lock
```

Commit the bump:

```bash
git add pyproject.toml
git add uv.lock
git commit -m "chore: bump version to 0.x.y"
```

> The version in `pyproject.toml` must match the numeric part of the tag: tag `v0.1.0` → `version = "0.1.0"` in `pyproject.toml` (no `v` prefix). The release workflow strips the `v` automatically before baking `PYAPP_PROJECT_VERSION` into the binary, so both stay in sync.

### 3. Tag and push

```bash
git tag v0.x.y
git push origin main
git push origin v0.x.y
```

The `push: tags: ['v*']` trigger in `release.yml` fires automatically.

### 4. Monitor CI

Go to **Actions -> Release** in the GitHub UI. You will see six build jobs running in parallel (one per platform/mode combination) and a final `Create GitHub Release` job that runs after all eight complete.

Each job is named `build (server, macos-latest)`, `build (spectator, windows-latest)`, etc.

If a single job fails, you can **re-run failed jobs** from the Actions UI without deleting the tag.

### 5. Verify the release

Once CI completes, check the [Releases page](https://github.com/neuroTUM/cortical-peaks-challenge-2026/releases). Confirm:

- All six binaries are attached.
- The changelog is auto-generated from conventional commit messages since the previous tag.
- The release title matches the tag.

## Testing a binary locally

To build and test a binary before tagging, use:

```bash
uv run just build-dist 0.x.y
```

This produces:

- `dist/server/bin/cpc-server` (macOS/Linux)
- `dist/spectator/bin/cpc-spectator` (macOS/Linux)

On macOS, you will need to allow the binary in **System Settings -> Privacy & Security -> Allow Anyway** (see Gatekeeper section below).

## macOS Gatekeeper

Binaries are ad-hoc signed but not notarised. On first launch macOS will block them with a "cannot be opened because it is from an unidentified developer" dialog.

**Workaround:**

1. Right-click the binary -> **Open** -> click **Open** in the dialog.
   OR
2. Go to **System Settings -> Privacy & Security**, scroll to the blocked app, click **Allow Anyway**.

## Rolling back a bad release

If a release is broken and needs to be retracted:

```bash
# Delete the tag remotely and locally
git push origin :refs/tags/v0.x.y
git tag -d v0.x.y
```

Then delete the GitHub Release from the Releases UI. Fix the issue, commit, and retag.

## Versioning scheme

We follow semantic versioning informally:

| Bump          | When                                                       |
| ------------- | ---------------------------------------------------------- |
| Patch `0.0.x` | Bug fixes, asset tweaks                                    |
| Minor `0.x.0` | New games, significant features                            |
| Major `x.0.0` | Breaking changes to the BCI protocol or complete overhauls |

Target a stable `v1.0.0` once the feature set is complete and the app has run successfully at a real event.
