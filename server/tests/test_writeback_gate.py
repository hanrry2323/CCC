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
        "# 任务卡 xy101\n"
        "## 回写区\n"
        "**执行体**：demo\n"
        "已完成，push 到 codex/xy101-wb 分支 Commit: aeb6c89\n",
        encoding="utf-8"
    )
    ok, err = check_writeback_credentials(card_file, "xy101-wb")
    assert ok is True
    assert err == ""

    # 4. 结构化凭证行齐备同样放行
    card_file.write_text(
        "# 任务卡 xy101\n"
        "## 回写区\n"
        "**执行体**：demo\n"
        "分支: codex/xy101-wb\n"
        "commit: aeb6c89\n",
        encoding="utf-8"
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
        "# 任务卡 xy105 · 测试\n"
        "> 关联：TEST · 执行体：demo · 验收：Codex · 状态：执行中 · 日期：2026-08-08\n",
        encoding="utf-8"
    )

    entry = ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="demo", note="test", command="echo")
    reg = ExecutorRegistry((entry,))

    work = Work(id="xy105", role="开发执行体", state=State.RUNNING, card_path=str(card_file))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "xy105.log"

    # 场景 1：退出码 1 且日志含 "nothing to commit" -> 成功 (不重试不打回)
    with patch("server.git_sync.resolve_repo_root", return_value=Path("/fake/main_repo")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("server.engine.main.build_command", return_value=["echo", "test"]):

         # Mock process wait to return 1, writing our empty commit signal right before wait finishes
         proc = MagicMock()
         def fake_wait(timeout=None):
             log_file.write_text(
                 "[ccc.engine] start work=xy105 phase=run pid_pending\n"
                 "On branch codex/xy105\n"
                 "nothing to commit, working tree clean\n",
                 encoding="utf-8"
             )
             return 1
         proc.wait.side_effect = fake_wait
         proc.pid = 9999
         mock_popen.return_value = proc

         cfg = {"DISPATCH_DIR": str(tmp_path / "docs" / "dispatch")}
         ok, problems = _dispatch_and_collect(work, registry=reg, cfg=cfg, log_dir=log_dir, timeout=30)

         # 应该被成功拦截并返回 True
         assert ok is True
         assert problems == []


    # 场景 2：退出码 1 且日志含 "error:" 且无空提交信号 -> 仍判失败
    with patch("server.git_sync.resolve_repo_root", return_value=Path("/fake/main_repo")), \
         patch("subprocess.Popen") as mock_popen, \
         patch("server.engine.main.build_command", return_value=["echo", "test"]):

         proc = MagicMock()
         def fake_wait(timeout=None):
             log_file.write_text(
                 "[ccc.engine] start work=xy105 phase=run pid_pending\n"
                 "error: failed to push some refs to github\n",
                 encoding="utf-8"
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
        encoding="utf-8"
    )

    entry = ExecutorEntry(
        role="开发执行体",
        category="可后台 CLI",
        binding="demo",
        note="test",
        command="echo",
        worktree_base=str(tmp_path / "wt")
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

    # 模拟 sidecar 记录该卡已经成功收单，从而跳过重置重建以保持 worktree_path
    from server.engine.runtime_state import write_card_state
    write_card_state(log_dir, "xy106", state="已回写")

    # 1. 模拟 exit 0，且无远端凭证，且回写区空 -> 应被拦截并打回
    with patch("server.git_sync.resolve_repo_root", return_value=tmp_path / "main"), \
         patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen, \
         patch("server.engine.main.build_command", return_value=["echo", "test"]):

         # show-ref for origin/codex/xy106-gate returns non-zero (remote deleted)
         def fake_run(args, **kwargs):
             m = MagicMock()
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
    with patch("server.git_sync.resolve_repo_root", return_value=tmp_path / "main"), \
         patch("subprocess.run") as mock_run, \
         patch("subprocess.Popen") as mock_popen, \
         patch("server.engine.main.build_command", return_value=["echo", "test"]):

         # git show remote returns card content with audit pass!
         def fake_run(args, **kwargs):
             m = MagicMock()
             if "git show" in " ".join(args) or "show" in args:
                 m.returncode = 0
                 # Card on remote branch has machine audit passed
                 m.stdout = (
                     "# 任务卡 xy106\n"
                     "## 机审区\n"
                     "结论：通过\n"
                 )
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
        "EXECUTOR_INFRA_MAX_STRIKES": "1", # 1次即熔断以快速测试
    }

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    with patch("server.engine.main._dispatch_and_collect", return_value=(False, ["503 Service Unavailable"])), \
         patch("server.engine.main.is_retryable_failure", return_value=(True, "503 Service Unavailable")), \
         patch("server.engine.runtime_state.read_card_state", return_value={"xy107": {"infra_count": 0}}), \
         patch("server.engine.runtime_state.write_card_state"):

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
        encoding="utf-8"
    )

    plan_file = tmp_path / "docs" / "projects" / "ccc" / "plans" / "011-docgate.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "# 方案 · Doc-Gate\n"
        "> 状态：部分执行\n"
        "> 关联卡：ccc101\n",
        encoding="utf-8"
    )

    (tmp_path / "docs" / "notes").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "notes" / "test-lesson.md").touch()
    (tmp_path / "docs" / "projects" / "ccc" / "README.md").touch()
    (tmp_path / "docs" / "roadmap.md").touch()

    from server.board.docgate import verify_maintenance

    with patch("server.board.docgate.get_modified_files", return_value=["docs/projects/ccc/README.md", "docs/roadmap.md"]):
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
        encoding="utf-8"
    )

    plan_file = tmp_path / "docs" / "projects" / "ccc" / "plans" / "011-docgate.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "# 方案 · Doc-Gate\n"
        "> 状态：草案\n"
        "> 关联卡：无\n",
        encoding="utf-8"
    )

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
