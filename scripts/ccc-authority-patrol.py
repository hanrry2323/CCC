#!/usr/bin/env python3
"""ccc-authority-patrol — 对照权威硬卡巡查；仅违规时人话报警。

契约：docs/product/loop-engineer-authority.md · 平台自动维护 + 违背才找老板
卡片：references/authority-patrol.jsonl（机读，不给人当说明书）

用法：
  python3 scripts/ccc-authority-patrol.py           # 安静成功 / 违规 exit 2 + notify
  python3 scripts/ccc-authority-patrol.py --quiet    # 仅退出码，不弹通知
  python3 scripts/ccc-authority-patrol.py --json     # 机器可读结果
  python3 scripts/ccc-authority-patrol.py --dry-run  # 不写 alerts / 不 notify

退出码：0=绿，2=有红灯，1=脚本错误
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "references" / "authority-patrol.jsonl"
NOTIFY = Path(__file__).resolve().parent / "ccc-notify.sh"
CONTROL = Path.home() / ".ccc" / "control.json"

_FORBID_MARKERS = ("禁止", "勿", "不要", "不得", "不认", "不更换", "不是", "≠", "禁")
_ALT_IDE_RE = re.compile(
    r"(用\s*(Claude\s*Code|Trae|Zed)\s*改|在\s*(Claude\s*Code|Trae|Zed)\s*(里|中)?\s*(改|开发)|"
    r"(Claude\s*Code|Trae|Zed)\s*(改本仓|改平台|作为平台|当平台))",
    re.I,
)
_LAN_DEFAULT_RE = re.compile(
    r"(default|DEFAULT|hubBase|hub_url|CCC_HUB|HUB_URL|baseURL|base_url).{0,80}192\.168\.3\.116:7777|"
    r"192\.168\.3\.116:7777.{0,40}(default|默认|主路径)",
    re.I | re.S,
)


def _load_cards() -> list[dict[str, Any]]:
    if not CARDS.is_file():
        raise FileNotFoundError(f"missing patrol cards: {CARDS}")
    out: list[dict[str, Any]] = []
    for line in CARDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(json.loads(line))
    return out


def _iter_files(paths: list[str], exclude_globs: list[str] | None = None) -> list[Path]:
    exclude_globs = exclude_globs or []
    files: list[Path] = []
    for raw in paths:
        p = ROOT / raw
        if p.is_file():
            files.append(p)
            continue
        if not p.is_dir():
            continue
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() not in {
                ".md",
                ".mdc",
                ".py",
                ".swift",
                ".sh",
                ".json",
                ".txt",
                ".yml",
                ".yaml",
            }:
                continue
            rel = f.relative_to(ROOT).as_posix()
            if any(_glob_match(rel, g) for g in exclude_globs):
                continue
            files.append(f)
    return files


def _glob_match(path: str, pattern: str) -> bool:
    # minimal ** / * support
    from fnmatch import fnmatch

    return fnmatch(path, pattern.lstrip("./"))


def _line_is_forbid(line: str) -> bool:
    return any(m in line for m in _FORBID_MARKERS)


def probe_no_affirmative_alt_ide(card: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    for f in _iter_files(card.get("paths") or [], card.get("exclude_globs")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if not _ALT_IDE_RE.search(line):
                continue
            if _line_is_forbid(line):
                continue
            # historical/changelog tone
            if "史" in line or "已退役" in line or "不再" in line:
                continue
            hits.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:160]}")
            if len(hits) >= 5:
                return hits
    return hits


def probe_grep_absent(card: dict[str, Any]) -> list[str]:
    """Fail if pattern appears in an affirmative (non-forbid) line."""
    pat = re.compile(card["pattern"])
    hits: list[str] = []
    for f in _iter_files(card.get("paths") or [], card.get("exclude_globs")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if not pat.search(line):
                continue
            if card.get("skip_if_forbid_nearby") and _line_is_forbid(line):
                continue
            hits.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:160]}")
            if len(hits) >= 5:
                return hits
    return hits


def probe_grep_absent_or_archive(card: dict[str, Any]) -> list[str]:
    return probe_grep_absent(card)


def probe_file_contains(card: dict[str, Any]) -> list[str]:
    path = ROOT / card["path"]
    if not path.is_file():
        return [f"missing file: {card['path']}"]
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [s for s in card.get("must_contain") or [] if s not in text]
    if missing:
        return [f"{card['path']} missing markers: {', '.join(missing)}"]
    return []


def probe_control_invent(card: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    if CONTROL.is_file():
        try:
            data = json.loads(CONTROL.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        policy = data.get("policy") if isinstance(data, dict) else {}
        if not isinstance(policy, dict):
            policy = {}
        hard = policy.get("invent_hard_disabled")
        mode = str(data.get("mode") or "")
        if hard is False or mode == "invent":
            hits.append(
                f"{CONTROL}: invent_hard_disabled={hard!r} mode={mode!r}"
            )
    # docs must not affirmatively teach enabling invent as current practice
    for f in _iter_files(
        ["docs/product", "STARTUP-BRIEF.md", "CLAUDE.md", ".cursor/rules"],
        ["**/archive/**"],
    ):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"(启用\s*invent|mode\s*[:=]\s*[\"']invent[\"'])", line, re.I):
                if _line_is_forbid(line) or "已退役" in line or "硬关" in line:
                    continue
                hits.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:160]}")
    return hits[:5]


def probe_no_lan_as_desktop_default(card: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    for f in _iter_files(card.get("paths") or [], card.get("exclude_globs")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # skip docs that explicitly mark LAN as non-default
        rel = f.relative_to(ROOT).as_posix()
        if rel.endswith(".md") and (
            "勿作主路径" in text or "禁止把 LAN" in text or "主路径" in text and "17777" in text
        ):
            # still scan code-like affirmative defaults in md
            pass
        for i, line in enumerate(text.splitlines(), 1):
            if "192.168.3.116:7777" not in line:
                continue
            if _line_is_forbid(line) or "勿" in line or "勿作" in line or "排障" in line:
                continue
            # 明确旁路命名：手机/内网 SPA，不是 Desktop·sidecar 默认
            if re.search(
                r"hub_base_lan|HUB_URL_LAN|DEFAULT_HUB_LAN|_LAN\b|手机|内网浏览器",
                line,
                re.I,
            ):
                continue
            if "17777" in line and ("优先" in line or "默认" in line or "主路径" in line):
                continue
            # only flag if line looks like a default assignment
            if not re.search(
                r"(default|DEFAULT|hubBase|CCC_HUB|baseURL|主路径|默认).{0,60}192\.168\.3\.116:7777|"
                r"192\.168\.3\.116:7777.{0,40}(default|默认|主路径)",
                line,
                re.I,
            ):
                # code literals used as examples in scripts are OK if labeled CCC_SERVER example
                if "CCC_SERVER=" in line or "example" in line.lower() or "例" in line:
                    continue
                if f.suffix in {".swift", ".py", ".json", ".plist"} and re.search(
                    r"[\"']http://192\.168\.3\.116:7777[\"']", line
                ):
                    # allow if same file also documents tunnel as default nearby — still flag hardcode defaults in desktop
                    if "desktop" in rel or "sidecar" in rel:
                        hits.append(f"{rel}:{i}: {line.strip()[:160]}")
                continue
            hits.append(f"{rel}:{i}: {line.strip()[:160]}")
            if len(hits) >= 5:
                return hits
    return hits


PROBES = {
    "no_affirmative_alt_ide": probe_no_affirmative_alt_ide,
    "grep_absent": probe_grep_absent,
    "grep_absent_or_archive": probe_grep_absent_or_archive,
    "file_contains": probe_file_contains,
    "control_invent_hard_disabled": probe_control_invent,
    "no_lan_as_desktop_default": probe_no_lan_as_desktop_default,
}


def run_patrol() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for card in _load_cards():
        probe = card.get("probe") or ""
        fn = PROBES.get(probe)
        if not fn:
            findings.append(
                {
                    "id": card.get("id"),
                    "title": card.get("title"),
                    "human_alert": f"未知探针类型 {probe}",
                    "evidence": [f"probe={probe}"],
                }
            )
            continue
        evidence = fn(card)
        if evidence:
            findings.append(
                {
                    "id": card.get("id"),
                    "title": card.get("title"),
                    "why": card.get("why"),
                    "human_alert": card.get("human_alert"),
                    "evidence": evidence,
                }
            )
    return findings


def _notify(findings: list[dict[str, Any]], *, dry_run: bool) -> None:
    if dry_run or not findings:
        return
    # one L3 alert summarizing first finding; full detail in alert file body via notify message
    first = findings[0]
    title = f"权威违背 · {first.get('title') or first.get('id')}"
    msg = str(first.get("human_alert") or first.get("title") or "发现权威违背，请拍板")
    if len(findings) > 1:
        msg = f"{msg}（另有 {len(findings) - 1} 条，见 ~/.ccc/alerts）"
    env = os.environ.copy()
    if not NOTIFY.is_file():
        print(f"[patrol] notify script missing: {NOTIFY}", file=sys.stderr)
        return
    # also write a consolidated human alert
    alert_dir = Path(os.environ.get("CCC_ALERT_DIR") or (Path.home() / ".ccc" / "alerts"))
    alert_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    alert_path = alert_dir / f"{ts}-L3-authority-patrol.md"
    body_lines = [
        "# 需要你拍板 · 权威巡查",
        "",
        "发现平台现状和我们定的权威不一致。下面用人话说明；你点头后再改。",
        "",
    ]
    for f in findings:
        body_lines.append(f"## {f.get('title') or f.get('id')}")
        body_lines.append("")
        body_lines.append(str(f.get("human_alert") or ""))
        body_lines.append("")
        body_lines.append("证据（给执行用）：")
        for ev in f.get("evidence") or []:
            body_lines.append(f"- `{ev}`")
        body_lines.append("")
    alert_path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    try:
        subprocess.run(
            ["bash", str(NOTIFY), "L3", title, msg[:180]],
            check=False,
            env=env,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"[patrol] notify failed: {e}", file=sys.stderr)
    print(f"[patrol] alert written: {alert_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="CCC authority patrol")
    ap.add_argument("--quiet", action="store_true", help="no notify")
    ap.add_argument("--json", action="store_true", help="print JSON findings")
    ap.add_argument("--dry-run", action="store_true", help="do not notify / write alerts")
    args = ap.parse_args()
    try:
        findings = run_patrol()
    except Exception as e:
        print(f"[patrol] error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False, indent=2))
    elif findings:
        print(f"[patrol] RED {len(findings)} finding(s)")
        for f in findings:
            print(f"- {f.get('id')}: {f.get('human_alert')}")
    else:
        print("[patrol] GREEN")

    if findings and not args.quiet:
        _notify(findings, dry_run=args.dry_run)

    return 2 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
