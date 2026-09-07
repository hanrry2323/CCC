"""reaper 日常三方对账入口（v2.0 P4.2）。

CLI 用法：
    python -m server.ops.reaper [--dispatch DIR] [--repo-root DIR]

读取 CCC 仓卡、看板 GET /cards、各业务仓 git 分支；差异追加到
``~/.ccc/logs/reaper-diffs.jsonl`` 与 audit ledger，并把当前差异快照写到
``~/.ccc/logs/reaper-active.jsonl``。任何一方不可用均 fail-closed：写一条
``reaper_source_unavailable`` 运行记录并返回非零，避免「没拉到看板」被当成一致。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.ops.board_fetch import fetch_cards
from server.ops.card_status import scan_dispatch
from server.ops.ledger_writer import record_reaper_diffs, write_active_snapshot
from server.ops.reconcile import classify_diffs

DEFAULT_LOG_DIR = Path.home() / ".ccc" / "logs"


def _read_registry_repos(repo_root: Path) -> list[Path]:
    """从 registry.yaml 的 mac2017 路径读取业务仓；解析失败只回退已知本仓。"""
    repos: list[Path] = [repo_root]
    registry = repo_root / "docs" / "projects" / "registry.yaml"
    try:
        text = registry.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return repos
    # registry 是受控 YAML；无需引入 PyYAML，仅提取 paths.mac2017 的绝对路径。
    in_paths = False
    for line in text.splitlines():
        if line.startswith("    paths:"):
            in_paths = True
            continue
        if in_paths and line.startswith("    ") and not line.startswith("      "):
            in_paths = False
        if in_paths and "mac2017:" in line:
            raw = line.split("mac2017:", 1)[1].strip().strip('"\'')
            if raw and raw != "null" and raw.startswith("/"):
                path = Path(raw).expanduser()
                if path.is_dir() and path not in repos:
                    repos.append(path)
    return repos


def _git_branches(repo: Path) -> list[dict[str, Any]]:
    """列出仓库 codex/* 分支，并独立核验是否已合入 origin/main。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "for-each-ref", "--format=%(refname:short)", "refs/heads/codex", "refs/remotes/origin/codex"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    refs: set[str] = set()
    for line in result.stdout.splitlines():
        name = line.strip()
        if name.startswith("origin/"):
            name = name[len("origin/") :]
        if name.startswith("codex/"):
            refs.add(name)
    out: list[dict[str, Any]] = []
    for name in sorted(refs):
        merged = False
        try:
            check = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", name, "origin/main"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            merged = check.returncode == 0
        except (OSError, subprocess.SubprocessError):
            # 无法核验时保持 False；分支残留仍会进入 uncleaned 检查，fail-closed。
            pass
        out.append({"branch": name, "merged": merged, "repo": str(repo)})
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(*, dispatch_dir: Path, repo_root: Path, log_dir: Path) -> tuple[int, list[dict[str, Any]]]:
    """执行一轮对账，返回 (exit_code, diff_rows)。"""
    cards = scan_dispatch(dispatch_dir)
    board = fetch_cards()
    branch_repos = _read_registry_repos(repo_root)
    branches: list[dict[str, Any]] = []
    for repo in branch_repos:
        branches.extend(_git_branches(repo))

    now = _now_iso()
    if board is None:
        unavailable = {
            "ts": now,
            "action": "reaper_source_unavailable",
            "object_id": "board",
            "source": "reaper",
            "kind": "reaper_diff",
            "code": "reaper_source_unavailable",
            "severity": "severe",
            "detail": "看板 /cards 不可达或鉴权失败；本轮不判定为一致",
        }
        _append_jsonl(log_dir / "reaper-diffs.jsonl", [unavailable])
        # 快照清空，避免上一轮黄标残留；退出码非零保留告警。
        write_active_snapshot([], log_dir / "reaper-active.jsonl")
        return 1, [unavailable]

    diffs = classify_diffs(cards, board, branches)
    # 每轮原始差异文件留证（包含时间，便于逐日审计）；ledger 同样追加。
    logged = [{"ts": now, **d} for d in diffs]
    _append_jsonl(log_dir / "reaper-diffs.jsonl", logged)
    record_reaper_diffs(diffs)
    write_active_snapshot(diffs, log_dir / "reaper-active.jsonl")
    return (1 if diffs else 0), diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CCC reaper 三方卡/看板/分支每日对账")
    parser.add_argument("--dispatch", default=None, help="dispatch 目录，默认仓内 docs/dispatch")
    parser.add_argument("--repo-root", default=None, help="CCC 仓根，默认按脚本位置推导")
    parser.add_argument("--log-dir", default=None, help="日志目录，默认 ~/.ccc/logs")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else Path(__file__).resolve().parents[2]
    dispatch_dir = Path(args.dispatch).expanduser().resolve() if args.dispatch else repo_root / "docs" / "dispatch"
    log_dir = Path(args.log_dir).expanduser().resolve() if args.log_dir else DEFAULT_LOG_DIR
    rc, diffs = run(dispatch_dir=dispatch_dir, repo_root=repo_root, log_dir=log_dir)
    print(json.dumps({"ts": _now_iso(), "cards": len(scan_dispatch(dispatch_dir)), "diffs": len(diffs), "exit": rc}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
