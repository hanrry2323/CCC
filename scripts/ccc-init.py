#!/usr/bin/env python3
"""ccc-init — new project initialization for CCC.

Usage: ccc init <project_path> [--force]
Reads AGENTS.md and .ccc-profile.md templates from ~/program/CCC/templates/,
replaces placeholders, and writes to the target project directory.

Placeholders: {{PROJECT_NAME}} {{PROJECT_PATH}} {{PRIMARY_LANGUAGE}} {{DATE}}
"""

import os
import sys
from datetime import date
from pathlib import Path

CCC_HOME = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = CCC_HOME / "templates"
TEMPLATES = {
    "AGENTS.md": TEMPLATE_DIR / "AGENTS.md",
    ".ccc/profile.md": TEMPLATE_DIR / ".ccc-profile.md",
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
    counts = {}
    for ext, lang in LANG_EXT_MAP.items():
        matches = list(proj_path.rglob(f"*.{ext}"))
        if matches:
            counts[lang] = counts.get(lang, 0) + len(matches)
    if not counts:
        return "Unknown"
    return max(counts, key=counts.get)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv

    if not args:
        print("Usage: ccc init <project_path> [--force] [--lang <lang>]", file=sys.stderr)
        sys.exit(1)

    proj_path = Path(args[0]).expanduser().resolve()

    if not proj_path.is_dir():
        print(f"Error: target path '{proj_path}' does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    lang_override = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--lang" and i + 2 < len(sys.argv):
            lang_override = sys.argv[i + 2]

    primary_lang = lang_override or detect_language(proj_path)

    missing = [k for k, p in TEMPLATES.items() if not p.is_file()]
    if missing:
        print(f"Error: template(s) not found: {', '.join(str(TEMPLATES[k]) for k in missing)}", file=sys.stderr)
        sys.exit(1)

    replacements = {
        "{{PROJECT_NAME}}": proj_path.name,
        "{{PROJECT_PATH}}": str(proj_path),
        "{{PRIMARY_LANGUAGE}}": primary_lang,
        "{{DATE}}": date.today().isoformat(),
    }

    writes = {
        proj_path / "AGENTS.md": TEMPLATES["AGENTS.md"],
        proj_path / ".ccc" / "profile.md": TEMPLATES[".ccc/profile.md"],
    }

    for dst, src in writes.items():
        if dst.exists() and not force:
            print(f"Skip: {dst} already exists (use --force to overwrite)", file=sys.stderr)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        content = src.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        dst.write_text(content, encoding="utf-8")
        print(f"Created: {dst}")

    print(f"\nDone. Project '{proj_path.name}' initialized for CCC.")
    print(f"  Primary language: {primary_lang}")
    print("Next: edit AGENTS.md and .ccc/profile.md to match your project.")


if __name__ == "__main__":
    main()
