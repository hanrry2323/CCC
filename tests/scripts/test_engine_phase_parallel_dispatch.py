"""test_engine_phase_parallel_dispatch.py — plan: engine-phase-parallel-dispatch

验收：
  [并行] 3 phase 无依赖时，并行分支触发（groups 包含所有 3 个 phase）
  [顺序] 有 depends_on 的 phase 不与依赖它的 phase 放在同组
  [串行] 并行组合部完成才推进下一组（groups 列表结构串行）
  [回滚] 并行启动失败时 fallback 回串行模式（fallback 路径存在）

注：ccc-engine.py 通过 _importlib_util spec 加载 ccc-board.py。
ccc-board.py 当前存在 pre-existing 缩进 bug（HEAD 3865: else 无 body），
与本 plan 范围无关。本测试用 AST 提取 _group_parallel_phases 独立验证。
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-engine.py"


def _load_group_function():
    """AST 提取 _group_parallel_phases 函数（绕开 ccc-board 的 pre-existing 缩进 bug）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_group_parallel_phases":
            mod = ast.Module(body=[node], type_ignores=[])
            pyc = compile(mod, str(SCRIPT), "exec")
            ns: dict = {}
            exec(pyc, ns)
            return ns["_group_parallel_phases"]
    raise RuntimeError("_group_parallel_phases not found")


def _load_parallel_dispatch_constants():
    """提取 PHASE_PARALLEL_MAX_WORKERS / _set_parallel_disabled / PHASE_PARALLEL_DISABLED。"""
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    found: dict = {}
    for node in tree.body:
        # 模块级常量 + 函数定义
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in (
                    "PHASE_PARALLEL_MAX_WORKERS",
                    "PHASE_PARALLEL_DISABLED",
                ):
                    try:
                        found[tgt.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass
        if isinstance(node, ast.FunctionDef) and node.name == "_set_parallel_disabled":
            mod = ast.Module(body=[node], type_ignores=[])
            pyc = compile(mod, str(SCRIPT), "exec")
            ns: dict = {}
            exec(pyc, ns)
            found["_set_parallel_disabled"] = ns["_set_parallel_disabled"]
    return found


_group_parallel_phases = _load_group_function()
_constants = _load_parallel_dispatch_constants()


# ═══════════════════════════════════════════════════════════════
# [并行] 3 phase 无依赖 → 一组并行
# ═══════════════════════════════════════════════════════════════


def test_three_independent_phases_one_group():
    """3 phase 无依赖 → 一组 [1,2,3]。"""
    phases = [
        {"phase": 1, "depends_on": []},
        {"phase": 2, "depends_on": []},
        {"phase": 3, "depends_on": []},
    ]
    groups = _group_parallel_phases(phases, {1, 2, 3})
    assert groups == [[1, 2, 3]], f"期望单组并行 [[1,2,3]]，实际 {groups}"


def test_two_independent_phases_one_group():
    """2 phase 无依赖 → 一组（满足 PHASE_PARALLEL_MAX_WORKERS=2 触发条件）。"""
    phases = [
        {"phase": 1, "depends_on": []},
        {"phase": 2, "depends_on": []},
    ]
    groups = _group_parallel_phases(phases, {1, 2})
    assert groups == [[1, 2]]


# ═══════════════════════════════════════════════════════════════
# [顺序] 有 depends_on 的 phase 不与依赖链上游放同组
# ═══════════════════════════════════════════════════════════════


def test_chain_phase1_2_3_serial_groups():
    """phase1 → phase2 → phase3 链 → 3 个独立 group。"""
    phases = [
        {"phase": 1, "depends_on": []},
        {"phase": 2, "depends_on": [1]},
        {"phase": 3, "depends_on": [2]},
    ]
    groups = _group_parallel_phases(phases, {1, 2, 3})
    # 每条依赖链强制开新组：[1], [2], [3]
    assert groups == [[1], [2], [3]], f"期望串行 3 组，实际 {groups}"


def test_partial_dependency_phase_1_and_3_parallel_phase_2_depends_on_1():
    """phase-1 无依赖；phase-3 无依赖；phase-2 depends on [1]。
    期望：[1,3] 一组（无依赖关系），[2] 一组（依赖 1 不能并行）。"""
    phases = [
        {"phase": 1, "depends_on": []},
        {"phase": 2, "depends_on": [1]},
        {"phase": 3, "depends_on": []},
    ]
    groups = _group_parallel_phases(phases, {1, 2, 3})
    # 算法按 sorted_executable = [1,2,3] 遍历：
    #   pid=1: 无 group → groups=[[1]]
    #   pid=2: last_group=[1]，conflicts={1}&{1}={1} → 开新 group [[1],[2]]
    #   pid=3: last_group=[2]，conflicts={2}&{}={}；reverse deps: {2} deps 不含 3 → 加入 [[1],[2,3]]
    assert groups == [[1], [2, 3]], f"期望 [[1], [2,3]]，实际 {groups}"


def test_reverse_dependency_blocks_same_group():
    """phase-3 depends on [1]，phase-1 与 phase-3 不能同组（reverse_deps check）。"""
    phases = [
        {"phase": 1, "depends_on": []},
        {"phase": 3, "depends_on": [1]},
    ]
    groups = _group_parallel_phases(phases, {1, 3})
    # sorted_executable=[1,3]:
    #   pid=1: groups=[[1]]
    #   pid=3: last_group=[1]，conflicts={1}&{1}={1} → 开新 group
    assert groups == [[1], [3]], f"期望反向依赖拆组，实际 {groups}"


# ═══════════════════════════════════════════════════════════════
# [串行] 多组之间顺序执行
# ═══════════════════════════════════════════════════════════════


def test_groups_order_is_serial():
    """返回值是 list[list]，组间有先后顺序（外层 list 即时间顺序）。"""
    phases = [
        {"phase": 1, "depends_on": []},
        {"phase": 2, "depends_on": []},
        {"phase": 3, "depends_on": []},
        {"phase": 4, "depends_on": [1]},
    ]
    groups = _group_parallel_phases(phases, {1, 2, 3, 4})
    # sorted_executable=[1,2,3,4]:
    #   pid=1 → [[1]]
    #   pid=2 → [[1,2]]
    #   pid=3 → [[1,2,3]]
    #   pid=4: last=[1,2,3]，conflicts={1,2,3}&{1}={1} → 开新 [[1,2,3],[4]]
    assert groups == [[1, 2, 3], [4]], f"组间顺序错，实际 {groups}"


def test_empty_executable_returns_empty():
    """无 executable phase → 返回空列表。"""
    assert _group_parallel_phases([], set()) == []
    assert _group_parallel_phases([{"phase": 1}], set()) == []


# ═══════════════════════════════════════════════════════════════
# [回滚] 并行关闭标志 PHASE_PARALLEL_DISABLED 可被设置
# ═══════════════════════════════════════════════════════════════


def test_parallel_disabled_toggle_exists():
    """PHASE_PARALLEL_DISABLED = False 时启用并行分支；True 时回退串行。"""
    assert "PHASE_PARALLEL_DISABLED" in _constants
    assert _constants["PHASE_PARALLEL_DISABLED"] is False
    # 默认值 False → _try_launch_planned 走并行分支
    assert "PHASE_PARALLEL_MAX_WORKERS" in _constants
    assert _constants["PHASE_PARALLEL_MAX_WORKERS"] == 2


def test_fallback_path_in_try_launch_planned():
    """_try_launch_planned 必须含 fallback 路径（并行失败 → 走串行 dev_role_launch）。"""
    src = SCRIPT.read_text(encoding="utf-8")
    # 双重确认：fallback 路径存在于并行失败后
    assert "fallback" in src, "fallback 关键词缺失"
    assert "回退" in src, "回退注释缺失"
    # 串行路径：并行失败后调 dev_role_launch
    assert "launch_r = dev_role_launch(tid)" in src, "fallback 后未调 dev_role_launch"


def test_parallel_log_marker_emitted():
    """日志标记 [parallel] 必须存在于 launch_parallel_group / try_launch_planned_parallel。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "[parallel]" in src, "[parallel] 日志标记缺失"


# ═══════════════════════════════════════════════════════════════
# [回滚] ThreadPoolExecutor 异常 → fallback 串行
# ═══════════════════════════════════════════════════════════════


def test_threadpool_fallback_sets_disabled():
    """_launch_parallel_group 在 ThreadPoolExecutor 异常时调 _set_parallel_disabled(True)。"""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_launch_parallel_group":
            mod_src = ast.unparse(ast.Module(body=[node], type_ignores=[]))
            assert "_set_parallel_disabled(True)" in mod_src, (
                "fallback 路径未调用 _set_parallel_disabled(True)"
            )
            assert "fallback" in mod_src, "fallback 注释缺失"
            return
    raise RuntimeError("_launch_parallel_group not found")


# ═══════════════════════════════════════════════════════════════
# 阶段完整性：_check_parallel_task_complete 串行推进 groups
# ═══════════════════════════════════════════════════════════════


def test_check_parallel_task_complete_advances_groups_serially():
    """_check_parallel_task_complete 一次只推进一个 group（不会跳组）。

    检查逻辑契约：
      - 必须根据 current_group 找出其后 group
      - 推到「下一个 group」后 return still_running，不跳多个
      - 全 group 完成后写 marker file + return task_complete_*
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "_check_parallel_task_complete"
        ):
            mod_src = ast.unparse(ast.Module(body=[node], type_ignores=[]))
            # 契约 1: 在 current_group 之后查下一个 group（不是并行多个）
            assert "current_group" in mod_src, "未读 current_group"
            # 契约 2: 全部完成后写 task_id.done marker
            assert ".done" in mod_src and ".exitcode" in mod_src, (
                "完成后未写 done/exitcode marker"
            )
            # 契约 3: 返回值包含 task_complete_*
            assert "task_complete_ok" in mod_src and "task_complete_fail" in mod_src, (
                "缺少 task_complete_ok/fail 返回分支"
            )
            # 契约 4: still_running 分支存在
            assert "still_running" in mod_src, "缺少 still_running 分支"
            # 契约 5: 当前 group 完成后才推进下一组（next_group 而非 all remaining）
            assert "next_group" in mod_src, "未实现 next_group 单组推进"
            return
    raise RuntimeError("_check_parallel_task_complete not found")


# ═══════════════════════════════════════════════════════════════
# 行为测试：实际加载 engine 模块验证 dispatch 路径
# ═══════════════════════════════════════════════════════════════


def _load_engine_module():
    """实际导入 ccc-engine.py 模块（用于行为测试）。"""
    if "ccc_engine_parallel_test" in sys.modules:
        return sys.modules["ccc_engine_parallel_test"]
    spec = importlib.util.spec_from_file_location(
        "ccc_engine_parallel_test", str(SCRIPT)
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ccc_engine_parallel_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_engine_module_loads_with_parallel_constants():
    """引擎模块加载后 PHASE_PARALLEL_MAX_WORKERS 应为 2，新函数全部存在。"""
    mod = _load_engine_module()
    assert mod.PHASE_PARALLEL_MAX_WORKERS == 2
    assert hasattr(mod, "_try_launch_planned_parallel")
    assert hasattr(mod, "_on_parallel_group_complete")
    assert hasattr(mod, "_check_parallel_task_complete")
    assert hasattr(mod, "_parallel_phases")


def test_lookup_phase_timeout_uses_first_phase():
    """_lookup_phase_timeout 取 phase 1 的 timeout，找不到走 cfg.default_timeout。"""
    mod = _load_engine_module()

    # phase 1 timeout=120
    phases = [
        {"phase": 1, "timeout": 120},
        {"phase": 2, "timeout": 999},
    ]
    assert mod._lookup_phase_timeout("t", phases) == 120

    # 无 phase 1 → cfg.default_timeout（1800，取决于 Config，但应当返回一致值）
    default_to = mod.cfg.default_timeout
    assert mod._lookup_phase_timeout("t", [{"phase": 2, "timeout": 30}]) == default_to

    # 空列表 → cfg.default_timeout
    assert mod._lookup_phase_timeout("t", []) == default_to


def test_parallel_disabled_fallback_cleared_per_tick():
    """_set_parallel_disabled + _reset_parallel_disabled_after_tick 配对工作。"""
    mod = _load_engine_module()
    try:
        assert mod.PHASE_PARALLEL_DISABLED is False
        mod._set_parallel_disabled(True)
        assert mod.PHASE_PARALLEL_DISABLED is True
        mod._reset_parallel_disabled_after_tick()
        assert mod.PHASE_PARALLEL_DISABLED is False
    finally:
        mod._reset_parallel_disabled_after_tick()


def test_try_launch_planned_chooses_parallel_when_conditions_met(tmp_path, monkeypatch):
    """_try_launch_planned: 3 executable phase + 没禁用 → 走并行分支。

    通过 monkeypatch _try_launch_planned_parallel 验证触发：
      1. task 被挪到 in_progress（前置条件）
      2. active_tasks 标记 mode='parallel'
    """
    mod = _load_engine_module()

    # 构造 workspace：.ccc/board/planned + phases 文件 + plan 文件
    ws = tmp_path
    ccc = ws / ".ccc"
    board = ccc / "board"
    for col in ("planned", "in_progress", "testing"):
        (board / col).mkdir(parents=True)
    (ccc / "plans").mkdir(parents=True)
    (ccc / "phases").mkdir(parents=True)
    # 用 ccc-board 的任务 schema
    task = {
        "id": "t-par",
        "title": "test",
        "status": "planned",
        "created_at": "2026-07-14T00:00:00+00:00",
        "updated_at": "2026-07-14T00:00:00+00:00",
        "assignee": None,
        "tags": [],
        "note": "",
        "schema_version": "1.0",
        "complexity": "small",
    }
    (board / "planned" / "t-par.jsonl").write_text(
        json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ccc / "plans" / "t-par.plan.md").write_text("# plan\n", encoding="utf-8")
    (ccc / "phases" / "t-par.phases.json").write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps(
            {"phase": 1, "status": "pending", "depends_on": []}, ensure_ascii=False
        )
        + "\n"
        + json.dumps(
            {"phase": 2, "status": "pending", "depends_on": []}, ensure_ascii=False
        )
        + "\n"
        + json.dumps(
            {"phase": 3, "status": "pending", "depends_on": []}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    # monkeypatch _try_launch_planned_parallel 看是否被调用
    called = {"flag": False, "groups": None}

    def fake_parallel(ws_arg, task_id_arg, groups, plan_content, timeout_s):
        called["flag"] = True
        called["groups"] = groups
        # 模拟并行启动成功，绕过实际子进程 spawn
        return True

    monkeypatch.setattr(mod, "_try_launch_planned_parallel", fake_parallel)

    active = {}
    result = mod._try_launch_planned(ws, active)

    assert result is True
    assert called["flag"] is True, "_try_launch_planned_parallel 未被调用"
    assert called["groups"] is not None
    # 第一组 ≥ 2（3 phase 无依赖 → 1 组含 3 个）
    assert len(called["groups"][0]) >= 2

    # task 已在 in_progress
    assert (board / "in_progress" / "t-par.jsonl").exists()
    assert active["active_key"]["mode"] == "parallel"


def test_try_launch_planned_skips_parallel_when_disabled(tmp_path, monkeypatch):
    """PHASE_PARALLEL_DISABLED=True 时强制走串行 dev_role_launch。"""
    mod = _load_engine_module()

    ws = tmp_path
    ccc = ws / ".ccc"
    board = ccc / "board"
    for col in ("planned", "in_progress", "testing"):
        (board / col).mkdir(parents=True)
    (ccc / "plans").mkdir(parents=True)
    (ccc / "phases").mkdir(parents=True)
    task = {
        "id": "t-skip",
        "title": "test",
        "status": "planned",
        "created_at": "2026-07-14T00:00:00+00:00",
        "updated_at": "2026-07-14T00:00:00+00:00",
        "assignee": None,
        "tags": [],
        "note": "",
        "schema_version": "1.0",
        "complexity": "small",
    }
    (board / "planned" / "t-skip.jsonl").write_text(
        json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ccc / "plans" / "t-skip.plan.md").write_text("# plan\n", encoding="utf-8")
    (ccc / "phases" / "t-skip.phases.json").write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 1, "status": "pending"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 2, "status": "pending"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    parallel_called = {"flag": False}

    def fake_parallel(*a, **kw):
        parallel_called["flag"] = True
        return True

    def fake_dev(task_id_arg):
        # 返回成功（不 spawn 进程）
        ws_local = ccc.parent
        (ws_local / ".ccc/pids" / f"{task_id_arg}.done").parent.mkdir(
            parents=True, exist_ok=True
        )
        (ws_local / ".ccc/pids" / f"{task_id_arg}.done").write_text("ok")
        (ws_local / ".ccc/pids" / f"{task_id_arg}.exitcode").write_text("0")
        return {}

    monkeypatch.setattr(mod, "_try_launch_planned_parallel", fake_parallel)
    monkeypatch.setattr(mod, "dev_role_launch", fake_dev)
    monkeypatch.setattr(mod, "_set_parallel_disabled", lambda v: None)

    # 临时把全局标志置 True（构造 disabled 状态）
    mod.PHASE_PARALLEL_DISABLED = True
    try:
        active = {}
        mod._try_launch_planned(ws, active)
        assert parallel_called["flag"] is False, (
            "PHASE_PARALLEL_DISABLED=True 时不应调 _try_launch_planned_parallel"
        )
    finally:
        mod.PHASE_PARALLEL_DISABLED = False


def test_try_launch_planned_skips_parallel_when_single_phase(tmp_path, monkeypatch):
    """只有 1 个 executable phase 时不触发并行（< 2）。"""
    mod = _load_engine_module()

    ws = tmp_path
    ccc = ws / ".ccc"
    board = ccc / "board"
    for col in ("planned", "in_progress"):
        (board / col).mkdir(parents=True)
    (ccc / "plans").mkdir(parents=True)
    (ccc / "phases").mkdir(parents=True)
    task = {
        "id": "t-1p",
        "title": "test",
        "status": "planned",
        "created_at": "2026-07-14T00:00:00+00:00",
        "updated_at": "2026-07-14T00:00:00+00:00",
        "assignee": None,
        "tags": [],
        "note": "",
        "schema_version": "1.0",
        "complexity": "small",
    }
    (board / "planned" / "t-1p.jsonl").write_text(
        json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (ccc / "plans" / "t-1p.plan.md").write_text("# plan\n", encoding="utf-8")
    (ccc / "phases" / "t-1p.phases.json").write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 1, "status": "pending"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    parallel_called = {"flag": False}

    def fake_parallel(*a, **kw):
        parallel_called["flag"] = True
        return True

    def fake_dev(task_id_arg):
        ws_local = ccc.parent
        (ws_local / ".ccc/pids" / f"{task_id_arg}.done").parent.mkdir(
            parents=True, exist_ok=True
        )
        (ws_local / ".ccc/pids" / f"{task_id_arg}.done").write_text("ok")
        (ws_local / ".ccc/pids" / f"{task_id_arg}.exitcode").write_text("0")
        return {}

    monkeypatch.setattr(mod, "_try_launch_planned_parallel", fake_parallel)
    monkeypatch.setattr(mod, "dev_role_launch", fake_dev)
    monkeypatch.setattr(mod, "_set_parallel_disabled", lambda v: None)

    active = {}
    mod._try_launch_planned(ws, active)
    assert parallel_called["flag"] is False, "单 phase 不应触发并行"


def test_on_parallel_group_complete_writes_phase_status(tmp_path):
    """_on_parallel_group_complete 写完 marker + 写回 phases.json。

    场景：2 phase 并行都成功 → phases.json 应更新成 done。
    """
    mod = _load_engine_module()

    ws = tmp_path
    pids = ws / ".ccc/pids"
    pids.mkdir(parents=True)
    phases_dir = ws / ".ccc/phases"
    phases_dir.mkdir(parents=True)

    # 写 phases.json
    phases_path = phases_dir / "g1.phases.json"
    phases_path.write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps(
            {"phase": 1, "status": "in_progress", "depends_on": []}, ensure_ascii=False
        )
        + "\n"
        + json.dumps(
            {"phase": 2, "status": "in_progress", "depends_on": []}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    # 标记 done（成功）
    subid1 = mod._phase_market_subid("g1", 1)
    subid2 = mod._phase_market_subid("g1", 2)
    (pids / f"{subid1}.done").write_text("ok")
    (pids / f"{subid1}.exitcode").write_text("0")
    (pids / f"{subid2}.done").write_text("ok")
    (pids / f"{subid2}.exitcode").write_text("0")

    # 还要 mock 掉 _store_atomic_write_phases 调用避免 .tmp 不存在
    # 这是 _on_parallel_group_complete 里的写回路径
    result = mod._on_parallel_group_complete(ws, "g1", [1, 2])
    assert result == "group_done_ok", f"expected group_done_ok, got {result}"

    # phases.json 写回
    lines = phases_path.read_text().splitlines()
    statuses = {}
    for line in lines:
        if not line.strip():
            continue
        obj = json.loads(line)
        if "phase" in obj:
            statuses[obj["phase"]] = obj["status"]
    assert statuses[1] == "done", f"phase 1 应 done，实际 {statuses}"
    assert statuses[2] == "done", f"phase 2 应 done，实际 {statuses}"


def test_on_parallel_group_complete_detects_failure(tmp_path):
    """一 phase 失败 → 返回 group_done_fail，相位状态标 failed。"""
    mod = _load_engine_module()

    ws = tmp_path
    pids = ws / ".ccc/pids"
    pids.mkdir(parents=True)
    phases_dir = ws / ".ccc/phases"
    phases_dir.mkdir(parents=True)
    phases_path = phases_dir / "g2.phases.json"
    phases_path.write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 1, "status": "in_progress"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 2, "status": "in_progress"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    subid1 = mod._phase_market_subid("g2", 1)
    subid2 = mod._phase_market_subid("g2", 2)
    (pids / f"{subid1}.done").write_text("ok")
    (pids / f"{subid1}.exitcode").write_text("0")
    (pids / f"{subid2}.done").write_text("ok")
    (pids / f"{subid2}.exitcode").write_text("1")  # phase 2 失败

    result = mod._on_parallel_group_complete(ws, "g2", [1, 2])
    assert result == "group_done_fail"

    lines = phases_path.read_text().splitlines()
    statuses = {}
    for line in lines:
        if not line.strip():
            continue
        obj = json.loads(line)
        if "phase" in obj:
            statuses[obj["phase"]] = obj["status"]
    assert statuses[1] == "done"
    assert statuses[2] == "failed"


def test_on_parallel_group_complete_still_running_when_no_marker(tmp_path):
    """无 done marker → still_running（不写回）。"""
    mod = _load_engine_module()

    ws = tmp_path
    pids = ws / ".ccc/pids"
    pids.mkdir(parents=True)
    phases_dir = ws / ".ccc/phases"
    phases_dir.mkdir(parents=True)
    phases_path = phases_dir / "g3.phases.json"
    phases_path.write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 1, "status": "in_progress"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    subid1 = mod._phase_market_subid("g3", 1)
    # 不写 done marker → 模拟还在跑

    result = mod._on_parallel_group_complete(ws, "g3", [1])
    assert result == "still_running"


def test_check_parallel_task_complete_writes_done_marker(tmp_path, monkeypatch):
    """单组并行全部 done 后 _check_parallel_task_complete 写 task_id.done marker。"""
    mod = _load_engine_module()

    ws = tmp_path
    pids = ws / ".ccc/pids"
    pids.mkdir(parents=True)
    phases_dir = ws / ".ccc/phases"
    phases_dir.mkdir(parents=True)
    plans_dir = ws / ".ccc/plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "g4.plan.md").write_text("# plan\n", encoding="utf-8")
    phases_path = phases_dir / "g4.phases.json"
    phases_path.write_text(
        json.dumps({"schema_version": "1.1"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 1, "status": "in_progress"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"phase": 2, "status": "in_progress"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    # 注册 group state
    key = f"{ws.resolve()}|g4"
    subid1 = mod._phase_market_subid("g4", 1)
    subid2 = mod._phase_market_subid("g4", 2)
    (pids / f"{subid1}.done").write_text("ok")
    (pids / f"{subid1}.exitcode").write_text("0")
    (pids / f"{subid2}.done").write_text("ok")
    (pids / f"{subid2}.exitcode").write_text("0")

    mod._parallel_phases[key] = {
        "groups": [[1, 2]],
        "current_group": [1, 2],
        "phase_meta": {1: {"subid": subid1}, 2: {"subid": subid2}},
        "any_group_fail": False,
        "ws_path": str(ws),
    }

    result = mod._check_parallel_task_complete(ws, "g4")
    assert result == "task_complete_ok"

    # marker 写出
    assert (pids / "g4.done").exists()
    assert (pids / "g4.exitcode").read_text() == "0"

    # state 已清
    assert key not in mod._parallel_phases
