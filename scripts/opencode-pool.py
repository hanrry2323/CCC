#!/usr/bin/env python3
"""opencode-pool.py — OpenCode 进程池（max 3 并发）

职责：用 asyncio.Semaphore 限制 opencode exec 并发数 ≤ 3。
      防止多 phase 同时跑导致 opencode 进程占满资源（红线 X1）。

用法：
  python3 opencode-pool.py <tasks.json>

  tasks.json 格式:
  [
    {"phase_id": "p1", "prompt_file": "/tmp/p1.txt", "timeout": 1800},
    {"phase_id": "p2", "prompt_file": "/tmp/p2.txt", "timeout": 600}
  ]

输出：每个 task 一行 JSON（来自 opencode-exec.py），最后输出汇总。

红线 X1: MAX_PARALLEL = 3（硬约束，不允许超）
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

MAX_PARALLEL = 3  # 红线 X1

# 复用 opencode-exec.py 的 run_opencode（避免重复代码）
sys.path.insert(0, str(Path(__file__).parent))
from opencode_exec import run_opencode  # type: ignore  # noqa: E402


async def run_task(task: dict, sem: asyncio.Semaphore) -> dict:
    """单 task：拿信号量 → 跑 opencode → 释放"""
    async with sem:
        return await run_opencode(
            phase_id=task["phase_id"],
            prompt_text=Path(task["prompt_file"]).read_text(encoding="utf-8"),
            timeout=task.get("timeout", 1800),
            cwd=task.get("cwd"),
        )


async def main() -> int:
    ap = argparse.ArgumentParser(description=f"OpenCode 进程池（max {MAX_PARALLEL} 并发）")
    ap.add_argument("tasks_file", help="tasks JSON 列表文件")
    ap.add_argument("--max-parallel", type=int, default=MAX_PARALLEL, help=f"并发上限（默认 {MAX_PARALLEL}）")
    args = ap.parse_args()

    if args.max_parallel > MAX_PARALLEL:
        print(
            f"[opencode-pool] 拒绝：max_parallel={args.max_parallel} > 红线 X1 上限 {MAX_PARALLEL}",
            file=sys.stderr,
        )
        return 1

    tasks_path = Path(args.tasks_file)
    if not tasks_path.exists():
        print(f"[opencode-pool] tasks 文件不存在: {tasks_path}", file=sys.stderr)
        return 2

    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list) or not tasks:
        print("[opencode-pool] tasks 必须是非空 list", file=sys.stderr)
        return 3

    sem = asyncio.Semaphore(args.max_parallel)
    results = await asyncio.gather(
        *(run_task(t, sem) for t in tasks),
        return_exceptions=True,
    )

    # 每行输出一个 task 结果
    ok_count = 0
    fail_count = 0
    for r in results:
        if isinstance(r, Exception):
            fail_count += 1
            print(json.dumps({"error": str(r)}, ensure_ascii=False))
        else:
            print(json.dumps(r, ensure_ascii=False))
            if r.get("exit_code") == 0 and not r.get("killed"):
                ok_count += 1
            else:
                fail_count += 1

    # 汇总行（prefix 便于 grep）
    print(f"[opencode-pool] total={len(results)} ok={ok_count} fail={fail_count} max_parallel={args.max_parallel}")
    return 0 if fail_count == 0 else 4


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
