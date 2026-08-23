#!/usr/bin/env python3
"""CCC L1 机械质量分（S5 · 增量不可劣化门禁）。

对一次合入分支（codex/<card>）计算增量质量指标，与存量基线对比，出质量分并进 ledger。

指标（对分支 diff 相对 main 的新增/改动代码）：
1. 圈复杂度 delta（radon avg of changed files）
2. mypy 类型错误 delta（changed .py 文件，--follow-imports=skip）
3. 测试断言密度（changed test 文件的 assert/test 比）

（第 4 维「重复代码信号」为早期规划，未实现——2026-08-23 P2-j 文档修正，勿按 4 维断言。）

基线（2026-08-22 全 server 扫描）：复杂度 A(4.96)、mypy 273/47文件、断言/测试 2.3。
门禁：增量不可劣化——复杂度/mypy 不劣于基线，断言密度不低于基线。

用法：
    python3 scripts/quality-score.py <repo_root> <branch> [--record]
    --record 把质量分记入 audit_ledger（action=quality_score）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 基线（2026-08-22 扫描 server/ 47 文件 23919 行）
BASELINE = {
    "complexity_avg": 4.96,     # radon 平均圈复杂度（A）
    "mypy_errors_per_file": 273 / 47,  # 5.8 错/文件
    "assert_per_test": 2.3,     # 断言/测试
}


def _run(cmd: list[str], cwd: Path) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(cwd))
        return r.stdout
    except Exception:
        return ""


def changed_files(repo: Path, branch: str) -> list[str]:
    out = _run(["git", "diff", "--name-only", f"origin/main...origin/{branch}"], repo)
    return [f for f in out.splitlines() if f.strip()]


def complexity_of(files: list[str], repo: Path) -> float | None:
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return None
    try:
        import radon.complexity as rc

        total_cc, total_fns = 0.0, 0
        for f in py:
            p = repo / f
            if not p.is_file():
                continue
            src = p.read_text(encoding="utf-8", errors="replace")
            blocks = rc.cc_visit(src)
            for b in blocks:
                total_cc += b.complexity
                total_fns += 1
        return total_cc / total_fns if total_fns else None
    except Exception:
        return None


def mypy_errors(files: list[str], repo: Path) -> int:
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return 0
    out = _run(["python3", "-m", "mypy", "--follow-imports=skip", *py], repo)
    m = re.search(r"Found (\d+) errors", out)
    return int(m.group(1)) if m else 0


def assert_density(files: list[str], repo: Path) -> float | None:
    tests = [f for f in files if f.endswith(".py") and ("test" in f or "tests" in f)]
    if not tests:
        return None
    total_asserts, total_tests = 0, 0
    for f in tests:
        p = repo / f
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        total_asserts += txt.count("assert ")
        total_tests += txt.count("def test_")
    return total_asserts / total_tests if total_tests else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo_root")
    ap.add_argument("branch")
    ap.add_argument("--record", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    files = changed_files(repo, args.branch)
    score = {
        "branch": args.branch,
        "changed_files": len(files),
        "complexity_avg": complexity_of(files, repo),
        "mypy_errors": mypy_errors(files, repo),
        "assert_per_test": assert_density(files, repo),
    }

    # 增量不可劣化判定
    degraded = []
    if score["complexity_avg"] is not None and score["complexity_avg"] > BASELINE["complexity_avg"]:
        degraded.append(f"复杂度 {score['complexity_avg']:.2f} > 基线 {BASELINE['complexity_avg']}")
    if score["mypy_errors"] > 0 and score["mypy_errors"] / max(len(files), 1) > BASELINE["mypy_errors_per_file"]:
        degraded.append(f"mypy {score['mypy_errors']} 错/改动文件数超基线")
    if score["assert_per_test"] is not None and score["assert_per_test"] < BASELINE["assert_per_test"]:
        degraded.append(f"断言/测试 {score['assert_per_test']:.2f} < 基线 {BASELINE['assert_per_test']}")
    score["degraded"] = degraded
    score["pass"] = not degraded

    print(json.dumps(score, ensure_ascii=False, indent=2))

    if args.record:
        try:
            sys.path.insert(0, str(repo))
            from server.board.audit_ledger import record_action

            record_action("quality_score", args.branch, source="quality-score",
                          detail=json.dumps(score, ensure_ascii=False))
            print("[ok] 质量分已记入 ledger")
        except Exception as e:
            print(f"[warn] ledger 记录失败: {e}", file=sys.stderr)
    return 0 if score["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
