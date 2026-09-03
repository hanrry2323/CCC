"""测试 D 规范固化回写校验门禁与 P3 空提交信号。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from server.engine.task import State, Work
from server.engine.dispatch import ExecutorRegistry, ExecutorEntry
from server.engine.store import InMemoryBoardStore
from server.engine.main import _dispatch_and_collect, _run_auto_worker, check_writeback_credentials


def test_check_writeback_credentials(tmp_path: Path):
    """测试 check_writeback_credentials 回写区两态校验：
    1. 无回写区 -> 直接放行 (历史构造卡 / 旧卡兼容)
    2. 有回写区且为空 -> 拦截
    3. 有回写区且有内容（自由文本，无需强制 分支=/commit= 行）-> 放行，
       分支/commit 凭证由引擎收单侧分支存在性校验兜底。
    """
    card_file = tmp_path / "xy101-wb.md"

    # 1. 未找到 ## 回写区 -> 放行
    card_file.write_text("# 任务卡 xy101\n", encoding="utf-8")
    ok, err = check_writeback_credentials(card_file, "xy101-wb")
    assert ok is True
    assert err == ""

    # 2. 回写区为空 -> 拦截
    card_file.write_text("# 任务卡 xy101\n## 回写区\n", encoding="utf-8")
    ok, err = check_writeback_credentials(card_file, "xy101-wb")
    assert ok is False
    assert "空回写卡" in err

    # 3. 有内容但缺结构化凭证行 -> 放行（自由文本回写，凭证由分支存在性兜底）
    card_file.write_text(
        "# 任务卡 xy101\n## 回写区\n**执行体**：demo\n已完成，push 到 codex/xy101-wb 分支 Commit: aeb6c89\n",
        encoding="utf-8",
    )
    ok, err = check_writeback_credentials(card_file, "xy101-wb")
    assert ok is True
    assert err == ""

    # 4. 结构化凭证行齐备同样放行
    card_file.write_text(
        "# 任务卡 xy101\n## 回写区\n**执行体**：demo\n分支: codex/xy101-wb\ncommit: aeb6c89\n", encoding="utf-8"
    )
    ok, err = check_writeback_credentials(card_file, "xy101-wb")
    assert ok is True
    assert err == ""


def test_p3_empty_commit_signal_success(tmp_path: Path):
    """测试 P3 空提交信号拦截规则：
    1. returncode=1 且 stdout 含 "nothing to commit" -> 拦截并判成功 (exit 0)
    2. returncode=1 但 stdout 含 "error: failed to push" -> 仍判失败
    """
    card_dir = tmp_path / "docs" / "dispatch" / "xy"
    card_dir.mkdir(parents=True)
    card_file = card_dir / "xy105-empty.md"
    card_file.write_text(
        "# 任务卡 xy105 · 测试\n> 关联：TEST · 执行体：demo · 验收：Codex · 状态：执行中 · 日期：2026-08-08\n",
        encoding="utf-8",
    )

    entry = ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="demo", note="test", command="echo")
    reg = ExecutorRegistry((entry,))

    work = Work(id="xy105", role="开发执行体", state=State.RUNNING, card_path=str(card_file))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "xy105.log"

    # 场景 1：退出码 1 且日志含 "nothing to commit" -> 成功 (不重试不打回)
    with (
        patch("server.git_sync.resolve_repo_root", return_value=Path("/fake/main_repo")),
        patch("subprocess.Popen") as mock_popen,
        patch("server.engine.main.build_command", return_value=["echo", "test"]),
    ):
        # Mock process wait to return 1, writing our empty commit signal right before wait finishes
        proc = MagicMock()

        def fake_wait(timeout=None):
            log_file.write_text(
                "[ccc.engine] start work=xy105 phase=run pid_pending\n"
                "On branch codex/xy105\n"
                "nothing to commit, working tree clean\n",
                encoding="utf-8",
            )
            return 1

        proc.wait.side_effect = fake_wait
        proc.pid = 9999
        mock_popen.return_value = proc

        cfg = {"DISPATCH_DIR": str(tmp_path / "docs" / "dispatch")}
        ok, problems = _dispatch_and_collect(work, registry=reg, cfg=cfg, log_dir=log_dir, timeout=30)

        # V3 起空提交信号判失败打回（不假成功）
        assert ok is False
        assert any("空提交" in p or "退出码非 0" in p for p in problems)

    # 场景 2：退出码 1 且日志含 "error:" 且无空提交信号 -> 仍判失败
    with (
        patch("server.git_sync.resolve_repo_root", return_value=Path("/fake/main_repo")),
        patch("subprocess.Popen") as mock_popen,
        patch("server.engine.main.build_command", return_value=["echo", "test"]),
    ):
        proc = MagicMock()

        def fake_wait(timeout=None):
            log_file.write_text(
                "[ccc.engine] start work=xy105 phase=run pid_pending\nerror: failed to push some refs to github\n",
                encoding="utf-8",
            )
            return 1

        proc.wait.side_effect = fake_wait
        proc.pid = 9999
        mock_popen.return_value = proc

        cfg = {"DISPATCH_DIR": str(tmp_path / "docs" / "dispatch")}
        ok, problems = _dispatch_and_collect(work, registry=reg, cfg=cfg, log_dir=log_dir, timeout=30)

        # 属于真失败，不应被拦截，返回 False
        assert ok is False
        assert any("退出码非 0: 1" in p for p in problems)


def test_writeback_gate_rejected_rules(tmp_path: Path):
    """测试收单阶段空回写及字段缺失打回门禁，以及远端凭证成立时豁免该检查的规则。"""
    # Create the card file under main repo docs/dispatch/xy
    main_dispatch = tmp_path / "main" / "docs" / "dispatch" / "xy"
    main_dispatch.mkdir(parents=True, exist_ok=True)
    card_file = main_dispatch / "xy106-gate.md"

    # 构造空回写卡
    card_file.write_text(
        "# 任务卡 xy106 · 测试\n"
        "> 关联：TEST · 执行体：demo · 验收：Codex · 状态：执行中 · 日期：2026-08-08\n"
        "## 目标\nx\n"
        "## 验收标准\nx\n"
        "## 回写区\n",
        encoding="utf-8",
    )

    entry = ExecutorEntry(
        role="开发执行体",
        category="可后台 CLI",
        binding="demo",
        note="test",
        command="echo",
        worktree_base=str(tmp_path / "wt"),
    )
    reg = ExecutorRegistry((entry,))

    # Worktree path for xy106 is: {worktree_base}-{work_id} -> wt-xy106
    wt_dir = tmp_path / "wt-xy106"
    wt_dispatch = wt_dir / "docs" / "dispatch" / "xy"
    wt_dispatch.mkdir(parents=True, exist_ok=True)
    wt_card_file = wt_dispatch / "xy106-gate.md"
    wt_card_file.write_text(card_file.read_text(encoding="utf-8"), encoding="utf-8")

    work = Work(id="xy106", role="开发执行体", state=State.RUNNING, card_path="docs/dispatch/xy/xy106-gate.md")
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # sidecar 契约（ccc-plan-021）：不存流程终态，判定上次成功靠日志 ok:true 收单证据，
    # 从而跳过重置重建以保持 worktree_path。
    (log_dir / "xy106.log").write_text(json.dumps({"ok": True, "work_id": "xy106"}) + "\n", encoding="utf-8")

    # 1. 模拟 exit 0，且无远端凭证，且回写区空 -> 应被拦截并打回
    with (
        patch("server.git_sync.resolve_repo_root", return_value=tmp_path / "main"),
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
        patch("server.engine.main.build_command", return_value=["echo", "test"]),
    ):
        # show-ref for origin/codex/xy106-gate returns non-zero (remote deleted)
        def fake_run(args, **kwargs):
            m = MagicMock()
            # 2026-08-12 v2：worktree 存在即复用 → rev-parse --git-dir 返回 0（有效 git 工作树）
            if "rev-parse --git-dir" in " ".join(args):
                m.returncode = 0
            else:
                m.returncode = 1
            return m

        mock_run.side_effect = fake_run

        proc = MagicMock()
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        cfg = {"DISPATCH_DIR": str(tmp_path / "main" / "docs" / "dispatch")}
        ok, problems = _dispatch_and_collect(work, registry=reg, cfg=cfg, log_dir=log_dir, timeout=30)

        assert ok is False
        assert any("空回写卡" in p for p in problems)

    # 2. 模拟 exit 0，且远端凭证成立 (machine_audit_passed_text == True) -> 豁免空回写检查
    # 恢复收单日志（测试 1 阶段已把 xy106.log 归档为 run1），保证 worktree 复用路径成立
    (log_dir / "xy106.log").write_text(json.dumps({"ok": True, "work_id": "xy106"}) + "\n", encoding="utf-8")
    with (
        patch("server.git_sync.resolve_repo_root", return_value=tmp_path / "main"),
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
        patch("server.engine.main.build_command", return_value=["echo", "test"]),
    ):
        # git show remote returns card content with audit pass!
        def fake_run(args, **kwargs):
            m = MagicMock()
            if "rev-parse --git-dir" in " ".join(args):
                m.returncode = 0
            elif "git show" in " ".join(args) or "show" in args:
                m.returncode = 0
                # Card on remote branch has machine audit passed
                m.stdout = "# 任务卡 xy106\n## 机审区\n结论：通过\n"
            else:
                m.returncode = 1
            return m

        mock_run.side_effect = fake_run

        proc = MagicMock()
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        cfg = {"DISPATCH_DIR": str(tmp_path / "main" / "docs" / "dispatch")}
        ok, problems = _dispatch_and_collect(work, registry=reg, cfg=cfg, log_dir=log_dir, timeout=30)

        # 有远端凭证护航，忽略本地空回写校验，判定成功！
        assert ok is True
        assert problems == []


def test_run_stage_melt_down_outcome_failed_metric(tmp_path: Path):
    """测试连续失败熔断时，outcome['failed'] = 1 统计字段闭合。"""
    store = InMemoryBoardStore()
    work = Work(id="xy107", role="开发执行体", state=State.RUNNING, card_path="/tmp/xy107.md")
    store.seed(work)

    entry = ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="demo", note="test", command="echo")
    reg = ExecutorRegistry((entry,))

    cfg = {
        "EXECUTOR_INFRA_MAX_STRIKES": "1",  # 1次即熔断以快速测试
    }

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    with (
        patch("server.engine.main._dispatch_and_collect", return_value=(False, ["503 Service Unavailable"])),
        patch("server.engine.main.is_retryable_failure", return_value=(True, "503 Service Unavailable")),
        patch("server.engine.runtime_state.read_card_state", return_value={"xy107": {"infra_count": 0}}),
        patch("server.engine.runtime_state.write_card_state"),
    ):
        outcome = _run_auto_worker(work, reg, store, cfg, log_dir, timeout=30)
        # 验证 熔断打回 时 failed = 1 统计数据闭环
        assert outcome.get("failed") == 1
        assert "infra" not in outcome
        assert work.state == State.REJECTED


def test_verify_maintenance_success(tmp_path: Path):
    card_file = tmp_path / "docs" / "dispatch" / "ccc" / "ccc101-test.md"
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text(
        "# 任务卡 ccc101 · 测试\n"
        "> 关联：ccc-plan-011 · 状态：执行中\n"
        "## 维护区\n"
        "1. **方案同步**：[是]\n"
        "   - 说明：ccc-plan-011\n"
        "2. **教训沉淀**：[有]\n"
        "   - 说明：docs/notes/test-lesson.md\n"
        "3. **档案/README**：[是]\n"
        "   - 说明：docs/projects/ccc/README.md\n"
        "4. **线路图**：[是]\n"
        "   - 说明：docs/roadmap.md\n",
        encoding="utf-8",
    )

    plan_file = tmp_path / "docs" / "projects" / "ccc" / "plans" / "011-docgate.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# 方案 · Doc-Gate\n> 状态：部分执行\n> 关联卡：ccc101\n", encoding="utf-8")

    (tmp_path / "docs" / "notes").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "notes" / "test-lesson.md").touch()
    (tmp_path / "docs" / "projects" / "ccc" / "README.md").touch()
    (tmp_path / "docs" / "roadmap.md").touch()

    from server.board.docgate import verify_maintenance

    with patch(
        "server.board.docgate.get_modified_files", return_value=["docs/projects/ccc/README.md", "docs/roadmap.md"]
    ):
        ok, problems = verify_maintenance(card_file, tmp_path)
        assert ok is True
        assert not problems


def test_verify_maintenance_failed_cases(tmp_path: Path):
    card_file = tmp_path / "docs" / "dispatch" / "ccc" / "ccc102-test.md"
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text(
        "# 任务卡 ccc102 · 测试\n"
        "> 关联：ccc-plan-011 · 状态：执行中\n"
        "## 维护区\n"
        "1. **方案同步**：[是]\n"
        "   - 说明：ccc-plan-011\n"
        "2. **教训沉淀**：[有]\n"
        "   - 说明：docs/notes/non-existent.md\n"
        "3. **档案/README**：[是]\n"
        "   - 说明：docs/projects/ccc/README.md\n"
        "4. **线路图**：[是]\n"
        "   - 说明：docs/roadmap.md\n",
        encoding="utf-8",
    )

    plan_file = tmp_path / "docs" / "projects" / "ccc" / "plans" / "011-docgate.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# 方案 · Doc-Gate\n> 状态：草案\n> 关联卡：无\n", encoding="utf-8")

    from server.board.docgate import verify_maintenance

    with patch("server.board.docgate.get_modified_files", return_value=[]):
        ok, problems = verify_maintenance(card_file, tmp_path)
        assert ok is False
        assert any("方案同步" in p for p in problems)
        assert any("Q2 声明的教训文件不存在" in p for p in problems)
        assert any("Q3 声明更新了项目档案" in p for p in problems)
        assert any("Q4 声明更新了线路图" in p for p in problems)


def test_get_modified_files_branch_resolution(tmp_path: Path):
    from server.board.docgate import get_modified_files

    card_file = tmp_path / "docs" / "dispatch" / "ccc" / "ccc101-test.md"
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text("# 任务卡 ccc101\n", encoding="utf-8")

    # 1. Unmerged case: should call merge-base and get diff on mb..branch
    with patch("subprocess.run") as mock_run:
        # Mock subprocess runs
        def fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "rev-parse" in args and "origin/main" in args:
                m.returncode = 0
            elif "show-ref" in args and "origin/codex/ccc101-test" in args:
                m.returncode = 0
            elif "merge-base" in args and "--is-ancestor" in args:
                # Is merged? -> No
                m.returncode = 1
            elif "merge-base" in args:
                m.stdout = "fake_merge_base_hash\n"
            elif "diff" in args and "fake_merge_base_hash..origin/codex/ccc101-test" in args:
                m.stdout = "docs/projects/ccc/README.md\ndocs/roadmap.md\n"
            return m

        mock_run.side_effect = fake_run

        res = get_modified_files(tmp_path, card_file)
        assert "docs/projects/ccc/README.md" in res
        assert "docs/roadmap.md" in res

    # 2. Merged case (regression case for ccc040): should grep card ID and diff oldest_commit^..branch
    with patch("subprocess.run") as mock_run:

        def fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "rev-parse" in args and "origin/main" in args:
                m.returncode = 0
            elif "show-ref" in args and "origin/codex/ccc101-test" in args:
                m.returncode = 0
            elif "merge-base" in args and "--is-ancestor" in args:
                # Is merged? -> Yes
                m.returncode = 0
            elif "log" in args and "--grep=ccc101" in args:
                m.stdout = "commit_1_hash\ncommit_2_hash\n"
            elif "diff" in args and "commit_2_hash^..origin/codex/ccc101-test" in args:
                m.stdout = "docs/projects/ccc/README.md\n"
            return m

        mock_run.side_effect = fake_run

        res = get_modified_files(tmp_path, card_file)
        assert res == ["docs/projects/ccc/README.md"]


# ── A2 引擎代写执行结果（2026-09-03 产线整备）──

def _a2_card_text() -> str:
    return (
        "# 任务卡 tst904 · smoke: a2 代写\n"
        "> 关联：TEST · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：tst · 日期：2026-09-03\n"
        "## 目标\n占位\n"
        "## 回写区\n\n**执行体**：DSH · 日期：\n"
        "## 维护区\n\n1. **方案同步**：是/否\n"
        "2. **教训沉淀**：有/无\n"
    )


def _a2_result_text() -> str:
    return (
        "# 执行结果 · tst904 · smoke: a2 代写\n"
        "## 0. 卡标题复述\n\ntst904 · smoke: a2 代写\n"
        "## 1. 探针输出\n\n- exit_code=0\n- PASS\n"
        "## 2. 自测输出\n\n- 8 passed\n"
        "## 3. 维护区四问\n\n"
        "1. 方案同步：[否] 无关联方案\n"
        "2. 教训沉淀：[无] 探针卡\n"
        "3. 档案/README：[否] 无结构变更\n"
        "4. 线路图：[否] 无变化\n"
        "## 4. 变更证据\n\ncommit=abc branch=codex/x push=success\n"
    )


def test_apply_executor_result_to_card_appends_annotation_fulfillment(tmp_path, monkeypatch):
    """P1：卡含「## 人工批注」节时，A2 代写同步补「## 批注落实」（card-validate 必过）。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst905-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(
        _a2_card_text().replace("tst904", "tst905")
        + "\n## 人工批注\n\n（无批注。）\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "logs" / "tst905-ccc-result.md"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(_a2_result_text().replace("tst904", "tst905"), encoding="utf-8")
    work = Work(id="tst905", role="开发执行体", card_path=str(card_path))

    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    monkeypatch.setattr("server.engine.main.subprocess.run", lambda cmd, **kw: MagicMock(returncode=1 if "--quiet" in cmd else 0))

    ok, err = _apply_executor_result_to_card(work, result_path, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    text = card_path.read_text(encoding="utf-8")
    assert "## 批注落实" in text
    assert "无批注，无需落实" in text or "批注" in text.split("## 批注落实", 1)[1]


def test_apply_executor_result_to_card_rewrites_card(tmp_path, monkeypatch):
    """A2：.ccc-result.md 存在且契约完整 → 引擎代写主仓卡：状态已回写 + 回写区 + 维护区。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst904-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text(), encoding="utf-8")

    result_path = tmp_path / "logs" / "tst904-ccc-result.md"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(_a2_result_text(), encoding="utf-8")

    work = Work(id="tst904", role="开发执行体", card_path=str(card_path))

    # 让 resolve_repo_root 指向 tmp（非 git 也够），且 subprocess git 全 mock 成功
    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        m = MagicMock()
        m.returncode = 1 if "--quiet" in cmd else 0
        return m

    monkeypatch.setattr("server.engine.main.subprocess.run", fake_run)

    ok, err = _apply_executor_result_to_card(work, result_path, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err

    text = card_path.read_text(encoding="utf-8")
    assert "状态：已回写" in text, text
    assert "## 回写区" in text
    assert "## 0. 卡标题复述" in text
    assert "tst904 · smoke: a2 代写" in text
    assert "## 维护区" in text
    assert "方案同步：[否] 无关联方案" in text
    # 引擎随后做了 git add/commit/push
    assert captured["cmd"] is not None


def test_apply_executor_result_title_sample_is_accepted(tmp_path, monkeypatch):
    """A1 实际结果格式：标题段可含自然语言，只要出现卡号即可通过。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst905-sample.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text().replace("tst904", "tst905"), encoding="utf-8")
    result_path = tmp_path / "logs" / "tst905-ccc-result.md"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        _a2_result_text().replace("tst904", "执行结果已完成：tst905 · smoke: A1-A2 clean full-probe"),
        encoding="utf-8",
    )
    work = Work(id="tst905", role="开发执行体", card_path=str(card_path))
    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    def fake_run(*args, **kwargs):
        command = args[0] if args else []
        return MagicMock(returncode=1 if "--quiet" in command else 0)

    monkeypatch.setattr("server.engine.main.subprocess.run", fake_run)
    ok, err = _apply_executor_result_to_card(work, result_path, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    assert "执行结果已完成" in card_path.read_text(encoding="utf-8")


def test_apply_executor_result_refreshes_index_before_commit(tmp_path, monkeypatch):
    """A2：唯一索引刷新发生在 git commit 之前。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst906-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text().replace("tst904", "tst906"), encoding="utf-8")
    result_path = tmp_path / "logs" / "tst906-ccc-result.md"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(_a2_result_text().replace("tst904", "tst906"), encoding="utf-8")
    work = Work(id="tst906", role="开发执行体", card_path=str(card_path))
    monkeypatch.setattr("server.git_sync.resolve_repo_root", lambda *a, **k: tmp_path)
    calls = []

    def fake_load(_path, **_kwargs):
        calls.append("refresh")
        return []

    monkeypatch.setattr("server.board.loader.load_dispatch_cards", fake_load)
    index_path = tmp_path / "cards.index.jsonl"
    index_path.write_text("", encoding="utf-8")
    monkeypatch.setattr("server.board.loader.get_index_path", lambda _path: index_path)

    def fake_run(cmd, **kwargs):
        calls.append(cmd[1] if len(cmd) > 1 else cmd[0])
        # git diff --quiet 返回 1 表示卡面存在待提交变更。
        return MagicMock(returncode=1 if "--quiet" in cmd else 0)

    monkeypatch.setattr("server.engine.main.subprocess.run", fake_run)
    # B1：卡状态 commit 已收口到 CardStateStore，不再由 main.py 直接调用 subprocess。
    def fake_store_run(cmd, **kwargs):
        calls.append(cmd[3] if len(cmd) > 3 else cmd[-1])
        # 让 git show 远端复核时模拟返回与本地写入后一致的 mock 数据，避免 reverify_remote 阻断
        if "show" in cmd:
            return MagicMock(returncode=0, stdout=card_path.read_text(encoding="utf-8"))
        return MagicMock(returncode=0, stdout="main\n")

    monkeypatch.setattr("server.engine.card_state_store.subprocess.run", fake_store_run)
    ok, err = _apply_executor_result_to_card(work, result_path, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok, err
    assert "refresh" in calls
    assert calls.index("refresh") < calls.index("commit")


def test_apply_executor_result_to_card_missing_contract(tmp_path, monkeypatch):
    """A2：结果文件缺契约段 → 不代写，返回错误。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst904b-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text(), encoding="utf-8")

    result_path = tmp_path / "logs" / "tst904b-ccc-result.md"
    result_path.parent.mkdir(parents=True)
    result_path.write_text("# 执行结果 · tst904b\n## 1. 探针输出\n\nok\n", encoding="utf-8")

    work = Work(id="tst904b", role="开发执行体", card_path=str(card_path))
    ok, err = _apply_executor_result_to_card(work, result_path, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok is False
    assert "契约不完整" in err

    # 卡未被改写
    assert "状态：待分派" in card_path.read_text(encoding="utf-8")


def test_apply_executor_result_to_card_missing_result(tmp_path):
    """A2：结果文件不存在 → 返回失败（空转嫌疑），不代写。"""
    from server.engine.main import _apply_executor_result_to_card
    from server.engine.task import Work

    card_path = tmp_path / "docs" / "dispatch" / "tst" / "tst904c-smoke.md"
    card_path.parent.mkdir(parents=True)
    card_path.write_text(_a2_card_text(), encoding="utf-8")

    missing = tmp_path / "logs" / "tst904c-ccc-result.md"
    work = Work(id="tst904c", role="开发执行体", card_path=str(card_path))
    ok, err = _apply_executor_result_to_card(work, missing, {"DISPATCH_DIR": "docs/dispatch"})
    assert ok is False
    assert "未产出结果文件" in err
