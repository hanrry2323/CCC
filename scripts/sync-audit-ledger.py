#!/usr/bin/env python3
"""双机机审台账同步（P0-3 单源化前置 · 2026-08-22）。

⚠️ **2026-08-22 废弃（S1 单机化）**：CCC 收缩到 2017 单机后，机审与合入都在 2017 同一 ledger，
双机分裂问题消失，本脚本不再需要（approve-merge 在 2017 跑时读本地 ledger 即权威）。
保留仅作历史/双机过渡期兜底；S1 完成后从 approve-merge 移除调用。

问题：机审在 2017（engine 执行体）落 2017 ledger，approve-merge 在 M1 读 M1 ledger，
两机各自 append-only → 分裂（实测 M1 500 条 machine_audit_pass vs 2017 970 条）。
approve-merge 在 M1 按 M1 ledger 判 provenance，会误拒已在 2017 真机审过的卡。

方向：2017 = 权威（机审在 2017 执行），单向 2017 → M1 合并（幂等去重，append-only 安全）。
用法：scripts/sync-audit-ledger.py [--dry-run] [--ssh-host fan@192.168.3.116]
       [--prod-repo /Users/fan/program/CCC]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def read_ledger(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def write_ledger(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".sync.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def fetch_2017_ledger(ssh_host: str, prod_repo: str) -> list[dict]:
    """SSH cat 2017 ledger 到 stdout 解析（避免 scp 临时文件残留）。"""
    cmd = f"cat {prod_repo}/data/audit/ledger.jsonl"
    try:
        out = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", ssh_host, cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise SystemExit(f"[ERROR] SSH 读取 2017 ledger 失败: {exc}")
    if out.returncode != 0:
        raise SystemExit(f"[ERROR] SSH 读取 2017 ledger 失败 (rc={out.returncode}): {out.stderr.strip()[:200]}")
    rows = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def merge_dedupe(m1_rows: list[dict], prod_rows: list[dict]) -> tuple[list[dict], int]:
    """按整条 JSON 记录去重合并：2017 权威行追加到 M1 尾部，幂等。"""
    # 记录键：规范化 JSON（保序），相同记录只保留一份
    seen = {json.dumps(r, ensure_ascii=False, sort_keys=True) for r in m1_rows}
    merged = list(m1_rows)
    added = 0
    for r in prod_rows:
        key = json.dumps(r, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            merged.append(r)
            seen.add(key)
            added += 1
    return merged, added


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 2017 机审台账到本机")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写盘")
    parser.add_argument("--ssh-host", default="fan@192.168.3.116")
    parser.add_argument("--prod-repo", default="/Users/fan/program/CCC")
    parser.add_argument(
        "--ledger-path",
        default=None,
        help="本机 ledger 路径（默认 data/audit/ledger.jsonl，相对本脚本目录）",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    ledger_path = Path(args.ledger_path) if args.ledger_path else repo_root / "data" / "audit" / "ledger.jsonl"

    m1_rows = read_ledger(ledger_path)
    print(f"[M1 ] ledger: {ledger_path} · {len(m1_rows)} 条")
    prod_rows = fetch_2017_ledger(args.ssh_host, args.prod_repo)
    print(f"[2017] ledger: {len(prod_rows)} 条")

    merged, added = merge_dedupe(m1_rows, prod_rows)
    print(f"合并结果：新增 {added} 条（去重后 M1 共 {len(merged)} 条）")

    if args.dry_run:
        print("[DRY-RUN] 未写盘")
        return 0
    if added:
        write_ledger(ledger_path, merged)
        print(f"[OK] 已写盘 {ledger_path}（+{added} 条）")
    else:
        print("[OK] 无新增，已一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
