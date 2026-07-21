#!/usr/bin/env python3
"""
CCC Board Reconcile — 清理 zombie 副本。

权威来源（按优先级）：
  1. jsonl["status"] 字段 — 自报所在列
  2. jsonl 物理位置 — 兜底（status 缺失时用）

清理规则：
  - 同 task_id 在多列存在 → 保留 status 字段与目录一致的副本，删其它 zombie
  - jsonl["status"] 与所在目录不一致 → 修正 status 字段（不挪文件，物理位置是兜底）

事件日志 events/ 只是审计，不作为权威（避免事件缺失或历史回退时误判）。
"""
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

from _config import get_logger
from _board_store import COLUMNS, _atomic_write, pick_canonical_column

_log = get_logger("board-reconcile")


def _choose_canonical(tid: str, cols: list[str], status_map: dict) -> str:
    """多副本权威列：abnormal 优先；否则在 status 自洽副本中取最远列。"""
    if "abnormal" in cols:
        return "abnormal"
    matching = [c for c in cols if status_map.get(tid, {}).get(c) == c]
    if matching:
        return pick_canonical_column(matching) or matching[0]
    return pick_canonical_column(cols) or cols[0]


def _is_schema_metadata(obj: object) -> bool:
    """元数据行检测：仅含 schema_version 无 status（v0.26+ 引入）"""
    return (
        isinstance(obj, dict)
        and "schema_version" in obj
        and "status" not in obj
    )


def load_status(path: Path) -> str | None:
    """从 jsonl 末行读 status 字段。跳过 schema_version 元数据行。失败返回 None。"""
    try:
        with open(path) as f:
            status = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _is_schema_metadata(obj):
                    continue
                if isinstance(obj, dict):
                    status = obj.get("status")
            return status
    except (OSError, json.JSONDecodeError):
        return None


def fix_status_field(path: Path, expected_col: str) -> bool:
    """修 jsonl 里 status 字段，使其与目录一致。返回是否修改。

    v0.26.1: 使用 _atomic_write 防崩溃时 JSONL 损坏；跳过 schema_version 元数据行。
    """
    try:
        with open(path) as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
    except OSError:
        return False
    if not lines:
        return False
    changed = False
    new_lines = []
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            new_lines.append(line)
            continue
        if not isinstance(obj, dict):
            new_lines.append(line)
            continue
        if _is_schema_metadata(obj):
            # 元数据行：保持原样，不污染 status 字段
            new_lines.append(json.dumps(obj, ensure_ascii=False))
            continue
        if obj.get("status") != expected_col:
            obj["status"] = expected_col
            changed = True
        new_lines.append(json.dumps(obj, ensure_ascii=False))
    if changed:
        _atomic_write(path, "\n".join(new_lines) + "\n")
    return changed


def reconcile(board: Path, dry_run: bool = True) -> int:
    # 1. 收集所有 task 出现位置
    presence: dict[str, list[str]] = defaultdict(list)
    status_map: dict[str, dict[str, str | None]] = defaultdict(dict)
    for col in COLUMNS:
        col_dir = board / col
        if not col_dir.is_dir():
            continue
        for jsonl in col_dir.glob("*.jsonl"):
            tid = jsonl.stem
            presence[tid].append(col)
            status_map[tid][col] = load_status(jsonl)

    # 2. 检测 zombie（同 task 多列副本）
    zombies = [(tid, cols) for tid, cols in presence.items() if len(cols) > 1]
    # 3. 检测 status 字段不一致
    mismatches: list[tuple[str, str, str]] = []
    for tid, cols in presence.items():
        for col in cols:
            s = status_map[tid].get(col)
            if s and s != col:
                mismatches.append((tid, col, s))

    if not zombies and not mismatches:
        print("[reconcile] 看板状态一致 ✓")
        return 0

    if zombies:
        print(f"[reconcile] 发现 {len(zombies)} 个多副本 task：")
        for tid, cols in sorted(zombies):
            # status 自洽副本中取流水线最远；abnormal 优先（见 _choose_canonical）
            canonical = _choose_canonical(tid, cols, status_map)
            to_delete = [c for c in cols if c != canonical]
            print(f"  {tid}: 保留={canonical}  删除={to_delete}")

    if mismatches:
        print(f"[reconcile] 发现 {len(mismatches)} 个 status 字段不一致：")
        for tid, col, declared in mismatches[:20]:
            print(f"  {tid}: 目录={col}  status={declared}  →  改 status={col}")
        if len(mismatches) > 20:
            print(f"  ... 还有 {len(mismatches) - 20} 个")

    if dry_run:
        return len(zombies) + len(mismatches)

    # 实际执行
    deleted = 0
    fixed = 0

    # 删 zombie（保留 canonical）
    for tid, cols in zombies:
        canonical = _choose_canonical(tid, cols, status_map)
        for c in cols:
            if c == canonical:
                continue
            zombie_path = board / c / f"{tid}.jsonl"
            try:
                zombie_path.unlink()
                deleted += 1
                print(f"  [deleted] {c}/{tid}.jsonl")
            except OSError as e:
                print(f"  [ERROR] {c}/{tid}: {e}", file=sys.stderr)

    # 修 status 字段
    for tid, col, declared in mismatches:
        path = board / col / f"{tid}.jsonl"
        if fix_status_field(path, col):
            fixed += 1
            print(f"  [fixed] {col}/{tid}.jsonl: status {declared} → {col}")

    print(f"[reconcile] 完成：删 {deleted} 个 zombie，修 {fixed} 个 status 字段")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="项目根（包含 .ccc/board/）")
    ap.add_argument("--apply", action="store_true", help="实际执行清理（默认 dry-run）")
    args = ap.parse_args()

    workspace = Path(args.workspace).resolve()
    board = workspace / ".ccc" / "board"
    if not board.is_dir():
        print(f"[reconcile] 看板目录不存在: {board}", file=sys.stderr)
        return 2

    return reconcile(board, dry_run=not args.apply)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
