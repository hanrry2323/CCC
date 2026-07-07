#!/usr/bin/env python3
"""ccc-board.py — 任务看板核心 (v0.18)

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
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = (
    Path(os.environ.get("CCC_WORKSPACE", ""))
    if os.environ.get("CCC_WORKSPACE")
    else Path(__file__).resolve().parent.parent
)
BOARD = ROOT / ".ccc" / "board"
EVENTS_DIR = BOARD / "events"

COLUMNS = ["backlog", "planned", "in_progress", "testing", "verified", "released"]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record_event(task_id: str, from_col: str, to_col: str) -> None:
    """追加 timeline event 到 .ccc/board/events/<task_id>.events.jsonl"""
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "move",
        "task_id": task_id,
        "from": from_col,
        "to": to_col,
        "timestamp": now_iso(),
    }
    event_file = EVENTS_DIR / f"{task_id}.events.jsonl"
    with open(event_file, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _task_id_exists(task_id: str) -> bool:
    """检查 task_id 是否在任意列中已存在"""
    for col in COLUMNS:
        col_dir = BOARD / col
        if (col_dir / f"{task_id}.jsonl").exists():
            return True
    return False


def create_task(data: dict, column: str = "backlog") -> bool:
    """创建新 task（含 id 唯一性校验）"""
    task_id = data.get("id", "")
    if not task_id:
        print("[board] create_task: missing 'id'", file=sys.stderr)
        return False
    if _task_id_exists(task_id):
        print(f"[board] create_task: duplicate id '{task_id}'", file=sys.stderr)
        return False
    if column not in COLUMNS:
        print(f"[board] create_task: invalid column '{column}'", file=sys.stderr)
        return False

    now = now_iso()
    task = {
        "id": task_id,
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "status": column,
        "created_at": now,
        "updated_at": now,
        "assignee": data.get("assignee"),
        "tags": data.get("tags", []),
    }
    dst = BOARD / column / f"{task_id}.jsonl"
    with open(dst, "w") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")
    _record_event(task_id, "none", column)
    print(f"[board] {task_id} created in {column}")
    return True


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
    _record_event(task_id, from_col, to_col)
    print(f"[board] {task_id}: {from_col} → {to_col}")
    return True


def update_index() -> dict:
    """更新 .ccc/board/index.json 状态总览"""
    counts = {col: len(list_tasks(col)) for col in COLUMNS}
    index_file = BOARD / "index.json"
    index_file.write_text(json.dumps(counts, indent=2, ensure_ascii=False) + "\n")
    return counts


def _load_timeout(phases_file: Path, default: int = 300) -> int:
    """从 phases.json 的第一条 phase 读 timeout"""
    try:
        with open(phases_file) as f:
            data = json.load(f)
            if isinstance(data, list) and data:
                return data[0].get("timeout", default)
    except (FileNotFoundError, json.JSONDecodeError, IndexError):
        pass
    return default


_CLAUDE_CLI = "claude"


def _call_claude_for_plan(task: dict) -> tuple[str, list]:
    """调 claude CLI 生成 plan.md + phases.json"""
    plan_dir = ROOT / ".ccc" / "plans"
    ref_plans = ""
    if plan_dir.exists():
        plan_files = sorted(
            plan_dir.glob("*.plan.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for pf in plan_files[:2]:
            ref_plans += f"--- {pf.name} ---\n{pf.read_text()}\n\n"

    template_plan = (ROOT / "templates" / "plan.plan.md").read_text()
    profile = (ROOT / ".ccc" / "profile.md").read_text()

    prompt = (
        f"你是 CCC 产品经理。根据以下信息生成 SPEC-合规的执行 plan。\n\n"
        f"## 项目概况\n{profile[:1500]}\n\n"
        f"## 任务\n"
        f"- id: {task['id']}\n"
        f"- title: {task.get('title', '')}\n"
        f"- description: {task.get('description', '')}\n\n"
        f"## Plan 格式（严格按此结构）\n{template_plan}\n\n"
        f"## Phases 格式\n"
        f"每行一个 JSON object：\n"
        f'{{"phase": <int>, "status": "pending", "subtasks": {{"1.1": "pending", ...}}, "timeout": <秒>, "commit": null, "notes": ""}}\n\n'
        f"## 参考历史 plan\n{ref_plans if ref_plans else '（无）'}\n\n"
        f"## 输出要求\n"
        f"输出以下两部分，用分隔符包裹：\n\n"
        f"---PLAN---\n（plan.md 完整内容）\n---END_PLAN---\n"
        f"---PHASES---\n（phases JSONL，每行一个 phase JSON）\n---END_PHASES---\n"
    )

    try:
        result = subprocess.run(
            [_CLAUDE_CLI, "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {result.returncode}: {result.stderr[:500]}"
            )

        output = result.stdout

        plan_match = re.search(r"---PLAN---\n(.*?)\n---END_PLAN---", output, re.DOTALL)
        if not plan_match:
            raise RuntimeError("---PLAN--- section not found in Claude output")
        plan_content = plan_match.group(1).strip()

        phases_match = re.search(
            r"---PHASES---\n(.*?)\n---END_PHASES---", output, re.DOTALL
        )
        if not phases_match:
            raise RuntimeError("---PHASES--- section not found in Claude output")

        phases = []
        for line in phases_match.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                phases.append(json.loads(line))

        return plan_content, phases
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after 120s")


def product_role(task_id: str = "") -> dict:
    """产品经理：扫 backlog，或 --promote 调 Claude API 写 SPEC-合规 plan"""
    tasks = list_tasks("backlog")

    if task_id:
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            print(f"[product] backlog 中未找到 task '{task_id}'", file=sys.stderr)
            return {
                "role": "product",
                "error": f"task '{task_id}' not found",
                "counts": update_index(),
            }

        print(f"[product] 正在拆解 {task_id}（调 Claude API 生成 plan）...")
        try:
            plan_content, phases = _call_claude_for_plan(task)
        except RuntimeError as e:
            print(f"[product] API 调用失败: {e}", file=sys.stderr)
            return {"role": "product", "error": str(e), "counts": update_index()}

        plan_dir = ROOT / ".ccc" / "plans"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plan_dir / f"{task_id}.plan.md"
        plan_file.write_text(plan_content)
        print(f"[product] ✓ 写入 {plan_file}")

        phases_dir = ROOT / ".ccc" / "phases"
        phases_dir.mkdir(parents=True, exist_ok=True)
        phases_file = phases_dir / f"{task_id}.phases.json"
        phases_file.write_text(
            "\n".join(json.dumps(p, ensure_ascii=False) for p in phases) + "\n"
        )
        print(f"[product] ✓ 写入 {phases_file} ({len(phases)} phases)")

        move_task(task_id, "backlog", "planned")

        return {"role": "product", "promoted": task_id, "counts": update_index()}

    report = {
        "backlog_count": len(tasks),
        "tasks": [{"id": t["id"], "title": t.get("title", "")} for t in tasks],
        "message": "待办是收件箱。使用 --promote <task_id> 拆解。",
    }
    if tasks:
        print(f"[product] backlog 有 {len(tasks)} 个待处理:")
        for t in tasks:
            print(f"  • {t['id']}: {t.get('title', '?')}")
        print(f"[product] 提示: 使用 --promote <task_id> 拆解")
    else:
        print("[product] backlog 空")
    return {"role": "product", "report": report, "counts": update_index()}


def dev_role() -> dict:
    """开发工程师: 查 in_progress（重试）→ 查 planned（新的）→ opencode 执行"""
    import subprocess as sp
    import tempfile

    moved = []
    task = None
    task_id = ""
    from_col = ""
    MAX_RETRY = 3

    # Step 1: 有卡在 in_progress 的任务吗？
    stuck = list_tasks("in_progress")
    if stuck:
        task = stuck[-1]
        task_id = task["id"]
        from_col = "in_progress"
        print(f"[dev] 发现卡住任务 {task_id}，准备重试")

        # 读 phases 里的 retry 计数
        phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        retry = 0
        try:
            if phases_file.exists():
                raw = json.loads(phases_file.read_text())
                if isinstance(raw, list) and raw:
                    retry = raw[0].get("retry", 0)
        except (json.JSONDecodeError, IndexError):
            pass

        retry += 1
        if retry > MAX_RETRY:
            # 升舱：移 abnormal + 建紧急修复任务
            abnormal_dir = ROOT / ".ccc" / "abnormal-reports"
            abnormal_dir.mkdir(parents=True, exist_ok=True)
            abnormal_dir.joinpath(f"{task_id}.abnormal.md").write_text(
                f"# {task_id} 升舱报告\n\n"
                f"重试 {MAX_RETRY} 次全部失败，已升舱。\n"
                f"请人工介入。\n"
            )
            bug_id = f"emergency-{task_id}"
            bug_title = f"紧急修复: {task.get('title', task_id)}（opencloud 重试{MAX_RETRY}次失败）"
            create_task({"id": bug_id, "title": bug_title,
                         "description": f"自动升舱:\n{task_id} 重试{MAX_RETRY}次均失败。"})
            print(f"[dev] {task_id} 重试{MAX_RETRY}次失败 → 升舱 {bug_id}", file=sys.stderr)
            return {"role": "dev", "moved": [], "error": "escalated",
                    "counts": update_index()}

        # 更新 retry 计数
        try:
            if phases_file.exists():
                raw = json.loads(phases_file.read_text())
                if isinstance(raw, list) and raw:
                    raw[0]["retry"] = retry
                    phases_file.write_text(json.dumps(raw, ensure_ascii=False) + "\n")
        except (json.JSONDecodeError, IndexError):
            pass
        print(f"[dev] {task_id} 第 {retry}/{MAX_RETRY} 次重试")

    # Step 2: in_progress 无事，取 planned
    if not task:
        planned = list_tasks("planned")
        if not planned:
            return {"role": "dev", "moved": [], "counts": update_index(), "info": "无任务"}
        task = planned[-1]
        task_id = task["id"]
        from_col = "planned"
        move_task(task_id, "planned", "in_progress")

    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not plan.exists() or not phases_file.exists():
        print(f"[dev] {task_id} 缺 plan/phases, 跳过")
        return {"role": "dev", "moved": [], "counts": update_index(),
                "info": f"{task_id} 缺 plan/phases"}

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(phases_file, default=600)
    phase_id = f"{task_id}-p1"

    # 从 plan.md 生成 executor prompt
    plan_content = plan.read_text()
    prompt = (
        f"# CCC 执行任务: {task_id}\n\n"
        f"## Plan\n\n{plan_content}\n\n"
        f"## 完成定义\n"
        f"1. 实现所有需求\n"
        f"2. 跑对应的测试（如有）\n"
        f"3. 提交一个 commit（message 以 {task_id} 开头）\n"
        f"4. 确认代码无语法错误\n"
        f"5. 不超出 plan 文件白名单\n"
    )

    # 写 temp prompt 文件
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".prompt.md", delete=False)
    tmp.write(prompt)
    tmp.close()
    prompt_file = tmp.name

    try:
        print(f"[dev] {task_id} phase={phase_id} timeout={timeout_s}s retry={retry if from_col=='in_progress' else 0}")
        result = sp.run(
            [
                sys.executable, str(ROOT / "scripts" / "opencode-exec.py"),
                "--phase", phase_id,
                "--prompt", prompt_file,
                "--timeout", str(timeout_s),
            ],
            capture_output=True, text=True, timeout=timeout_s + 30,
        )
        # 写 report（无论成败）
        report_dir = ROOT / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report = report_dir / f"{task_id}.report.md"
        report.write_text(
            f"# {task_id} 执行报告\n\n"
            f"## 信息\n"
            f"- Phase: {phase_id}\n"
            f"- Timeout: {timeout_s}s\n"
            f"- 退出码: {result.returncode}\n"
            f"- 时长: -\n\n"
            f"## stdout\n```\n{result.stdout[:2000]}\n```\n\n"
            f"## stderr\n```\n{result.stderr[:1000]}\n```\n"
        )
        if result.returncode == 0:
            move_task(task_id, "in_progress", "testing")
            moved.append(task_id)
            print(f"[dev] {task_id} ✓ → testing")
        else:
            print(f"[dev] {task_id} ✗ rc={result.returncode}（停留在 in_progress，下轮重试）", file=sys.stderr)
    except sp.TimeoutExpired:
        print(f"[dev] {task_id} 超时（停留在 in_progress，下轮重试）", file=sys.stderr)
        report_dir = ROOT / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_dir.joinpath(f"{task_id}.report.md").write_text(
            f"# {task_id} 执行报告\n\n## 信息\n- 状态: 超时\n"
        )
    finally:
        os.unlink(prompt_file)

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
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                all_ok = False
                print(
                    f"[reviewer] {task_id} py_compile {py.name} FAIL: {r.stderr[:200]}",
                    file=sys.stderr,
                )
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
                "python3",
                "-m",
                "pytest",
                str(ROOT / "tests" / "scripts"),
                "-q",
                "--tb=line",
                "--timeout=60",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
        else:
            print(
                f"[tester] {task_id} pytest FAIL: {result.stdout[-200:]}",
                file=sys.stderr,
            )
    return {"role": "tester", "moved": moved, "counts": update_index()}


def ops_role() -> dict:
    """运维监控: 健康检查 + 告警 (不动 board)"""
    health = {
        "opencode_pids": len(
            list((Path.home() / ".ccc" / "opencode-pids").glob("*.pid"))
        ),
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob(f"*-L*.md"))),
        "git_ahead": 0,
    }
    # git ahead check
    import subprocess as sp

    for proj in [
        ROOT,
        ROOT.parent / "qx-observer",
        ROOT.parent / "xianyu",
        ROOT.parent / "projects" / "qx",
    ]:
        if (proj / ".git").exists():
            r = sp.run(
                ["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                cwd=proj,
                timeout=10,
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
            [
                "git",
                "tag",
                "-a",
                f"board-{task_id}",
                "-m",
                f"v0.16: {task_id} 看板发布",
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
        )
        # git push tag
        sp.run(
            ["git", "push", "origin", f"board-{task_id}"],
            cwd=ROOT,
            capture_output=True,
            timeout=30,
        )
        # 挪 released
        move_task(task_id, "verified", "released")
        moved.append(task_id)
    return {"role": "kb", "moved": moved, "counts": update_index()}


def regress_role() -> dict:
    """回测工程师: 每日扫 released → py_compile + git diff → 发现回归→建 bug"""
    import subprocess as sp
    from datetime import date

    results = {"checked": 0, "passed": 0, "failed": 0, "regressions": []}
    tasks = list_tasks("released")
    if not tasks:
        return {"role": "regress", "info": "无已发布任务", "results": results}

    today = date.today().isoformat()
    scripts_dir = ROOT / "scripts"
    py_files = list(scripts_dir.rglob("*.py"))

    for task in tasks:
        tid = task["id"]
        results["checked"] += 1

        # 1. py_compile
        py_ok = True
        for py in py_files:
            r = sp.run(
                ["python3", "-m", "py_compile", str(py)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                py_ok = False
                break

        # 2. git diff 检查是否代码被意外改过
        diff_ok = True
        r = sp.run(
            ["git", "diff", "--stat"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.stdout.strip():
            diff_ok = False

        if py_ok and diff_ok:
            results["passed"] += 1
            print(f"[regress] ✓ {tid}")
        else:
            results["failed"] += 1
            bug_id = f"regression-{tid}-{results['failed']}"
            bug_title = f"回归: {task.get('title', tid)} ({today})"
            bug_desc = f"原任务 {tid} 在 {today} 回测失败\n"
            if not py_ok:
                bug_desc += "- py_compile 失败：代码有语法错误\n"
            if not diff_ok:
                bug_desc += "- git diff 非空：代码有意外改动\n"
            create_task({"id": bug_id, "title": bug_title, "description": bug_desc})
            results["regressions"].append(bug_id)
            print(f"[regress] ✗ {tid} → {bug_id}")

    # 写回测日报
    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"regression-{today}.md"
    report.write_text(
        f"# 回测日报 {today}\n\n"
        f"- 检查任务: {results['checked']}\n"
        f"- 通过: {results['passed']}\n"
        f"- 失败: {results['failed']}\n"
        f"- 新建回归 bug: {len(results['regressions'])}\n"
    )
    return {"role": "regress", "results": results, "report": str(report)}


ROLES = {
    "product": product_role,
    "dev": dev_role,
    "reviewer": reviewer_role,
    "tester": tester_role,
    "ops": ops_role,
    "kb": kb_role,
    "regress": regress_role,
}


def batch_process(lines: list[dict]) -> dict:
    """批量处理 create/move 操作

    每行格式:
      {"action":"create","id":"...","title":"...","column":"backlog",...}
      {"action":"move","id":"...","from":"backlog","to":"planned"}
    """
    results: dict = {"created": [], "moved": [], "errors": []}
    for i, op in enumerate(lines):
        action = op.get("action", "")
        task_id = op.get("id", "")
        try:
            if action == "create":
                column = op.get("column", "backlog")
                ok = create_task(op, column=column)
                if ok:
                    results["created"].append(task_id)
                else:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "create failed"}
                    )
            elif action == "move":
                from_col = op.get("from", "")
                to_col = op.get("to", "")
                if not from_col or not to_col:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "missing from/to"}
                    )
                    continue
                ok = move_task(task_id, from_col, to_col)
                if ok:
                    results["moved"].append(task_id)
                else:
                    results["errors"].append(
                        {"line": i, "id": task_id, "error": "move failed"}
                    )
            else:
                results["errors"].append(
                    {"line": i, "id": task_id, "error": f"unknown action '{action}'"}
                )
        except Exception as e:
            results["errors"].append({"line": i, "id": task_id, "error": str(e)})
    results["counts"] = update_index()
    return results


def main():
    ap = argparse.ArgumentParser(description="CCC 任务看板 6 角色核心")
    ap.add_argument(
        "role",
        nargs="?",
        choices=list(ROLES.keys()) + ["index"],
        help="角色名 或 'index'",
    )
    ap.add_argument(
        "--batch", action="store_true", help="批量模式（从 stdin 读 JSONL）"
    )
    ap.add_argument("--file", type=str, help="批量模式输入文件（替代 stdin）")
    ap.add_argument(
        "--promote",
        type=str,
        help="product: 处理指定 backlog task → 写 plan/phases → 挪 planned",
    )
    ap.add_argument("--json", action="store_true", help="JSON 输出（角色模式下）")
    args = ap.parse_args()

    if args.batch:
        fp = open(args.file) if args.file else sys.stdin
        lines = []
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[board] batch skip invalid JSON: {e}", file=sys.stderr)
        if args.file:
            fp.close()
        result = batch_process(lines)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.role == "index":
        print(json.dumps(update_index(), indent=2, ensure_ascii=False))
        return

    if not args.role:
        ap.print_help()
        sys.exit(1)

    if args.promote:
        if args.role != "product":
            print("[board] --promote 仅适用于 product 角色", file=sys.stderr)
            sys.exit(1)
        result = product_role(task_id=args.promote)
    else:
        result = ROLES[args.role]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
