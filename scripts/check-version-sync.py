#!/usr/bin/env python3
"""F-VER-01: 校验 VERSION 与主要文档/包版本一致。"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
assert VERSION.startswith("v"), f"VERSION must start with v, got {VERSION!r}"
SEMVER = VERSION.lstrip("v")

ERRORS: list[str] = []


def check_contains(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        ERRORS.append(f"{path.relative_to(ROOT)}: missing {needle!r}")


check_contains(ROOT / "SKILL.md", VERSION)
check_contains(ROOT / "STARTUP-BRIEF.md", VERSION)
check_contains(ROOT / "CLAUDE.md", VERSION)
check_contains(ROOT / "README.md", VERSION)

pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
if pkg.get("version") != SEMVER:
    ERRORS.append(f"package.json version={pkg.get('version')!r} != {SEMVER}")

tauri = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
if tauri.get("package", {}).get("version") != SEMVER:
    ERRORS.append(f"tauri.conf.json package.version mismatch")

cargo = (ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
if not re.search(rf'^version\s*=\s*"{re.escape(SEMVER)}"', cargo, re.M):
    ERRORS.append(f"Cargo.toml version != {SEMVER}")

if ERRORS:
    print("VERSION sync FAILED:")
    for e in ERRORS:
        print(" -", e)
    sys.exit(1)
print(f"VERSION sync OK ({VERSION})")
