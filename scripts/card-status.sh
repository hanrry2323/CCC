#!/usr/bin/env bash
# ── scripts/card-status.sh ──
# 卡执行一页视图（只读）：逐卡输出认领/执行/结果/门禁摘要。
# 数据源：dispatch 卡文件、~/.ccc/logs/exec/runtime sidecar + worker-events.jsonl。
# 用法：scripts/card-status.sh [卡号]（不传则输出所有卡）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${EXECUTOR_LOG_DIR:-$HOME/.ccc/logs/exec}"
CARD_ID="${1:-}"
export ROOT LOG_DIR CARD_ID
exec python3 - <<'PY'
import json
import os
import re
from pathlib import Path

root = Path(os.environ["ROOT"])
log_dir = Path(os.environ["LOG_DIR"])
filter_id = os.environ.get("CARD_ID", "")

runtime = {}
state_file = log_dir / "state" / "cards.jsonl"
if state_file.is_file():
    for line in state_file.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("id"):
            runtime.setdefault(str(rec["id"]), {}).update(rec)

events = {}
events_file = log_dir / "worker-events.jsonl"
if events_file.is_file():
    for line in events_file.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        wid = str(rec.get("work_id") or "")
        if not wid:
            continue
        current = events.setdefault(wid, {})
        current.update(rec)

# Session probe events are separate from worker completion events.
sessions = {}
for line in events_file.read_text(encoding="utf-8", errors="replace").splitlines() if events_file.is_file() else []:
    try:
        rec = json.loads(line)
    except ValueError:
        continue
    if rec.get("kind") == "session" and rec.get("work_id"):
        sessions[str(rec["work_id"])] = rec


def session_path_for(card_id: str) -> str:
    """Best-effort DSH session directory lookup without reading session contents."""
    base = Path.home() / ".dsh" / "sessions"
    if not base.is_dir():
        return "-"
    matches = sorted(base.glob(f"*{card_id}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else "-"


def tool_call_count(card_id: str) -> int | str:
    """Count tool-call records in the latest compressed DSH session."""
    session_dir = session_path_for(card_id)
    if session_dir == "-":
        return "-"
    files = sorted(Path(session_dir).glob("*/session.jsonl.zstd"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "-"
    try:
        import subprocess
        raw = subprocess.run(["zstd", "-d", "-c", str(files[0])], capture_output=True, check=False, timeout=10).stdout
        text = raw.decode("utf-8", errors="replace")
        return sum(1 for line in text.splitlines() if '"toolCall"' in line or '"tool_call"' in line)
    except (OSError, subprocess.SubprocessError):
        return "-"

cards = []
for path in sorted((root / "docs" / "dispatch").glob("*/*.md")):
    match = re.match(r"([a-z]{2,4}[0-9]{3,4})-", path.name)
    if not match:
        continue
    card_id = match.group(1)
    if filter_id and card_id != filter_id:
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    state_match = re.search(r"状态：([^ ·\n]+)", text)
    state = state_match.group(1) if state_match else "未知"
    result = log_dir / f"{card_id}-ccc-result.md"
    event = events.get(card_id, {})
    rec = runtime.get(card_id, {})
    started = event.get("ts") or rec.get("ts") or "-"
    session = session_path_for(card_id)
    calls = tool_call_count(card_id)
    if result.is_file():
        result_state = "已产出"
    else:
        result_state = "无结果"
    gate = event.get("exit_kind") or ("已回写" if state == "已回写" else "-")
    print(f"{card_id}\tstate={state}\tclaimed={started}\tsession={session}\ttool_calls={calls}\tresult={result_state}\tgate={gate}")
PY
