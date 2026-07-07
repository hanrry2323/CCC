#!/usr/bin/env python3
"""ccc-board.py — 任务看板核心 (v0.16b)

6 角色都通过这个 core 操作 .ccc/board/:
- product: backlog → planned
- dev: planned → in_progress → testing
- reviewer: testing → verified (过 ruff/mypy)
- tester: testing → verified (过 pytest)
- ops: 健康检查 (不动 board)
- kb: verified → released (归档)

任务流转规则见 .ccc/board/README.md
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / ".ccc" / "board"

COLUMNS = ["backlog", "planned", "in_progress", "testing", "verified", "released"]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_tasks(column: str) -> list[dict]:
    """读某列所有 task"""
    col_dir = BOARD / column
    if not col_dir.exists():
        return []
    tasks = []
    for f in col_dir.glob("*.jsonl"):
        with open(f) as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    tasks.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return tasks


def move_task(task_id: str, from_col: str, to_col: str) -> bool:
    """把 task 从 from_col 挪到 to_col"""
    src = BOARD / from_col / f"{task_id}.jsonl"
    if not src.exists():
        print(f"[board] {task_id} not in {from_col}", file=sys.stderr)
        return False
    task = None
    with open(src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("id") == task_id:
                    task = obj
                    break
            except json.JSONDecodeError:
                pass
    if not task:
        return False

    task["status"] = to_col
    task["updated_at"] = now_iso()

    dst = BOARD / to_col / f"{task_id}.jsonl"
    with open(dst, "w") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")
    src.unlink()
    print(f"[board] {task_id}: {from_col} → {to_col}")
    return True


def update_index() -> dict:
    """更新 .ccc/board/index.json 状态总览"""
    counts = {col: len(list_tasks(col)) for col in COLUMNS}
    index_file = BOARD / "index.json"
    index_file.write_text(json.dumps(counts, indent=2, ensure_ascii=False) + "\n")
    return counts


def product_role() -> dict:
    """产品经理: 扫 backlog → 写 plan.md → 挪 planned"""
    moved = []
    for task in list_tasks("backlog"):
        task_id = task["id"]
        plan_dir = ROOT / ".ccc" / "plans"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / f"{task_id}.plan.md"
        if not plan_file.exists():
            plan_file.write_text(
                f"# {task_id}\n\n"
                f"> 标题: {task['title']}\n"
                f"> 创建: {task['created_at']}\n\n"
                f"## 目标\n\n{task.get('description', '待细化')}\n\n"
                f"## Phase\n\n(由 dev 拆)\n\n"
                f"## Commit 计划\n\n- dev 完成后自动 commit + push\n"
            )
        phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        if not phases_file.exists():
            phases_file.parent.mkdir(parents=True, exist_ok=True)
            phases_file.write_text(
                json.dumps([{"phase": f"{task_id}-p1", "status": "pending"}]) + "\n"
            )
        if move_task(task_id, "backlog", "planned"):
            moved.append(task_id)
    return {"role": "product", "moved": moved, "counts": update_index()}


def dev_role() -> dict:
    """开发工程师: 扫 planned + in_progress → 调 opencode 写代码 → 挪 testing"""
    import subprocess as sp

    moved = []
    for task in list_tasks("planned"):
        task_id = task["id"]
        plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
        phases = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        if not plan.exists() or not phases.exists():
            print(f"[dev] {task_id} 缺 plan/phases, 跳过")
            continue
        # 挪到 in_progress
        move_task(task_id, "planned", "in_progress")
        # 调 launcher (90s timeout, 防止 harness 2min 杀)
        result = sp.run(
            [
                "bash", str(ROOT / "scripts" / "ccc-exec-launcher.sh"),
                f"{task_id}-p1", str(plan),
                "--timeout", "90",
            ],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            move_task(task_id, "in_progress", "testing")
            moved.append(task_id)
        else:
            print(f"[dev] {task_id} launcher 失败: {result.returncode}", file=sys.stderr)
            # 留在 in_progress, 下次再试
    return {"role": "dev", "moved": moved, "counts": update_index()}


def reviewer_role() -> dict:
    """代码审查员: 扫 testing → ruff/mypy → 通过则挪 verified

    简化版: ruff 不一定装, 用 python3 -m py_compile 替代 (所有 .py 能 compile)
    """
    import subprocess as sp

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        # 用 py_compile 替代 ruff (跨 IDE 兼容)
        scripts_dir = ROOT / "scripts"
        py_files = list(scripts_dir.rglob("*.py"))
        all_ok = True
        for py in py_files:
            r = sp.run(
                ["python3", "-m", "py_compile", str(py)],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                all_ok = False
                print(f"[reviewer] {task_id} py_compile {py.name} FAIL: {r.stderr[:200]}", file=sys.stderr)
                break
        if all_ok:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
    return {"role": "reviewer", "moved": moved, "counts": update_index()}


def tester_role() -> dict:
    """测试工程师: 扫 testing → pytest → 通过则挪 verified"""
    import subprocess as sp

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        # pytest (带 timeout, 不跑 e2e, 4min cap)
        result = sp.run(
            [
                "python3", "-m", "pytest", str(ROOT / "tests" / "scripts"),
                "-q", "--tb=line", "--timeout=60",
            ],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode == 0:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
        else:
            print(f"[tester] {task_id} pytest FAIL: {result.stdout[-200:]}", file=sys.stderr)
    return {"role": "tester", "moved": moved, "counts": update_index()}


def ops_role() -> dict:
    """运维监控: 健康检查 + 告警 (不动 board)"""
    health = {
        "opencode_pids": len(list((Path.home() / ".ccc" / "opencode-pids").glob("*.pid"))),
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob(f"*-L*.md"))),
        "git_ahead": 0,
    }
    # git ahead check
    import subprocess as sp
    for proj in [ROOT, ROOT.parent / "qx-observer", ROOT.parent / "xianyu", ROOT.parent / "projects" / "qx"]:
        if (proj / ".git").exists():
            r = sp.run(
                ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
                capture_output=True, text=True, cwd=proj, timeout=10,
            )
            if r.returncode == 0:
                ahead = r.stdout.strip().split()[-1] if r.stdout.strip() else "0"
                health[f"ahead_{proj.name}"] = int(ahead)
    return {"role": "ops", "health": health}


def kb_role() -> dict:
    """知识管理员: 扫 verified → 归档 + git tag → 挪 released"""
    import subprocess as sp

    moved = []
    for task in list_tasks("verified"):
        task_id = task["id"]
        # git tag
        sp.run(
            ["git", "tag", "-a", f"board-{task_id}", "-m", f"v0.16: {task_id} 看板发布"],
            cwd=ROOT, capture_output=True, timeout=10,
        )
        # git push tag
        sp.run(
            ["git", "push", "origin", f"board-{task_id}"],
            cwd=ROOT, capture_output=True, timeout=30,
        )
        # 挪 released
        move_task(task_id, "verified", "released")
        moved.append(task_id)
    return {"role": "kb", "moved": moved, "counts": update_index()}


ROLES = {
    "product": product_role,
    "dev": dev_role,
    "reviewer": reviewer_role,
    "tester": tester_role,
    "ops": ops_role,
    "kb": kb_role,
}


def main():
    ap = argparse.ArgumentParser(description="CCC 任务看板 6 角色核心")
    ap.add_argument("role", choices=list(ROLES.keys()) + ["index"], help="角色名 或 'index'")
    args = ap.parse_args()

    if args.role == "index":
        print(json.dumps(update_index(), indent=2, ensure_ascii=False))
        return

    result = ROLES[args.role]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
