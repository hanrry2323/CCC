#!/usr/bin/env python3
"""ccc-board.py — 任务看板核心 (v0.18)

7 角色都通过这个 core 操作 .ccc/board/:
- product: backlog → planned
- dev: planned → in_progress → testing
- reviewer: testing → verified (过 ruff/mypy)
- tester: testing → verified (过 pytest)
- ops: 健康检查 (不动 board)
- kb: verified → released (归档)
- regress: released → backlog (回归回测)

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

COLUMNS = ["backlog", "planned", "in_progress", "testing", "verified", "released", "abnormal"]

# 列迁移白名单：{目标列: [允许的源列列表]}
# 不在白名单中的迁移会被拒绝
COLUMN_TRANSITIONS: dict[str, list[str]] = {
    "planned": ["backlog"],
    "in_progress": ["planned"],
    "testing": ["in_progress"],
    "verified": ["testing"],
    "released": ["verified"],
    "backlog": ["released", "in_progress", "abnormal"],  # regress 回归 / dev 升舱 / 手动回退
    "abnormal": ["in_progress", "testing", "verified", "released"],  # 任何列都可转入异常
}

# 容错参数
MAX_RETRY = 5           # 最大重试次数 → 异常隔离
MAX_STALE_HOURS = 6      # in_progress 卡住超时 → 异常隔离
STALE_CHECK_INTERVAL = 6  # ops_role 每次扫描间隔（判断是否该扫描）


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _backoff_seconds(retry: int) -> int:
    """指数退避：60 * 2^retry，封顶 3600s（1h）

    retry=0→60s, 1→120s, 2→240s, 3→480s, 4→960s, 5→1920s, 6+→3600s
    """
    return min(60 * (2 ** retry), 3600)


def _quarantine(task_id: str, reason: str) -> None:
    """将任务移入异常列（abnormal），附带原因

    跳过 create_task 的唯一性校验（可能已在 abnormal），
    如果已在 abnormal 则只更新。
    """
    from_col = ""
    for col in COLUMNS:
        if col == "abnormal":
            continue
        src = BOARD / col / f"{task_id}.jsonl"
        if src.exists():
            from_col = col
            break

    if not from_col:
        print(f"[quarantine] {task_id} not found in any column, skip")
        return

    task = json.loads((BOARD / from_col / f"{task_id}.jsonl").read_text())
    task["status"] = "abnormal"
    task["updated_at"] = now_iso()
    if "tags" not in task:
        task["tags"] = []
    if "abnormal" not in task["tags"]:
        task["tags"].append("abnormal")
    if "automated" not in task["tags"]:
        task["tags"].append("automated")
    task["title"] = f"[ABNORMAL] {task.get('title', task_id)}"
    if "note" not in task:
        task["note"] = reason
    else:
        task["note"] += f"\n{reason}"

    dst = BOARD / "abnormal" / f"{task_id}.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as f:
        f.write(json.dumps(task, ensure_ascii=False) + "\n")

    (BOARD / from_col / f"{task_id}.jsonl").unlink()
    _record_event(task_id, from_col, "abnormal")
    print(f"[quarantine] {task_id} {from_col} → abnormal: {reason}")


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
    """把 task 从 from_col 挪到 to_col（受 COLUMN_TRANSITIONS 白名单约束）"""
    # 列迁移门控
    allowed_from = COLUMN_TRANSITIONS.get(to_col, [])
    if from_col not in allowed_from:
        print(
            f"[board] 拒绝迁移: {from_col} → {to_col} "
            f"(允许的源列: {allowed_from})",
            file=sys.stderr,
        )
        return False
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
    """从 phases.jsonl 的第一行读 timeout（JSONL 格式，每行一个 JSON）"""
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                phase = json.loads(line)
                return phase.get("timeout", default)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return default


_CLAUDE_CLI = "claude"


def _get_relay_url() -> str:
    return os.environ.get("AGENT_PLANNER_BASE_URL", "http://127.0.0.1:4000")


def _call_claude_for_plan(task: dict) -> tuple[str, list]:
    """调 claude CLI 生成 plan.md + phases.json（通过中转站 127.0.0.1:4000）"""
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

    relay_url = _get_relay_url()
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = relay_url
    try:
        result = subprocess.run(
            [_CLAUDE_CLI, "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
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


def _generate_fallback_plan(task: dict) -> str:
    """API 不可用时生成 fallback plan"""
    return (
        f"# {task['id']}\n\n"
        f"> 此 plan 由 fallback 自动生成（product API 不可用）\n\n"
        f"## 目标\n"
        f"- {task.get('title', task['id'])}\n"
        f"- {task.get('description', '请手动补充详细描述')}\n\n"
        f"## 文件白名单\n"
        f"- （待补充）\n\n"
        f"## 验收\n"
        f"1. 完成任务目标\n"
        f"2. 相关测试通过\n"
    )


def _generate_fallback_phases() -> list:
    """API 不可用时生成 fallback phases（单 phase）"""
    return [{"phase": 1, "status": "pending", "subtasks": {"1.1": "pending"}, "timeout": 300, "commit": None, "notes": "fallback"}]


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
        plan_content = None
        phases = None
        fallback = False
        try:
            plan_content, phases = _call_claude_for_plan(task)
        except RuntimeError as e:
            print(f"[product] API 调用失败: {e}", file=sys.stderr)
            print(f"[product] 使用 fallback plan（API 不可用）")
            plan_content = _generate_fallback_plan(task)
            phases = _generate_fallback_phases()
            fallback = True

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

        result = {"role": "product", "promoted": task_id, "fallback": fallback, "counts": update_index()}
        return result

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

    # Step 1: 有卡在 in_progress 的任务吗？
    stuck = list_tasks("in_progress")
    if stuck:
        task = stuck[-1]
        task_id = task["id"]
        from_col = "in_progress"
        print(f"[dev] 发现卡住任务 {task_id}，准备重试")

        # 读 phases 里的 retry 计数 + retry_at（JSONL 格式，取第一行）
        phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        retry = 0
        retry_at = None
        try:
            if phases_file.exists():
                with open(phases_file) as _pf:
                    for _line in _pf:
                        _line = _line.strip()
                        if not _line:
                            continue
                        parsed = json.loads(_line)
                        retry = parsed.get("retry", 0)
                        retry_at = parsed.get("retry_at")
                        break
        except (json.JSONDecodeError):
            pass

        # 退避检查：如果在退避期内，跳过此任务的这一轮
        if retry_at:
            from datetime import datetime as _dt
            try:
                wait_until = _dt.fromisoformat(retry_at)
                if _dt.now(timezone.utc) < wait_until.replace(tzinfo=timezone.utc):
                    remaining = (wait_until.replace(tzinfo=timezone.utc) - _dt.now(timezone.utc)).total_seconds()
                    print(f"[dev] {task_id} 退避中（还剩 {remaining:.0f}s），跳过本轮")
                    return {
                        "role": "dev",
                        "moved": [],
                        "counts": update_index(),
                        "info": f"{task_id} 退避中",
                    }
            except (ValueError, TypeError):
                pass

        retry += 1
        if retry > MAX_RETRY:
            # 达到最大重试 → 异常隔离
            _quarantine(task_id, f"重试{MAX_RETRY}次全部失败，已移入异常列")
            # 同时创建紧急修复任务到 backlog
            bug_id = f"emergency-{task_id}"
            bug_title = f"紧急修复: {task.get('title', task_id)}（重试{MAX_RETRY}次失败）"
            create_task(
                {
                    "id": bug_id,
                    "title": bug_title,
                    "description": f"自动升舱:\n{task_id} 重试{MAX_RETRY}次均失败，已移入异常列。",
                }
            )
            print(
                f"[dev] {task_id} 重试{MAX_RETRY}次失败 → {_quarantine.__name__} + 升舱 {bug_id}",
                file=sys.stderr,
            )
            return {
                "role": "dev",
                "moved": [],
                "error": "quarantined",
                "counts": update_index(),
            }

        # 计算退避时间
        backoff = _backoff_seconds(retry - 1)  # retry 已自增，用增量前的值计算
        retry_at_iso = (
            datetime.now(timezone.utc).isoformat()
            if retry >= 1
            else None
        )
        # 更新 retry 计数 + retry_at（JSONL，更新第一行）
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                for i, _line in enumerate(lines):
                    _line_s = _line.strip()
                    if not _line_s:
                        continue
                    phase = json.loads(_line_s)
                    phase["retry"] = retry
                    phase["retry_at"] = retry_at_iso
                    lines[i] = json.dumps(phase, ensure_ascii=False)
                    break
                phases_file.write_text("\n".join(lines))
        except (json.JSONDecodeError):
            pass
        print(f"[dev] {task_id} 第 {retry}/{MAX_RETRY} 次重试，退避 {backoff}s")

    # Step 2: in_progress 无事，取 planned
    if not task:
        planned = list_tasks("planned")
        if not planned:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "无任务",
            }
        task = planned[-1]
        task_id = task["id"]
        from_col = "planned"
        move_task(task_id, "planned", "in_progress")

    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not plan.exists() or not phases_file.exists():
        print(f"[dev] {task_id} 缺 plan/phases, 跳过")
        return {
            "role": "dev",
            "moved": [],
            "counts": update_index(),
            "info": f"{task_id} 缺 plan/phases",
        }

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
        print(
            f"[dev] {task_id} phase={phase_id} timeout={timeout_s}s retry={retry if from_col == 'in_progress' else 0}"
        )
        # PID 检查：opencode 还在跑就不重复启动
        pid_path = ROOT / ".ccc" / "pids" / f"{task_id}.pid"
        if pid_path.exists():
            try:
                old_pid = int(pid_path.read_text().strip())
                try:
                    os.kill(old_pid, 0)
                    print(f"[dev] {task_id} opencode {old_pid} 仍在运行，跳过")
                    return {
                        "role": "dev",
                        "moved": [],
                        "counts": update_index(),
                        "info": f"opencode PID={old_pid} 运行中",
                    }
                except OSError:
                    # stale PID, clean up and fall through to done check
                    print(
                        f"[dev] {task_id} PID {old_pid} 异常退出，清理后重试",
                        file=sys.stderr,
                    )
                    try:
                        pid_path.unlink()
                    except OSError:
                        pass
            except (ValueError, OSError):
                pass

        done_path = ROOT / ".ccc" / "pids" / f"{task_id}.done"
        exitcode_path = ROOT / ".ccc" / "pids" / f"{task_id}.exitcode"
        result_path = ROOT / ".ccc" / "reports" / f"{task_id}.result.json"
        pid_path = ROOT / ".ccc" / "pids" / f"{task_id}.pid"

        # 检查上一轮 opencode 是否跑完
        if done_path.exists():
            exit_code = (
                exitcode_path.read_text().strip() if exitcode_path.exists() else "?"
            )
            result_raw = result_path.read_text() if result_path.exists() else "{}"
            report_dir = ROOT / ".ccc" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_dir.joinpath(f"{task_id}.report.md").write_text(
                f"# {task_id} 执行报告\n\n## 信息\n- Phase: {phase_id}\n"
                f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n"
            )
            for p in [done_path, exitcode_path, pid_path, result_path]:
                try:
                    p.unlink()
                except OSError:
                    pass
            if exit_code == "0":
                move_task(task_id, "in_progress", "testing")
                moved.append(task_id)
                print(f"[dev] {task_id} ✓ → testing")
            else:
                print(
                    f"[dev] {task_id} ✗ rc={exit_code}（留在 in_progress 下轮重试）",
                    file=sys.stderr,
                )
            return {"role": "dev", "moved": moved, "counts": update_index()}

        # 启动 opencode（通过 runner.sh 持久化结果）
        report_dir = ROOT / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{task_id}.report.md"

        proc = sp.Popen(
            [
                str(ROOT / "scripts" / "opencode-runner.sh"),
                task_id,
                str(ROOT),
                "--phase",
                phase_id,
                "--prompt",
                prompt_file,
                "--timeout",
                str(timeout_s),
            ],
            start_new_session=True,
        )
        pid_dir = ROOT / ".ccc" / "pids"
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
        report_path.write_text(
            f"# {task_id} 执行报告\n\n## 信息\n- 状态: 运行中\n- PID: {proc.pid}\n- Started: {now_iso()}\n"
        )
        print(f"[dev] {task_id} 后台启动 PID={proc.pid}，下轮检查结果")

    except Exception as e:
        print(f"[dev] {task_id} 启动失败: {e}", file=sys.stderr)
    finally:
        # prompt 保留给后台读
        pass

    return {"role": "dev", "moved": moved, "counts": update_index()}


def _parse_plan_scope(task_id: str) -> list[str]:
    """从 plan.md 读文件白名单"""
    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    if not plan.exists():
        return []
    content = plan.read_text()
    # 找 ## 文件白名单 后面的行，按 - 或 * 开头的
    in_scope = False
    files = []
    for line in content.split("\n"):
        if line.startswith("## 文件白名单") or line.startswith("## 文件"):
            in_scope = True
            continue
        if in_scope and line.startswith("## "):
            break
        if in_scope and (
            line.strip().startswith("- ") or line.strip().startswith("* ")
        ):
            f = line.strip()[2:].strip()
            # 支持 glob 模式
            if f and not f.startswith("不"):
                files.append(f)
    return files


def reviewer_role() -> dict:
    """代码审查员: 扫 testing → 按 plan 文件白名单检查 py_compile → 通过则挪 verified"""
    import subprocess as sp
    import glob

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        files = _parse_plan_scope(task_id)

        if not files:
            # 没有文件白名单 → 传统模式：扫全部 scripts/*.py
            files = [str(p) for p in (ROOT / "scripts").rglob("*.py")]

        py_files = []
        for f in files:
            # glob 展开（支持 scripts/**/*.py 模式）
            matched = glob.glob(str(ROOT / f)) if "*" in f else [str(ROOT / f)]
            py_files.extend(matched)
        py_files = [f for f in py_files if f.endswith(".py") and Path(f).exists()]

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
                    f"[reviewer] {task_id} py_compile {Path(py).name} FAIL: {r.stderr[:200]}",
                    file=sys.stderr,
                )
                break

        if not py_files:
            all_ok = True  # 无 .py 文件不需要审查

        if all_ok:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
            print(f"[reviewer] {task_id} ✓（检查 {len(py_files)} 文件）")
    return {"role": "reviewer", "moved": moved, "counts": update_index()}


def tester_role() -> dict:
    """测试工程师: 扫 testing → 按 plan 跑验证 → 通过则挪 verified"""
    import subprocess as sp

    moved = []
    for task in list_tasks("testing"):
        task_id = task["id"]
        plan_file = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
        verify_commands = []
        if plan_file.exists():
            content = plan_file.read_text()
            in_verify = False
            for line in content.split("\n"):
                if line.startswith("## 验收") or line.startswith("## 验证"):
                    in_verify = True
                    continue
                if in_verify and line.startswith("## "):
                    break
                if (
                    in_verify
                    and line.strip().startswith("- ")
                    and not line.strip().startswith("- 不")
                ):
                    cmd = line.strip()[2:].strip()
                    verify_commands.append(cmd)

        # fallback: 如果没有验收项，跑 pytest
        if not verify_commands:
            verify_commands = [
                f"python3 -m pytest {ROOT / 'tests' / 'scripts'} -q --tb=line --timeout=60"
            ]

        all_ok = True
        for cmd in verify_commands:
            if not all_ok:
                break
            r = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                all_ok = False
                print(f"[tester] {task_id} FAIL: {r.stdout[-200:]}", file=sys.stderr)

        if all_ok:
            move_task(task_id, "testing", "verified")
            moved.append(task_id)
            print(f"[tester] {task_id} ✓（验证 {len(verify_commands)} 项）")
    return {"role": "tester", "moved": moved, "counts": update_index()}


def ops_role() -> dict:
    """运维监控: 健康检查 + stale 检测 + 孤儿 PID 清理 + 告警"""
    health = {
        "opencode_pids": len(
            list((Path.home() / ".ccc" / "opencode-pids").glob("*.pid"))
        ),
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob(f"*-L*.md"))),
        "git_ahead": 0,
        "stale_detected": 0,
        "orphan_pids_cleaned": 0,
    }

    # 1. Stale 检测：in_progress 超时 → 异常列
    from datetime import datetime as _dt
    now = _dt.now(timezone.utc)
    for task in list_tasks("in_progress"):
        updated_str = task.get("updated_at", task.get("created_at", ""))
        if not updated_str:
            continue
        try:
            updated = _dt.fromisoformat(updated_str.replace("Z", "+00:00"))
            hours_stale = (now - updated).total_seconds() / 3600
            if hours_stale > MAX_STALE_HOURS:
                _quarantine(
                    task["id"],
                    f"in_progress 滞留 {hours_stale:.1f}h（阈值 {MAX_STALE_HOURS}h），自动隔离",
                )
                health["stale_detected"] += 1
                print(
                    f"[ops] stale: {task['id']} in_progress 滞留 {hours_stale:.1f}h → abnormal"
                )
        except (ValueError, TypeError):
            pass

    # 2. 孤儿 PID 清理
    pid_dir = ROOT / ".ccc" / "pids"
    if pid_dir.exists():
        for f in pid_dir.glob("*.pid"):
            try:
                pid = int(f.read_text().strip())
                os.kill(pid, 0)  # 检查进程是否存在
            except (ValueError, OSError, ProcessLookupError):
                stem = f.stem
                f.unlink()
                for suffix in [".done", ".exitcode", ".report.md", ".result.json"]:
                    extra = pid_dir.parent / "reports" / f"{stem}{suffix}"
                    if extra.exists():
                        extra.unlink(missing_ok=True)
                health["orphan_pids_cleaned"] += 1
                print(f"[ops] 清理孤儿 PID: {stem}")

    # 3. 检查 abnormal 列任务（上报）
    abnormal_tasks = list_tasks("abnormal")
    if abnormal_tasks:
        print(f"[ops] ⚠ abnormal 列有 {len(abnormal_tasks)} 个任务需处理:")
        for t in abnormal_tasks:
            print(f"  • {t['id']}: {t.get('note', '?')[:120]}")
        health["abnormal_count"] = len(abnormal_tasks)

    # 4. git ahead check
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


def _extract_agents_suggestions(
    filepath: Path, task_id: str, source: str
) -> list[dict]:
    """从 report/verdict 文件中提取 AGENTS.md 建议"""
    import re

    suggestions = []
    if not filepath.exists():
        return suggestions
    content = filepath.read_text()
    # tempered dot: match content until blank line, ---, next marker, or end
    pattern = re.compile(
        r"> \*\*AGENTS\.md 建议:\*\*\s*((?:(?!> \*\*AGENTS\.md 建议:|\n\n|\n---).)*)",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        text = match.group(1).strip()
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        text = text.strip()
        if text:
            suggestions.append({"task_id": task_id, "source": source, "content": text})
    return suggestions


def kb_role() -> dict:
    """知识管理员: 扫 verified → 归档 + git tag → 挪 released → 收集 AGENTS.md 建议"""
    import subprocess as sp

    moved = []
    all_suggestions: list[dict] = []
    for task in list_tasks("verified"):
        task_id = task["id"]
        # 从 VERSION 读版本号
        version = Path(ROOT / "VERSION").read_text().strip()
        # git tag（版本号动态读取，不硬编码）
        sp.run(
            [
                "git",
                "tag",
                "-a",
                f"board-{task_id}",
                "-m",
                f"{version}: {task_id} 看板发布",
            ],
            cwd=ROOT,
            capture_output=True,
            timeout=10,
        )
        # git push tag
        push_r = sp.run(
            ["git", "push", "origin", f"board-{task_id}"],
            cwd=ROOT,
            capture_output=True,
            timeout=30,
        )
        if push_r.returncode != 0:
            print(f"[kb] {task_id} git push 失败 rc={push_r.returncode}", file=sys.stderr)
            fail_log = ROOT / ".ccc" / "reports" / f"{task_id}.push-fail.md"
            fail_log.write_text(
                f"# {task_id} git push 失败\n\n"
                f"rc={push_r.returncode}\n"
                f"{push_r.stderr[:500]}\n"
            )
            continue

        # CHANGELOG.md 追加
        today_str = now_iso()[:10]
        changelog_path = ROOT / "CHANGELOG.md"
        entry = f"\n## [{version}] - {today_str}\n\n- {task_id}: {task.get('title', '')} 看板发布\n"
        if changelog_path.exists():
            changelog_path.write_text(changelog_path.read_text() + entry)
        else:
            changelog_path.write_text(f"# CHANGELOG\n\n{entry}")
        print(f"[kb] ✓ CHANGELOG 追加 {task_id} ({version})")

        # 收集 AGENTS.md 建议
        report_file = ROOT / ".ccc" / "reports" / f"{task_id}.report.md"
        all_suggestions.extend(
            _extract_agents_suggestions(report_file, task_id, source="dev")
        )
        verdict_file = ROOT / ".ccc" / "verdicts" / f"{task_id}.verdict.md"
        all_suggestions.extend(
            _extract_agents_suggestions(verdict_file, task_id, source="reviewer")
        )

        # 挪 released
        move_task(task_id, "verified", "released")
        moved.append(task_id)

    # 去重 → 写 pending-agents-suggestions.md
    if all_suggestions:
        seen: set[str] = set()
        unique: list[dict] = []
        for s in all_suggestions:
            key = s["content"].strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(s)

        pending_file = ROOT / ".ccc" / "pending-agents-suggestions.md"
        template_file = ROOT / "templates" / "pending-agents-suggestions.md"

        new_blocks: list[str] = []
        now_str = now_iso()[:10]
        for s in unique:
            block = (
                f"## 来源 task: {s['task_id']}\n\n"
                f"归档日期: {now_str}\n\n"
                f"### 来自 {s['source']}\n\n"
                f"{s['content']}\n\n"
                f"---\n"
            )
            new_blocks.append(block)

        new_content = "\n".join(new_blocks)
        if pending_file.exists():
            existing = pending_file.read_text().rstrip()
            pending_file.write_text(existing + "\n" + new_content + "\n")
        else:
            header = (
                template_file.read_text()
                if template_file.exists()
                else "# Pending AGENTS.md Suggestions\n\n"
            )
            pending_file.write_text(header + "\n" + new_content + "\n")
        print(f"[kb] ✓ 收集 {len(unique)} 条 AGENTS.md 建议到 {pending_file}")

    return {
        "role": "kb",
        "moved": moved,
        "suggestions_collected": len(all_suggestions),
        "counts": update_index(),
    }


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
            today_compact = date.today().strftime("%Y%m%d")
            bug_id = f"regression-{tid}-{today_compact}-{results['failed']}"
            bug_title = f"回归: {task.get('title', tid)} ({today})"
            bug_desc = f"原任务 {tid} 在 {today} 回测失败\n"
            if not py_ok:
                bug_desc += "- py_compile 失败：代码有语法错误\n"
            if not diff_ok:
                bug_desc += "- git diff 非空：代码有意外改动\n"
            create_task({"id": bug_id, "title": bug_title, "description": bug_desc})
            results["regressions"].append(bug_id)
            print(f"[regress] ✗ {tid} → {bug_id}")
            # 把原任务移回 backlog 并加 regression 标签
            src_path = BOARD / "released" / f"{tid}.jsonl"
            if src_path.exists():
                _lines = src_path.read_text().split("\n")
                for _i, _line in enumerate(_lines):
                    _ls = _line.strip()
                    if not _ls:
                        continue
                    try:
                        _obj = json.loads(_ls)
                        _tags = _obj.get("tags", [])
                        if "regression" not in _tags:
                            _tags.append("regression")
                        _obj["tags"] = _tags
                        _obj["updated_at"] = now_iso()
                        _lines[_i] = json.dumps(_obj, ensure_ascii=False)
                        break
                    except json.JSONDecodeError:
                        pass
                src_path.write_text("\n".join(_lines))
            move_task(tid, "released", "backlog")
            # macOS 桌面通知
            subprocess.run(
                ["bash", str(ROOT / "scripts" / "ccc-notify.sh"), "L2", bug_title, bug_desc[:200]],
                capture_output=True,
                timeout=10,
            )

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


def get_timeline(task_id: str | None = None) -> list[dict]:
    """从 .ccc/board/events/<task_id>.events.jsonl 读取 timeline 事件

    Args:
        task_id: 指定 task，None 则返回所有 task 的 events
    """
    if not EVENTS_DIR.exists():
        return []
    events: list[dict] = []
    if task_id:
        event_file = EVENTS_DIR / f"{task_id}.events.jsonl"
        if event_file.exists():
            for line in event_file.read_text().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    else:
        for f in sorted(EVENTS_DIR.glob("*.events.jsonl")):
            for line in f.read_text().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


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
    ap = argparse.ArgumentParser(description="CCC 任务看板 7 角色核心")
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
