"""机审命中率台账（机审 v4 · 2026-08-14）。

存储：data/audit/ledger.jsonl（追加写，一行一条审计结论）。
命中判定（D3：自动推导 + 老板可标误报）：
- 审计不通过 → 修复（就地修复/修复轮）→ 最终通过 = 命中（对同一卡的既往不通过行回填 hit=True）
- 审计不通过 → 老板标「误报」 = 未命中（hit=False）
- 审计通过 → 合入后无返工 = 命中（合入时由调用方回填）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _ledger_path(dispatch_dir: str | Path | None = None) -> Path:
    """台账路径：data/audit/ledger.jsonl（相对仓库根）。"""
    if dispatch_dir:
        d = Path(dispatch_dir)
        if (d / "docs" / "dispatch").is_dir():
            return d / "data" / "audit" / "ledger.jsonl"
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "audit" / "ledger.jsonl"


def _append(record: dict[str, Any]) -> None:
    path = _ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def record_audit(
    work_id: str,
    card_id: str,
    *,
    conclusion: str,  # 通过 / 不通过 / 重试
    severity: str = "中",
    reasons: list[str] | None = None,
    fix_action: str = "",  # 就地修复 / 修复轮 / 打回 / ""
    source: str = "engine",  # engine / manual
) -> None:
    """机审结论落定时写入台账（不推导命中，命中由 hit 回填）。"""
    _append(
        {
            "ts": _now_iso(),
            "work_id": work_id,
            "card_id": card_id,
            "conclusion": conclusion,
            "severity": severity,
            "reasons": (reasons or [])[:3],
            "fix_action": fix_action,
            "hit": None,
            "source": source,
        }
    )


def mark_card_hit(card_id: str, hit: bool) -> None:
    """回填某卡的机审命中：卡最终通过（修复有效）→ hit=True；老板标误报 → hit=False。

    只回填该卡最近一条 hit 为 None 的「不通过」记录（误报标记目标）。
    """
    rows = load_ledger()
    if not rows:
        return
    for rec in reversed(rows):
        if rec.get("card_id") == card_id and rec.get("hit") is None:
            rec["hit"] = hit
            break
    _write_all(rows)


def backfill_card_hits(card_id: str) -> None:
    """卡审计通过 → 回填该卡所有 hit=None 记录为命中（既往不通过 = 修复有效 = 命中）。"""
    rows = load_ledger()
    if not rows:
        return
    changed = False
    for rec in rows:
        if rec.get("card_id") == card_id and rec.get("hit") is None:
            rec["hit"] = True
            changed = True
    if changed:
        _write_all(rows)


def load_ledger(dispatch_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """读台账全部记录（时间序）。"""
    path = _ledger_path(dispatch_dir)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return rows


def hit_rate(window: int = 50) -> dict[str, Any]:
    """近期命中率：hit 已判定的记录中，命中比例。"""
    rows = [r for r in load_ledger() if r.get("hit") is not None][-window:]
    if not rows:
        return {"total": 0, "hits": 0, "misses": 0, "hit_rate": None}
    hits = sum(1 for r in rows if r.get("hit"))
    return {
        "total": len(rows),
        "hits": hits,
        "misses": len(rows) - hits,
        "hit_rate": round(hits / len(rows), 3),
    }


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_all(rows: list[dict[str, Any]]) -> None:
    path = _ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    except OSError:
        pass
