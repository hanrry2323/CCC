#!/usr/bin/env python3
"""ccc-init — 将任意目录接入 CCC Hub / Board / Engine。

Usage:
  python3 scripts/ccc-init.py <project_path> [--force] [--lang <lang>] [--register]

做的事：
  - AGENTS.md + .ccc/profile.md（模板）
  - 七列 .ccc/board/（Hub 发现条件）
  - 种子 .ccc/state.md、根目录 CLAUDE.md（若不存在）
  - --register → 幂等写入 ~/.ccc/workspaces.json（Engine 消费名单）

权威说明：docs/workspace-binding.md
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

CCC_HOME = Path(__file__).resolve().parent.parent
SCRIPTS = CCC_HOME / "scripts"
TEMPLATE_DIR = CCC_HOME / "templates"
TEMPLATES = {
    "AGENTS.md": TEMPLATE_DIR / "AGENTS.md",
    ".ccc/profile.md": TEMPLATE_DIR / ".ccc-profile.md",
    "CLAUDE.md": TEMPLATE_DIR / "project-CLAUDE.md",
    ".ccc/state.md": TEMPLATE_DIR / "project-state.md",
}

LANG_EXT_MAP = {
    "py": "Python",
    "js": "JavaScript",
    "ts": "TypeScript",
    "jsx": "React/JSX",
    "tsx": "React/TSX",
    "go": "Go",
    "rs": "Rust",
    "rb": "Ruby",
    "java": "Java",
    "kt": "Kotlin",
    "swift": "Swift",
    "c": "C",
    "cpp": "C++",
    "h": "C/C++ Header",
    "cs": "C#",
    "php": "PHP",
    "sh": "Bash/Shell",
    "bash": "Bash/Shell",
    "pl": "Perl",
    "lua": "Lua",
    "ex": "Elixir",
    "exs": "Elixir",
    "hs": "Haskell",
    "scala": "Scala",
    "clj": "Clojure",
    "dart": "Dart",
    "vue": "Vue.js",
    "svelte": "Svelte",
}


def detect_language(proj_path: Path) -> str:
    counts: dict[str, int] = {}
    for ext, lang in LANG_EXT_MAP.items():
        matches = list(proj_path.rglob(f"*.{ext}"))
        # 跳过常见噪音目录
        matches = [
            m
            for m in matches
            if ".git" not in m.parts
            and "node_modules" not in m.parts
            and ".venv" not in m.parts
        ]
        if matches:
            counts[lang] = counts.get(lang, 0) + len(matches)
    if not counts:
        return "Unknown"
    return max(counts, key=counts.get)


def _render(src: Path, replacements: dict[str, str]) -> str:
    content = src.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        content = content.replace(placeholder, value)
    return content


def ensure_board(proj_path: Path) -> None:
    """创建七列看板（Hub discover 条件）。"""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from _board_store import FileBoardStore  # noqa: WPS433

    FileBoardStore(proj_path)
    print(f"Ensured: {proj_path / '.ccc' / 'board'} (7 columns)")


def maybe_register(proj_path: Path, name: str | None = None) -> dict:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from _workspace_registry import register_workspace  # noqa: WPS433

    return register_workspace(proj_path, name=name or proj_path.name)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in argv
    do_register = "--register" in argv
    argv = [a for a in argv if a not in ("--force", "--register")]

    lang_override = None
    filtered_args: list[str] = []
    skip_next = False
    for i, a in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if a == "--lang" and i + 1 < len(argv):
            lang_override = argv[i + 1]
            skip_next = True
            continue
        if not a.startswith("--"):
            filtered_args.append(a)

    if not filtered_args:
        print(
            "Usage: ccc-init.py <project_path> [--force] [--lang <lang>] [--register]",
            file=sys.stderr,
        )
        print("See docs/workspace-binding.md", file=sys.stderr)
        return 1

    proj_path = Path(filtered_args[0]).expanduser().resolve()
    if not proj_path.is_dir():
        print(
            f"Error: target path '{proj_path}' does not exist or is not a directory.",
            file=sys.stderr,
        )
        return 1

    primary_lang = lang_override or detect_language(proj_path)
    missing = [k for k, p in TEMPLATES.items() if not p.is_file()]
    if missing:
        print(
            f"Error: template(s) not found: {', '.join(str(TEMPLATES[k]) for k in missing)}",
            file=sys.stderr,
        )
        return 1

    replacements = {
        "{{PROJECT_NAME}}": proj_path.name,
        "{{PROJECT_PATH}}": str(proj_path),
        "{{PRIMARY_LANGUAGE}}": primary_lang,
        "{{DATE}}": date.today().isoformat(),
    }

    writes = {
        proj_path / "AGENTS.md": TEMPLATES["AGENTS.md"],
        proj_path / ".ccc" / "profile.md": TEMPLATES[".ccc/profile.md"],
        proj_path / "CLAUDE.md": TEMPLATES["CLAUDE.md"],
        proj_path / ".ccc" / "state.md": TEMPLATES[".ccc/state.md"],
    }

    for dst, src in writes.items():
        if dst.exists() and not force:
            print(f"Skip: {dst} already exists (use --force to overwrite)", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_render(src, replacements), encoding="utf-8")
        print(f"Created: {dst}")

    ensure_board(proj_path)

    if do_register:
        result = maybe_register(proj_path)
        if not result.get("ok"):
            print(f"Register failed: {result.get('error')}", file=sys.stderr)
            return 1
        verb = "Registered" if result.get("added") else "Already registered"
        print(f"{verb}: {result.get('path')} → {result.get('registry')}")

    print(f"\nDone. Project '{proj_path.name}' ready for CCC Hub.")
    print(f"  Primary language: {primary_lang}")
    print(f"  Board: {proj_path / '.ccc' / 'board'}")
    print("Next:")
    print(f"  1. Edit {proj_path / 'CLAUDE.md'} (project cognition)")
    print(f"  2. Edit {proj_path / '.ccc' / 'profile.md'}")
    print("  3. Open Hub → refresh projects → select this project")
    print("  4. Docs: docs/workspace-binding.md")
    if not do_register:
        print("  (Engine): re-run with --register, or dispatch once from Hub")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
