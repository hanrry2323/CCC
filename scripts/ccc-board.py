#!/usr/bin/env python3
"""ccc-board.py — 任务看板核心 (v0.20)

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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from _config import Config
from _board_store import FileBoardStore

cfg = Config()
store = FileBoardStore(cfg.workspace)
ROOT = cfg.workspace
CCC_HOME = cfg.ccc_home
BOARD = ROOT / ".ccc" / "board"
EVENTS_DIR = BOARD / "events"

# 容错参数（从 Config 读取）
MAX_RETRY = cfg.max_retry
MAX_STALE_HOURS = cfg.max_stale_hours
STALE_CHECK_INTERVAL = 6  # ops_role 每次扫描间隔（判断是否该扫描）


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _backoff_seconds(retry: int) -> int:
    """指数退避：60 * 2^retry，封顶 3600s（1h）

    retry=0→60s, 1→120s, 2→240s, 3→480s, 4→960s, 5→1920s, 6+→3600s
    """
    return min(60 * (2**retry), 3600)


def _quarantine(task_id: str, reason: str) -> None:
    """将任务移入异常列（委托 FileBoardStore）"""
    store.quarantine(task_id, reason)


def _task_id_exists(task_id: str) -> bool:
    """检查 task_id 是否在任意列中已存在"""
    return store._task_id_exists(task_id)


def create_task(data: dict, column: str = "backlog") -> bool:
    """创建新 task（委托 FileBoardStore）"""
    return store.create_task(data, column=column)


def list_tasks(column: str) -> list[dict]:
    """读某列所有 task（委托 FileBoardStore）"""
    return store.list_tasks(column)


def move_task(task_id: str, from_col: str, to_col: str) -> bool:
    """把 task 从 from_col 挪到 to_col（委托 FileBoardStore）"""
    return store.move_task(task_id, from_col, to_col)


def update_index() -> dict:
    """更新 .ccc/board/index.json 状态总览（委托 FileBoardStore）"""
    return store.update_index()


def _load_timeout(phases_file: Path, default: int = 300) -> int:
    """从 phases.jsonl 的第一行读 timeout（JSONL 格式，每行一个 JSON）"""
    try:
        with open(phases_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                phase = json.loads(line)
                if isinstance(phase, list):
                    phase = phase[0] if phase else {}
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
    return [
        {
            "phase": 1,
            "status": "pending",
            "subtasks": {"1.1": "pending"},
            "timeout": 300,
            "commit": None,
            "notes": "fallback",
        }
    ]


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
            print("[product] 使用 fallback plan（API 不可用）")
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
        schema_line = json.dumps({"schema_version": "1.0"}, ensure_ascii=False)
        phases_file.write_text(
            schema_line + "\n"
            + "\n".join(json.dumps(p, ensure_ascii=False) for p in phases) + "\n"
        )
        print(f"[product] ✓ 写入 {phases_file} ({len(phases)} phases)")

        move_task(task_id, "backlog", "planned")

        result = {
            "role": "product",
            "promoted": task_id,
            "fallback": fallback,
            "counts": update_index(),
        }
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
        print("[product] 提示: 使用 --promote <task_id> 拆解")
    else:
        print("[product] backlog 空")
    return {"role": "product", "report": report, "counts": update_index()}


def dev_role() -> dict:
    """开发工程师: 查 in_progress（重试）→ 查 planned（新的）→ opencode 执行"""
    import subprocess as sp

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

        # 读 phases 里的 retry 计数 + retry_at（JSONL 格式，跳过 schema_version 元数据行）
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
                        try:
                            _meta = json.loads(_line)
                            if "schema_version" in _meta:
                                continue  # 跳过 schema_version 元数据行
                        except json.JSONDecodeError:
                            continue
                        parsed = _meta
                        # phases 可能是 JSON 数组 [{...}] 或 JSONL 单行 {...}
                        if isinstance(parsed, list):
                            parsed = parsed[0] if parsed else {}
                        retry = parsed.get("retry", 0)
                        retry_at = parsed.get("retry_at")
                        break
        except json.JSONDecodeError:
            pass

        # ★ 退避前先检查 .done（防退避死锁）
        _done_early = ROOT / ".ccc" / "pids" / f"{task_id}.done"
        if _done_early.exists():
            print(f"[dev] {task_id} .done 存在，跳过退避直接处理结果")
        else:
            # 退避检查：如果在退避期内，跳过此任务的这一轮
            if retry_at:
                from datetime import datetime as _dt

                try:
                    wait_until = _dt.fromisoformat(retry_at)
                    if _dt.now(timezone.utc) < wait_until.replace(tzinfo=timezone.utc):
                        remaining = (
                            wait_until.replace(tzinfo=timezone.utc) - _dt.now(timezone.utc)
                        ).total_seconds()
                        print(f"[dev] {task_id} 退避中（还剩 {remaining:.0f}s），跳过本轮，检查 planned")
                        # 重置 task，使执行流落入 Step 2（planned）
                        task = None
                        task_id = ""
                        from_col = ""
                except (ValueError, TypeError):
                    pass

        # 退避跳过：不增 retry，直接 fall through 到 Step 2（planned）
        if task is not None:
            retry += 1

        if retry >= MAX_RETRY:
            # 达到最大重试 → 异常隔离
            _quarantine(task_id, f"重试{MAX_RETRY}次全部失败，已移入异常列")
            # 同时创建紧急修复任务到 backlog
            bug_id = f"emergency-{task_id}"
            bug_title = (
                f"紧急修复: {task.get('title', task_id)}（重试{MAX_RETRY}次失败）"
            )
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
        backoff = _backoff_seconds(retry - 1) if retry else 0
        retry_at_iso = (datetime.now(timezone.utc) + timedelta(seconds=backoff)).isoformat() if retry >= 1 else None
        # 更新 retry 计数 + retry_at（JSONL，跳过 schema_version 元数据行）
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                for i, _line in enumerate(lines):
                    _line_s = _line.strip()
                    if not _line_s:
                        continue
                    try:
                        _meta = json.loads(_line_s)
                        if "schema_version" in _meta:
                            continue  # 跳过 schema_version 元数据行
                    except json.JSONDecodeError:
                        continue
                    phase = _meta
                    # phases 可能是 JSON 数组 [{...}] 或 JSONL 单行 {...}
                    if isinstance(phase, list):
                        phase = phase[0] if phase else {}
                    phase["retry"] = retry
                    phase["retry_at"] = retry_at_iso
                    lines[i] = json.dumps(phase, ensure_ascii=False)
                    break
                phases_file.write_text("\n".join(lines))
        except json.JSONDecodeError:
            pass
        print(f"[dev] {task_id} 第 {retry}/{MAX_RETRY} 次重试，退避 {backoff}s")

    # Step 2: in_progress 无事，取 planned（迭代，跳过错/缺 plan 的任务）
    if not task:
        planned = list_tasks("planned")
        if not planned:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "无任务",
            }
        # 迭代 planned 任务，跳过缺 plan/phases 的（移入异常），处理第一个合法的
        for candidate in planned:
            cid = candidate["id"]
            cplan = ROOT / ".ccc" / "plans" / f"{cid}.plan.md"
            cphases = ROOT / ".ccc" / "phases" / f"{cid}.phases.json"
            if cplan.exists() and cphases.exists():
                task = candidate
                task_id = cid
                from_col = "planned"
                break
            else:
                # 缺失 plan/phases → 移入异常列，不阻塞其他任务
                _quarantine(cid, "dev_role: 缺 plan 或 phases 文件, 无法执行")
                print(f"[dev] {cid} 缺 plan/phases, 已移入 abnormal")
        if not task:
            return {
                "role": "dev",
                "moved": [],
                "counts": update_index(),
                "info": "planned 任务均缺 plan/phases",
            }
        move_task(task_id, "planned", "in_progress")

    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"

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

    # 写 prompt 文件到 .ccc/pids/（跟其他 task 文件一起清理，不泄漏）
    pids_dir = ROOT / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    try:
        print(
            f"[dev] {task_id} phase={phase_id} timeout={timeout_s}s retry={retry if from_col == 'in_progress' else 0}"
        )
        done_path = ROOT / ".ccc" / "pids" / f"{task_id}.done"
        exitcode_path = ROOT / ".ccc" / "pids" / f"{task_id}.exitcode"
        result_path = ROOT / ".ccc" / "reports" / f"{task_id}.result.json"
        pid_path = ROOT / ".ccc" / "pids" / f"{task_id}.pid"

        # ❗.done 检查必须在 PID 检查之前
        # stale PID 被回收后 os.kill 返回成功，先查 .done 再查 PID
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
            for p in [done_path, exitcode_path, pid_path, result_path, ROOT / ".ccc" / "pids" / f"{task_id}.prompt.md"]:
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

        # PID 检查：.done 不存在时确认 opencode 是否还在跑
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
                    # stale PID
                    print(f"[dev] {task_id} PID {old_pid} 不存在，清理后重试")
                    try:
                        pid_path.unlink()
                    except OSError:
                        pass
            except (ValueError, OSError):
                pass

        # 启动 opencode（通过 runner.sh 持久化结果）
        report_dir = ROOT / ".ccc" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{task_id}.report.md"

        proc = sp.Popen(
            [
                str(CCC_HOME / "scripts" / "opencode-runner.sh"),
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
    """从 plan.md 读文件白名单

    兼容两种格式：
      新模板：## 范围 → - **只改文件**： → 后续 - file 行
      旧格式：## 文件白名单 → 直接 - file 行
    """
    plan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    if not plan.exists():
        return []
    content = plan.read_text()

    def _clean(f: str) -> str:
        """提取纯文件路径（去掉尾部注释/说明）"""
        f = f.strip().strip("`\"'*")
        # 去掉尾部中文/括号说明（product_role 增强 → 空）
        m = re.match(r'^([\w./~@+\-\[\]]+)', f)
        if m:
            f = m.group(1)
        # 如果还多出来尾缀（如括号前有空格）
        for sep in ("（", "(", "`（", "`("):
            idx = f.find(sep)
            if idx > 0:
                f = f[:idx]
        return f.strip().rstrip(".")

    in_scope = False
    collecting_only = False
    old_format = False
    files = []
    for line in content.split("\n"):
        if line.startswith("## 范围"):
            in_scope = True
            old_format = False
            continue
        if line.startswith("## 文件白名单") or line.startswith("## 文件"):
            in_scope = True
            old_format = True
            continue
        if in_scope and line.startswith("## "):
            break
        if not in_scope:
            continue
        stripped = line.strip()

        if not old_format:
            # 新模板格式
            if "**只改文件" in stripped and (stripped.startswith("- ") or stripped.startswith("* ")):
                collecting_only = True
                after_label = stripped.split("**")[-1].lstrip("：:").strip()
                if after_label:
                    for f in after_label.split():
                        f_clean = _clean(f)
                        if f_clean:
                            files.append(f_clean)
                continue
            if "**不改文件" in stripped and (stripped.startswith("- ") or stripped.startswith("* ")):
                break
            if collecting_only:
                if stripped.startswith("- ") or stripped.startswith("* "):
                    f = _clean(stripped[2:])
                    if f and not f.startswith("(") and not f.startswith("不") and f not in ("只改文件", "不改文件"):
                        files.append(f)
        else:
            # 旧格式：直接收集 - 条目
            if stripped.startswith("- ") or stripped.startswith("* "):
                f = _clean(stripped[2:])
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
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
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

    # 5. launchd 自检：检查 7 角色 plist 是否存活
    roles_check = ["product", "dev", "reviewer", "tester", "ops", "kb", "regress"]
    launchd_up = []
    for role in roles_check:
        r = sp.run(
            ["launchctl", "list", f"com.ccc.{role}"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and "PID" in r.stdout:
            launchd_up.append(role)
        else:
            print(f"[ops] ⚠ com.ccc.{role} 未运行")
    health["launchd_up"] = launchd_up
    health["launchd_missing"] = [r for r in roles_check if r not in launchd_up]

    # 4.5 日志清理：删除 >30 天的 role 日志
    if (Path.home() / ".ccc" / "logs").exists():
        _now_ts = time.time()
        _cutoff = _now_ts - 30 * 86400
        for _lf in (Path.home() / ".ccc" / "logs").glob("role-*.log"):
            if _lf.stat().st_mtime < _cutoff:
                _lf.unlink(missing_ok=True)

    # 6. 指标收集 → .ccc/metrics.json
    pid_dir = ROOT / ".ccc" / "pids"
    metrics = {
        "updated_at": now_iso(),
        "tasks_in_flight": len(list_tasks("in_progress")) + len(list_tasks("testing")),
        "abnormal_count": len(list_tasks("abnormal")),
        "pids_count": len(list(pid_dir.glob("*.pid"))) if pid_dir.exists() else 0,
        "alerts_today": len(list((Path.home() / ".ccc" / "alerts").glob("*-L*.md"))),
        "launchd_missing": health["launchd_missing"],
    }
    metrics_file = ROOT / ".ccc" / "metrics.json"
    metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")

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
            print(
                f"[kb] {task_id} git push 失败 rc={push_r.returncode}", file=sys.stderr
            )
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
            ["git", "diff", "HEAD", "--stat"],
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
                [
                    "bash",
                    str(CCC_HOME / "scripts" / "ccc-notify.sh"),
                    "L2",
                    bug_title,
                    bug_desc[:200],
                ],
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


def get_timeline(task_id: Optional[str] = None) -> list[dict]:
    """读取 timeline 事件（委托 FileBoardStore）"""
    return store.get_timeline(task_id)


def approve_agents() -> dict:
    """人类审批: 读 pending-agents-suggestions.md → 追加到 .ccc/AGENTS.md"""
    import re

    pending_file = ROOT / ".ccc" / "pending-agents-suggestions.md"
    if not pending_file.exists():
        msg = f"[approve-agents] 无待审批建议文件: {pending_file}"
        print(msg)
        return {"role": "approve-agents", "approved": 0, "error": "no pending file"}

    content = pending_file.read_text()

    # 分割：migration_idx 之前是建议块，之后是迁移记录
    migration_idx = content.find("\n## 迁移记录")
    suggestions_text = content[:migration_idx] if migration_idx != -1 else content

    # 按 ## 来源 task: 分割每个建议块
    raw_blocks = re.split(r"\n(?=## 来源 task:)", suggestions_text)
    suggestions = []
    for block in raw_blocks:
        block = block.strip()
        if not block or block.startswith("# Pending") or block.startswith("> "):
            continue

        task_m = re.search(r"## 来源 task:\s*(\S+)", block)
        source_m = re.search(r"### 来自\s+(\w+)", block)
        if not task_m or not source_m:
            continue
        task_id = task_m.group(1)
        source = source_m.group(1)

        # 提取 ### 来自 <source> 之后到 --- 之前的内容
        after_source = block.split(f"### 来自 {source}")[-1].strip()
        content_text = re.split(r"\n---|\n## ", after_source)[0].strip()
        if content_text:
            suggestions.append(
                {
                    "task_id": task_id,
                    "source": source,
                    "content": content_text,
                }
            )

    if not suggestions:
        print("[approve-agents] 无新建议需审批")
        return {"role": "approve-agents", "approved": 0, "info": "nothing new"}

    # 写入/追加 .ccc/AGENTS.md
    agents_file = ROOT / ".ccc" / "AGENTS.md"
    if not agents_file.exists():
        template_file = ROOT / "templates" / "AGENTS.md"
        if template_file.exists():
            agents_content = template_file.read_text()
            profile_file = ROOT / ".ccc" / "profile.md"
            if profile_file.exists():
                pf = profile_file.read_text()
                name_m = re.search(r"项目名[：:]\s*(.+)", pf)
                if name_m:
                    agents_content = agents_content.replace(
                        "{{PROJECT_NAME}}", name_m.group(1).strip()
                    )
            agents_content = agents_content.replace("{{PROJECT_PATH}}", str(ROOT))
            agents_content = agents_content.replace(
                "{{PRIMARY_LANGUAGE}}", "Python+Bash"
            )
            agents_content = agents_content.replace("{{DATE}}", now_iso()[:10])
        else:
            agents_content = "# CCC Agent Guide\n"
        agents_file.write_text(agents_content + "\n\n## AGENTS.md 建议积累\n\n")
        print(f"[approve-agents] 创建 {agents_file}")

    existing = agents_file.read_text().rstrip()
    new_entries = []
    for s in suggestions:
        entry = f"### 来自 {s['source']} ({s['task_id']})\n\n{s['content']}\n"
        new_entries.append(entry)
    agents_file.write_text(existing + "\n" + "\n".join(new_entries) + "\n")

    # 从 pending 文件中移除已审批的建议块（保留 header + 迁移记录）
    now = now_iso()[:10]
    n = len(suggestions)
    # 提取 header（截止到第一个建议块之前）
    header_lines = []
    for line in content.split("\n"):
        if line.strip().startswith("## 来源 task:") or line.strip().startswith("---"):
            break
        header_lines.append(line)
    header = "\n".join(header_lines).rstrip()

    migration_line = f"| {now} | approve-agents | ✅ (已写入 {n} 条) | 自动审批 |\n"
    if migration_idx != -1:
        existing_migration = content[migration_idx:].rstrip()
        pending_file.write_text(
            header + "\n\n" + existing_migration + "\n" + migration_line
        )
    else:
        pending_file.write_text(
            header
            + "\n\n## 迁移记录\n\n"
            + "| 日期 | 迁移人 | 写入 AGENTS.md? | 备注 |\n"
            + "|------|--------|----------------|------|\n"
            + migration_line
        )

    print(f"[approve-agents] ✓ {n} 条建议已写入 {agents_file}")
    return {"role": "approve-agents", "approved": n, "file": str(agents_file)}


# ═══════════════════════════════════════════
# 引擎辅助函数 (v0.20.1)
# ═══════════════════════════════════════════


def dev_role_launch(task_id: str) -> dict:
    """引擎用：启 opencode 执行 task，返回启动结果

    1. 确认 task 在 planned，有 plan+phases
    2. 挪 planned → in_progress
    3. 启 opencode-runner.sh（后台进程）
    4. 不等待，立即返回
    """

    planned = list_tasks("planned")
    task = next((t for t in planned if t["id"] == task_id), None)
    if not task:
        return {"error": f"task '{task_id}' not in planned", "task_id": task_id}

    cplan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    cphases = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not cplan.exists() or not cphases.exists():
        _quarantine(task_id, "engine: 缺 plan 或 phases 文件")
        return {"error": f"task '{task_id}' missing plan/phases, quarantined", "task_id": task_id}

    move_task(task_id, "planned", "in_progress")

    # 从 phases.json 读 timeout
    timeout_s = _load_timeout(cphases, default=600)
    phase_id = f"{task_id}-p1"
    plan_content = cplan.read_text()
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

    pids_dir = ROOT / ".ccc" / "pids"
    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    import subprocess as sp
    proc = sp.Popen(
        [
            str(CCC_HOME / "scripts" / "opencode-runner.sh"),
            task_id,
            str(CCC_HOME),  # ★ CCC_HOME（opencode-exec.py 所在目录）
            "--phase", phase_id,
            "--prompt", prompt_file,
            "--timeout", str(timeout_s),
            "--cwd", str(ROOT),  # opencode 工作目录 = workspace
        ],
        start_new_session=True,
    )
    pids_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
    print(f"[engine] {task_id} launched PID={proc.pid}")

    return {"ok": True, "task_id": task_id, "pid": proc.pid}


def dev_role_relaunch(task_id: str) -> dict:
    """引擎用：失败重试时重新启 opencode（task 已在 in_progress 不挪列）

    与 dev_role_launch 的区别：
    - 不检查 planned，直接读 plan+phases
    - 不挪列（已在 in_progress）
    - 清理旧的 .done/exitcode 后重新启动
    """

    cplan = ROOT / ".ccc" / "plans" / f"{task_id}.plan.md"
    cphases = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
    if not cplan.exists() or not cphases.exists():
        _quarantine(task_id, "engine relaunch: 缺 plan 或 phases 文件")
        return {"error": f"task '{task_id}' missing plan/phases", "task_id": task_id}

    # 清理旧的标记文件
    pids_dir = ROOT / ".ccc" / "pids"
    for suffix in [".done", ".exitcode", ".pid", ".prompt.md", ".result.json"]:
        f = pids_dir / f"{task_id}{suffix}"
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass
        # 也检查 reports/
        f2 = ROOT / ".ccc" / "reports" / f"{task_id}{suffix}"
        if f2.exists():
            try:
                f2.unlink()
            except OSError:
                pass

    timeout_s = _load_timeout(cphases, default=600)
    phase_id = f"{task_id}-p1"
    plan_content = cplan.read_text()
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

    pids_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = str(pids_dir / f"{task_id}.prompt.md")
    Path(prompt_file).write_text(prompt)

    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    import subprocess as sp
    proc = sp.Popen(
        [
            str(CCC_HOME / "scripts" / "opencode-runner.sh"),
            task_id,
            str(CCC_HOME),  # ★ CCC_HOME
            "--phase", phase_id,
            "--prompt", prompt_file,
            "--timeout", str(timeout_s),
            "--cwd", str(ROOT),
        ],
        start_new_session=True,
    )
    pids_dir.joinpath(f"{task_id}.pid").write_text(str(proc.pid))
    print(f"[engine] {task_id} relaunched PID={proc.pid}")

    return {"ok": True, "task_id": task_id, "pid": proc.pid}


def dev_role_check_complete(task_id: str) -> dict:
    """引擎用：检查 task 的 opencode 是否完成

    返回:
      {"status": "running"} — 仍在跑
      {"status": "success"} — 完成，已从 in_progress 移到 testing
      {"status": "failed", "retry": N} — 可重试
      {"status": "quarantined"} — 重试耗尽，已隔离
      {"status": "not_found"} — task 不在 in_progress
    """
    in_prog = list_tasks("in_progress")
    if not any(t["id"] == task_id for t in in_prog):
        return {"status": "not_found", "task_id": task_id}

    done_path = ROOT / ".ccc" / "pids" / f"{task_id}.done"
    if not done_path.exists():
        return {"status": "running", "task_id": task_id}

    exitcode_path = ROOT / ".ccc" / "pids" / f"{task_id}.exitcode"
    result_path = ROOT / ".ccc" / "reports" / f"{task_id}.result.json"
    exit_code = exitcode_path.read_text().strip() if exitcode_path.exists() else "?"
    result_raw = result_path.read_text() if result_path.exists() else "{}"

    report_dir = ROOT / ".ccc" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_dir.joinpath(f"{task_id}.report.md").write_text(
        f"# {task_id} 执行报告\n\n## 信息\n- Phase: {task_id}-p1\n"
        f"- 退出码: {exit_code}\n\n## 输出\n```\n{result_raw[:2000]}\n```\n"
    )

    # 标记文件列表（用于清算）
    marker_files = [
        done_path, exitcode_path,
        ROOT / ".ccc" / "pids" / f"{task_id}.pid",
        ROOT / ".ccc" / "pids" / f"{task_id}.prompt.md",
        result_path,
    ]

    if exit_code == "0":
        # 成功：清标记文件 + 挪列
        for p in marker_files:
            try:
                p.unlink()
            except OSError:
                pass
        move_task(task_id, "in_progress", "testing")
        print(f"[engine] {task_id} ✓ moved to testing")
        return {"status": "success", "task_id": task_id}
    else:
        # 失败：读 retry 计数，保留 .done 文件供 engine 下次 check
        phases_file = ROOT / ".ccc" / "phases" / f"{task_id}.phases.json"
        retry = 0
        try:
            if phases_file.exists():
                with open(phases_file) as _pf:
                    for _line in _pf:
                        _line = _line.strip()
                        if not _line or not _line.startswith("{"):
                            continue
                        phase = json.loads(_line)
                        if "schema_version" in phase:
                            continue
                        retry = phase.get("retry", 0)
                        break
        except (json.JSONDecodeError, OSError):
            pass

        retry += 1
        # 更新 phases.json retry 计数
        try:
            if phases_file.exists():
                lines = phases_file.read_text().split("\n")
                for i, _line in enumerate(lines):
                    _ls = _line.strip()
                    if not _ls or not _ls.startswith("{"):
                        continue
                    try:
                        phase = json.loads(_ls)
                        if "schema_version" in phase:
                            continue
                        phase["retry"] = retry
                        lines[i] = json.dumps(phase, ensure_ascii=False)
                        break
                    except json.JSONDecodeError:
                        pass
                phases_file.write_text("\n".join(lines))
        except OSError:
            pass

        if retry >= MAX_RETRY:
            # 重试耗尽：清理标记 + 异常隔离
            for p in marker_files:
                try:
                    p.unlink()
                except OSError:
                    pass
            _quarantine(task_id, f"engine: 重试{MAX_RETRY}次全部失败，隔离")
            print(f"[engine] {task_id} retry={retry} >= {MAX_RETRY}, quarantined", file=sys.stderr)
            return {"status": "quarantined", "task_id": task_id}
        else:
            # 保留 .done 在磁盘，engine 下次 check 时看到 failed 状态就会 relaunch
            print(f"[engine] {task_id} rc={exit_code} retry={retry}/{MAX_RETRY}")
            return {"status": "failed", "task_id": task_id, "retry": retry}


ROLES = {
    "product": product_role,
    "dev": dev_role,
    "reviewer": reviewer_role,
    "tester": tester_role,
    "ops": ops_role,
    "kb": kb_role,
    "regress": regress_role,
    "approve-agents": approve_agents,
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
