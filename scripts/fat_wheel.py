#!/usr/bin/env python3
"""Merge a dependency wheel into a project wheel to produce a fat wheel.

Usage: fat_wheel.py <project_wheel> <dep_wheel> <output_dir>

Intended for use with PyApp (PYAPP_PROJECT_PATH), not direct pip installation.
The dependency's files are embedded directly into the project wheel. The RECORD
is rebuilt with correct SHA-256 hashes, the WHEEL Tag is updated to the
dependency's platform tag (since compiled extensions are now included), and the
dependency is removed from Requires-Dist in METADATA.

Prints the path of the produced wheel to stdout.
"""

from __future__ import annotations

import base64
import hashlib
import re
import sys
import zipfile
from pathlib import Path


def _sha256(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def build_fat_wheel(project_wheel: str, dep_wheel: str, output_dir: str) -> Path:
    files: dict[str, bytes] = {}

    with zipfile.ZipFile(project_wheel) as zf:
        for name in zf.namelist():
            if not name.endswith("/"):
                files[name] = zf.read(name)

    our_dist_info = next((name.split("/")[0] for name in files if ".dist-info/" in name), None)
    if our_dist_info is None:
        msg = f"No .dist-info directory found in wheel: {project_wheel}"
        raise ValueError(msg)

    with zipfile.ZipFile(dep_wheel) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            first_dir = name.split("/")[0]
            if ".dist-info" in first_dir or "__pycache__" in name:
                continue
            files[name] = zf.read(name)

    dep_name = Path(dep_wheel).stem.split("-")[0].lower()
    # Last three dash-separated parts of the stem are always python-abi-platform
    platform_tag = "-".join(Path(dep_wheel).stem.split("-")[-3:])

    wheel_key = f"{our_dist_info}/WHEEL"
    wheel_text = files[wheel_key].decode()
    wheel_text = re.sub(r"^Tag:.*$", f"Tag: {platform_tag}", wheel_text, flags=re.MULTILINE)
    wheel_text = re.sub(r"^Root-Is-Purelib:.*$", "Root-Is-Purelib: false", wheel_text, flags=re.MULTILINE)
    files[wheel_key] = wheel_text.encode()

    metadata_key = f"{our_dist_info}/METADATA"
    metadata = files[metadata_key].decode()
    metadata = re.sub(
        rf"^Requires-Dist:\s+{dep_name}[^\n]*\n",
        "",
        metadata,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    files[metadata_key] = metadata.encode()

    record_key = f"{our_dist_info}/RECORD"
    sorted_paths = sorted(path for path in files if path != record_key)
    record_lines = [f"{path},{_sha256(files[path])},{len(files[path])}" for path in sorted_paths]
    record_lines.append(f"{record_key},,")
    files[record_key] = "\n".join(record_lines).encode()

    # Derive a PEP 427-compliant filename: {dist}-{version}-{python}-{abi}-{platform}.whl
    proj_stem_parts = Path(project_wheel).stem.split("-")  # e.g. cortical_peaks_challenge_2026-0.0.0-py3-none-any
    dist_name, version = proj_stem_parts[0], proj_stem_parts[1]
    output = Path(output_dir) / f"{dist_name}-{version}-{platform_tag}.whl"

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted_paths:
            zf.writestr(path, files[path])
        zf.writestr(record_key, files[record_key])

    print(f"fat wheel → {output}  ({output.stat().st_size // 1_000_000} MB)", file=sys.stderr)  # noqa: T201
    print(output)  # noqa: T201 — callers capture this to get the path
    return output


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <project_wheel> <dep_wheel> <output_dir>", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    build_fat_wheel(sys.argv[1], sys.argv[2], sys.argv[3])
