"""机审命中率台账（机审 v4 · 2026-08-14 · 重度复审后口径修正）。

存储：data/audit/ledger.jsonl（追加写，一行一条审计结论；读改写带 fcntl 锁 + 原子 tmp+rename）。

命中判定（D3 修正口径，2026-08-14 重度复审）：
- 「不通过（审计）」行：hit=None，待「修复→最终通过」回填命中（backfill 只标不通过行，不碰通过行）。
- 「通过」行：hit=None，待「合入后无返工」才标命中（mark_card_pass_hit）；合入后返工 → miss。
- 「机审执行失败（基建）」行：kind="infra"，不参与命中回填（基建故障 ≠ 审计命中）。
- 老板标误报：把最近一条「不通过」审计行标为未命中（mark_card_hit False）。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _ledger_path(dispatch_dir: str | Path | None = None) -> Path:
    """台账路径：data/audit/ledger.jsonl（相对仓库根）。

    CCC_AUDIT_LEDGER 环境变量可覆盖（测试隔离用，避免污染生产 ledger）。
    """
    env = os.environ.get("CCC_AUDIT_LEDGER", "").strip()
    if env:
        return Path(env)
    if dispatch_dir:
        d = Path(dispatch_dir)
        if (d / "docs" / "dispatch").is_dir():
            return d / "data" / "audit" / "ledger.jsonl"
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "audit" / "ledger.jsonl"


def _acquire_lock(path: Path):
    """台账写锁（fcntl 文件锁；无 fcntl 退化为无锁）。返回句柄或 None。"""
    try:
        import fcntl

        lock_path = path.with_name(path.name + ".lock")
        f = open(lock_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX)
        return f
    except (ImportError, OSError):
        return None


def _release_lock(lock_f) -> None:
    if lock_f is None:
        return
    try:
        import fcntl

        fcntl.flock(lock_f, fcntl.LOCK_UN)
    finally:
        lock_f.close()


def _atomic_write(path: Path, rows: list[dict[str, Any]]) -> None:
    """原子改写：tmp + rename（防并发读改写竞态）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="ledger.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def record_audit(
    work_id: str,
    card_id: str,
    *,
    conclusion: str,  # 通过 / 不通过 / 重试
    severity: str = "中",
    reasons: list[str] | None = None,
    fix_action: str = "",  # 就地修复 / 修复轮 / 打回 / ""
    source: str = "engine",  # engine / manual
    kind: str = "audit",  # audit / infra（基建失败不参与命中）
) -> None:
    """机审结论落定追加写入（append，带锁）。命中由回填函数设置。"""
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
            "kind": kind,
        }
    )


def _append(record: dict[str, Any]) -> None:
    path = _ledger_path()
    lock = _acquire_lock(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    finally:
        _release_lock(lock)


def _read_write_rows(mutate) -> bool:
    """带锁读全文件 → mutate → 原子改写。返回是否发生写。"""
    path = _ledger_path()
    if not path.is_file():
        return False
    lock = _acquire_lock(path)
    try:
        rows = _read_rows(path)
        changed = mutate(rows)
        if changed:
            _atomic_write(path, rows)
        return changed
    finally:
        _release_lock(lock)


def _read_rows(path: Path) -> list[dict[str, Any]]:
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


def load_ledger(dispatch_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """读台账全部记录（时间序）。"""
    path = _ledger_path(dispatch_dir)
    return _read_rows(path)


def mark_card_hit(card_id: str, hit: bool) -> bool:
    """老板标误报：把该卡最近一条「不通过·审计」未判定行标为未命中（hit=False）。

    Returns:
        True 找到并回填；False 无匹配记录（调用方可报错，P2-E 修复）。
    """

    def _mut(rows: list[dict[str, Any]]) -> bool:
        for rec in reversed(rows):
            if (
                rec.get("card_id") == card_id
                and rec.get("conclusion") == "不通过"
                and rec.get("kind") != "infra"
                and rec.get("hit") is None
            ):
                rec["hit"] = hit
                return True
        return False

    return _read_write_rows(_mut)


def backfill_card_hits(card_id: str) -> None:
    """修复后最终通过 → 回填该卡所有「不通过·审计」未判定行为命中（只标不通过行，不碰通过行）。"""

    def _mut(rows: list[dict[str, Any]]) -> bool:
        changed = False
        for rec in rows:
            if (
                rec.get("card_id") == card_id
                and rec.get("conclusion") == "不通过"
                and rec.get("kind") != "infra"
                and rec.get("hit") is None
            ):
                rec["hit"] = True
                changed = True
        return changed

    _read_write_rows(_mut)


def mark_card_pass_hit(card_id: str) -> None:
    """合入后无返工 → 该卡最近「通过」行标命中。"""

    def _mut(rows: list[dict[str, Any]]) -> bool:
        for rec in reversed(rows):
            if (
                rec.get("card_id") == card_id
                and rec.get("conclusion") == "通过"
                and rec.get("hit") is None
            ):
                rec["hit"] = True
                return True
        return False

    _read_write_rows(_mut)


def mark_card_pass_miss(card_id: str) -> None:
    """合入后返工 → 该卡最近「通过」行标未命中。"""

    def _mut(rows: list[dict[str, Any]]) -> bool:
        for rec in reversed(rows):
            if (
                rec.get("card_id") == card_id
                and rec.get("conclusion") == "通过"
                and rec.get("hit") is None
            ):
                rec["hit"] = False
                return True
        return False

    _read_write_rows(_mut)


def hit_rate(window: int = 50) -> dict[str, Any]:
    """近期命中率：hit 已判定的审计记录（不含 infra）中，命中比例。"""
    rows = [
        r
        for r in load_ledger()
        if r.get("kind") != "infra" and r.get("hit") is not None
    ][-window:]
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


# ── 批准真值账本（033 阶段 2 M6 · 2026-08-16）────────────────────────
# 三大人审节点的「老板确认/拍板/合入」由自证盖章升级为账本证据链：
# 每次动作追加写（不可改），校验时查 ledger 而非只信卡/方案文本。

# 批准/流转动作类型
ACTION_TYPES = ("confirm_plan", "convert", "approve_merge", "accept", "machine_audit_pass")


def record_action(action: str, object_id: str, source: str = "", detail: str = "") -> None:
    """记录批准/流转动作（追加写、只增不改——批准真值账本）。

    Args:
        action: confirm_plan（方案确认）/ convert（转卡）/ approve_merge（合入）/
                accept（验收拍板）/ machine_audit_pass（机审通过）
        object_id: 方案 plan_id 或卡 ID
        source: 调用方（engine / approve-merge / ccc-api / tool）
        detail: 附加信息（如被审 commit、卡 IDs）
    """
    _append(
        {
            "ts": _now_iso(),
            "action": action,
            "object_id": object_id,
            "source": source,
            "detail": detail,
            "kind": "approval",
        }
    )


def has_action(action: str, object_id: str, source: str = "") -> bool:
    """查 ledger 是否有对应批准/流转动作记录。

    source 非空时精确匹配来源；为空只按 action+object_id 匹配。
    """
    rows = load_ledger()
    for r in rows:
        if r.get("action") != action or r.get("object_id") != object_id:
            continue
        if source and r.get("source") != source:
            continue
        return True
    return False


# ── 机审真值单源化（P0-3 · 2026-08-22）────────────────────────
# machine_audit_passed 的单一事实源 = 账本 machine_audit_pass 记录（engine 落盘，执行体不可自写）。
# 按 ledger 文件 mtime+size 缓存 pass-id 集合，写后自动失效（record_action/record_audit/回填均追加或改写）。
_pass_ids_cache: dict[str, object] = {"key": None, "ids": None}


def _machine_audit_pass_ids() -> set[str]:
    """已有机审通过记录的卡 ID 集合（path+mtime+size 缓存，env 切换路径自动失效）。"""
    path = _ledger_path()
    try:
        st = path.stat()
    except OSError:
        return set()
    key = (str(path.resolve()), st.st_mtime, st.st_size)
    if _pass_ids_cache["key"] == key and _pass_ids_cache["ids"] is not None:
        return _pass_ids_cache["ids"]  # type: ignore[return-value]
    ids: set[str] = set()
    for r in _read_rows(path):
        if r.get("action") == "machine_audit_pass" and r.get("object_id"):
            ids.add(str(r["object_id"]))
    _pass_ids_cache["key"] = key
    _pass_ids_cache["ids"] = ids
    return ids


def has_pass(card_id: str) -> bool:
    """机审通过真值：查账本是否有该卡 machine_audit_pass 记录（单一事实源）。"""
    return card_id in _machine_audit_pass_ids()
