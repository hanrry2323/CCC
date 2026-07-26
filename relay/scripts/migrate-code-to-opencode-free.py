#!/usr/bin/env python3
"""Migrate ~/.ccc/relay/upstreams.json: code → OpenCode free pool; Pro empty; retire xfyun.

Reuse existing opencode-go* API keys (no secrets in git). Idempotent.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

UPSTREAMS = Path.home() / ".ccc/relay/upstreams.json"
PROXY = "http://127.0.0.1:18080"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else UPSTREAMS
    if not path.is_file():
        print(f"missing {path}", file=sys.stderr)
        return 2

    data = json.loads(path.read_text())
    if not isinstance(data, list):
        print("upstreams.json must be a list", file=sys.stderr)
        return 2

    by_name = {u.get("name"): u for u in data if isinstance(u, dict) and u.get("name")}

    # Disable Pro / xfyun; park zhipu as last-resort disabled
    for name, patch in (
        ("opencode-go-pro", {"enabled": False, "description": "Pro 空档（pro→flash 回落）"}),
        ("xfyun-code", {"enabled": False, "description": "讯飞退役（套餐到期）"}),
        (
            "zhipu-code",
            {
                "enabled": False,
                "tier_priority": 99,
                "description": "code fail-open 末位（默认关）",
            },
        ),
    ):
        if name in by_name:
            by_name[name].update(patch)

    # Map flash keys → code rows (big-pickle + flash-free, dual egress)
    code_specs = [
        ("opencode-code-a", "opencode-go", "big-pickle", None),
        ("opencode-code-b", "opencode-go-b", "deepseek-v4-flash-free", None),
        ("opencode-code-d", "opencode-go-d", "big-pickle", PROXY),
        ("opencode-code-e", "opencode-go-e", "deepseek-v4-flash-free", PROXY),
        ("opencode-code-f", "opencode-go-f", "big-pickle", PROXY),
        ("opencode-code-g", "opencode-go-g", "deepseek-v4-flash-free", None),
    ]

    for code_name, flash_name, model, proxy in code_specs:
        src = by_name.get(flash_name)
        if not src or not src.get("api_key"):
            print(f"skip {code_name}: no key from {flash_name}")
            continue
        row = {
            "name": code_name,
            "tier": "code",
            "tier_priority": 1,
            "enabled": True,
            "base_url": "https://opencode.ai/zen/v1",
            "upstream_model": model,
            "models": ["code"],
            "api_key": src["api_key"],
            "transcode": True,
            "free": True,
            "provider_group": "opencode",
            "description": f"code 免费 · {model}" + (" · HK" if proxy else " · 直连"),
        }
        if proxy:
            row["proxy"] = proxy
        if code_name in by_name:
            # Preserve any manual tweaks except force free-pool fields
            existing = by_name[code_name]
            existing.update(row)
        else:
            data.append(row)
            by_name[code_name] = row
        print(f"upsert {code_name} model={model} proxy={bool(proxy)}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_suffix(path.suffix + f".bak.{stamp}")
    shutil.copy2(path, bak)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {path} (backup {bak.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
