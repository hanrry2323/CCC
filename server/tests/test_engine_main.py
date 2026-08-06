"""test_engine_main — 入口冒烟 + 真实派发/收单闭环。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from server.config.loader import ConfigError
from server.engine.dispatch import load_registry
from server.engine.main import main, run_once
from server.engine.pool import reset_dispatch_pool
from server.engine.store import FileBoardStore, InMemoryBoardStore
from server.engine.task import State, Work


@pytest.fixture(autouse=True)
def _reset_engine_dispatch_pool() -> None:
    """避免跨用例残留在途线程/占槽。"""
    reset_dispatch_pool()
    yield
    reset_dispatch_pool()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "server" / "config" / "executors.example.json"


def _write_env(tmp_path: Path, registry_path: Path | str, **overrides: str) -> str:
    """写一份可用的 config.env（测试夹具；字面值仅属测试数据）。"""
    lines = [
        "ENGINE_PORT=8101",
        "BOARD_PORT=8102",
        "WEB_PORT=8103",
        "RELAY_PORT=8104",
        f"DATA_DIR={overrides.get('DATA_DIR', '/tmp/ccc2/data')}",
        f"LOG_DIR={overrides.get('LOG_DIR', '/tmp/ccc2/logs')}",
        "RELAY_UPSTREAM_URL=http://example.com/v1",
        f"EXECUTOR_REGISTRY_PATH={registry_path}",
        f"EXECUTOR_TIMEOUT_SECONDS={overrides.get('EXECUTOR_TIMEOUT_SECONDS', '300')}",
        f"EXECUTOR_LOG_DIR={overrides.get('EXECUTOR_LOG_DIR', str(tmp_path / 'exec-logs'))}",
        f"DISPATCH_DIR={overrides.get('DISPATCH_DIR', str(tmp_path / 'dispatch'))}",
    ]
    env = tmp_path / "config.env"
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(env)


def _write_demo_registry(
    tmp_path: Path,
    command: str = "echo",
    args_template: str = "work={work_id} card={card_path}",
    worktree_base: str = "",
) -> Path:
    """写临时 executors.json（演示用占位命令，禁止生产引用）。"""
    p = tmp_path / "executors.json"
    p.write_text(
        json.dumps(
            {
                "version": "2",
                "executors": [
                    {
                        "角色": "开发执行体",
                        "分类": "可后台 CLI",
                        "当前绑定": "demo",
                        "命令": command,
                        "参数模板": args_template,
                        "工作目录": "",
                        "worktree_base": worktree_base,
                        "备注": "测试夹具",
                    },
                    {
                        "角色": "管理席",
                        "分类": "—",
                        "当前绑定": "demo",
                        "命令": "",
                        "参数模板": "",
                        "工作目录": "",
                        "备注": "",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return p


class TestMainCli:
    """CLI 行为。"""

    def test_missing_config_argument(self) -> None:
        """缺 --config：argparse 以退出码 2 报错。"""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_config_file_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--config 指向不存在的文件：退出码 2 + FATAL 报错。"""
        code = main(["--config", "/tmp/nonexistent_cfg_xyz.env", "--once"])
        assert code == 2
        assert "FATAL" in capsys.readouterr().err

    def test_once_smoke(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """--once 有配置但空板：退出码 0，输出一行 JSON 统计。"""
        reg = _write_demo_registry(tmp_path)
        env = _write_env(tmp_path, reg)
        code = main(["--config", env, "--once"])
        out = capsys.readouterr().out
        assert code == 0
        summary = json.loads(out)
        assert summary["mode"] == "once"
        assert summary["scanned"] == 0
        assert summary["dispatched"] == 0
        assert summary["in_flight"] == 0
        assert summary["collected"] == 0
        assert summary["timed_out"] == 0


class TestRunOnceRealDispatch:
    """真实派发 + 收单闭环（用 echo / 临时注册表）。"""

    def test_executor_log_dir_required(self, tmp_path: Path) -> None:
        """P2-3：EXECUTOR_LOG_DIR 未配置 → 抛 ConfigError（无默认值，零硬编码）。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w0", role="开发执行体", card_path=str(tmp_path / "card.md")))
        cfg = {"DATA_DIR": str(tmp_path)}  # 故意不传 EXECUTOR_LOG_DIR
        with pytest.raises(ConfigError, match="EXECUTOR_LOG_DIR"):
            run_once(reg, store, cfg)

    def test_exit_zero_collected_as_done(self, tmp_path: Path) -> None:
        """echo 退出码 0 → work 收单为「已回写」。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w1", role="开发执行体", card_path=str(tmp_path / "card.md")))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 1
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        assert summary["timed_out"] == 0
        assert summary["in_flight"] == 0
        done = store.list_work(state=State.DONE)
        assert [w.id for w in done] == ["w1"]

    def test_exit_nonzero_collected_as_rejected(self, tmp_path: Path) -> None:
        """false 命令退出码 1 → work 收单为「打回」+ 问题清单。"""
        reg_path = _write_demo_registry(tmp_path, command="false", args_template="")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w2", role="开发执行体"))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert rejected[0].id == "w2"
        assert any("退出码非 0" in p for p in rejected[0].problems)

    def test_launch_failure_collected_as_rejected(self, tmp_path: Path) -> None:
        """命令不存在 → 启动失败 → work 收单为「打回」。"""
        reg_path = _write_demo_registry(
            tmp_path, command="/nonexistent/command/xyz", args_template=""
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w3", role="开发执行体"))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert any("启动失败" in p for p in rejected[0].problems)

    def test_timeout_collected_as_rejected(self, tmp_path: Path) -> None:
        """sleep 超时 → kill → work 收单为「打回」+ timed_out 计数。"""
        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="10")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w4", role="开发执行体"))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "1", "EXECUTOR_RETRY_ONCE": "false"}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert summary["timed_out"] == 1
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert any("超时" in p for p in rejected[0].problems)

    def test_staff_work_not_dispatched(self, tmp_path: Path) -> None:
        """管理席 work → 不派发，仍留在待分派。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="t2", role="管理席"))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 0
        pending = store.list_work(state=State.TODO)
        assert [w.id for w in pending] == ["t2"]

    def test_done_work_not_rescanned(self, tmp_path: Path) -> None:
        """已回写 work 不参与本次扫描。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="t3", role="开发执行体", state=State.DONE))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 0

    def test_log_file_written(self, tmp_path: Path) -> None:
        """执行体 stdout 写入 {EXECUTOR_LOG_DIR}/{work_id}.log。"""
        reg_path = _write_demo_registry(
            tmp_path, command="echo", args_template="hello-{work_id}"
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w5", role="开发执行体"))
        log_dir = tmp_path / "logs"
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(log_dir),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        run_once(reg, store, cfg)
        log_file = log_dir / "w5.log"
        assert log_file.is_file()
        content = log_file.read_text(encoding="utf-8")
        assert "hello-w5" in content


class TestRunOnceManualGui:
    """手动 GUI 派发：挂起等人（不真拉执行体）。"""

    def test_manual_gui_hangs_in_running(self, tmp_path: Path) -> None:
        """手动 GUI work → 派发为执行中（不收单）。"""
        # 临时注册表：开发执行体仅手动 GUI 行
        reg_path = tmp_path / "manual.json"
        reg_path.write_text(
            json.dumps(
                {
                    "version": "2",
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "手动 GUI",
                            "当前绑定": "Trae",
                            "命令": "",
                            "参数模板": "",
                            "工作目录": "",
                            "备注": "",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="m1", role="开发执行体"))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert summary["in_flight"] == 1
        running = store.list_work(state=State.RUNNING)
        assert [w.id for w in running] == ["m1"]


class TestRunOnceDispatchByBinding:
    """T39：卡头执行体绑定优先派发（run_once 端到端行为）。"""

    @staticmethod
    def _trae_role_has_cli_registry(tmp_path: Path) -> Path:
        """构造 T38 插曲场景注册表：开发执行体同时含 Trae(手动 GUI) + OpenCode(CLI)。"""
        p = tmp_path / "trae_role_has_cli.json"
        p.write_text(
            json.dumps(
                {
                    "version": "2",
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "手动 GUI",
                            "当前绑定": "Trae",
                            "命令": "",
                            "参数模板": "",
                            "工作目录": "",
                            "备注": "人工接单",
                        },
                        {
                            "角色": "开发执行体",
                            "分类": "可后台 CLI",
                            "当前绑定": "OpenCode",
                            "命令": "echo",
                            "参数模板": "{work_id}",
                            "工作目录": "",
                            "备注": "默认写码",
                        },
                        {
                            "角色": "管理席",
                            "分类": "—",
                            "当前绑定": "Codex",
                            "命令": "",
                            "参数模板": "",
                            "工作目录": "",
                            "备注": "",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return p

    def test_trae_card_manual_even_if_role_has_cli(self, tmp_path: Path) -> None:
        """① 卡头 Trae（手动 GUI）但角色含 OpenCode CLI 行 → MANUAL，挂起 + 无执行日志。

        T38 插曲回归：修复前 decide(role) 会返回 AUTO 并拉起 OpenCode。
        """
        reg_path = self._trae_role_has_cli_registry(tmp_path)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="t38card", role="开发执行体", executor="Trae"))
        log_dir = tmp_path / "logs"
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(log_dir),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
        }
        summary = run_once(reg, store, cfg)
        # MANUAL：派发计数 +1，挂起在执行中，不收单
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert summary["in_flight"] == 1
        running = store.list_work(state=State.RUNNING)
        assert [w.id for w in running] == ["t38card"]
        # 关键：没有真实拉起 → 无执行日志文件
        assert not log_dir.exists() or not (log_dir / "t38card.log").exists()

    def test_opencode_card_auto_real_dispatch(self, tmp_path: Path) -> None:
        """② 卡头 OpenCode（CLI）→ AUTO 真实拉起收单（echo 退出 0 → 已回写）。"""
        reg_path = self._trae_role_has_cli_registry(tmp_path)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="cli-card", role="开发执行体", executor="OpenCode"))
        log_dir = tmp_path / "logs"
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(log_dir),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
        }
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        assert summary["in_flight"] == 0
        done = store.list_work(state=State.DONE)
        assert [w.id for w in done] == ["cli-card"]
        # 真实拉起 → 日志文件存在
        assert (log_dir / "cli-card.log").is_file()

    def test_codex_card_none_not_dispatched(self, tmp_path: Path) -> None:
        """③ 卡头 Codex（管理席「—」）→ NONE 不派发，留在待分派。"""
        reg_path = self._trae_role_has_cli_registry(tmp_path)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="codex-card", role="管理席", executor="Codex"))
        log_dir = tmp_path / "logs"
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(log_dir),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
        }
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 0
        assert summary["collected"] == 0
        pending = store.list_work(state=State.TODO)
        assert [w.id for w in pending] == ["codex-card"]
        # 不派发 → 无日志
        assert not log_dir.exists() or not (log_dir / "codex-card.log").exists()


class TestRunOnceManualDispatch:
    """T53：卡头「派发：manual」→ Engine 不自动拉，保持待分派（消灭假「执行中」）。"""

    def test_manual_dispatch_work_stays_pending(self, tmp_path: Path) -> None:
        """manual work（即使执行体是可后台 CLI）→ 不派发、不回写，仍留待分派。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(
            Work(
                id="m53", role="开发执行体", executor="demo",
                card_path=str(tmp_path / "card.md"), dispatch="manual",
            )
        )
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 1
        assert summary["dispatched"] == 0
        assert summary["collected"] == 0
        pending = store.list_work(state=State.TODO)
        assert [w.id for w in pending] == ["m53"]
        # 不派发 → 无执行日志
        assert not (tmp_path / "logs" / "m53.log").exists()

    def test_manual_dispatch_via_real_card(self, tmp_path: Path) -> None:
        """端到端：真实卡带 派发：manual → run_once 不派发，卡头保持待分派。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        card = tmp_path / "T53-e.md"
        card.write_text(
            "# 任务卡 T53 · 管理卡\n"
            "> 关联：TEST · 执行体：demo · 状态：待分派 · 派发：manual · 日期：2026-08-04\n"
            "\n## 目标\n管理席派发\n",
            encoding="utf-8",
        )
        store = FileBoardStore(tmp_path, reg)
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 0
        text = card.read_text(encoding="utf-8")
        assert "状态：待分派" in text


class TestFileBoardStore:
    """P1-1 文件/卡驱动 BoardStore：读 docs/dispatch → 构造 Work → 回写卡头状态。"""

    @staticmethod
    def _write_card(path: Path, card_id: str, executor: str, state: str) -> None:
        """写一张真实格式任务卡到 path。"""
        path.write_text(
            f"# 任务卡 {card_id} · 测试任务\n"
            f"> 关联：TEST\n"
            f"> 执行体：{executor} · 验收：Codex · 状态：{state} · 日期：2026-08-03\n"
            f"\n"
            f"## 目标\n测试用\n",
            encoding="utf-8",
        )

    def test_list_work_reads_card_headers(self, tmp_path: Path) -> None:
        """list_work 扫卡目录 → 解析卡头 → 构造 Work（含 role 反查 + executor 绑定）。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        # 注册表里「当前绑定」=demo，卡头执行体也写 demo → role=开发执行体
        self._write_card(tmp_path / "T99-test.md", "T99", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        works = store.list_work()
        assert len(works) == 1
        w = works[0]
        assert w.id == "T99"
        assert w.role == "开发执行体"
        assert w.state is State.TODO
        assert w.card_path.endswith("T99-test.md")
        # T39：卡头执行体绑定名填充到 work.executor
        assert w.executor == "demo"

    def test_list_work_fills_executor_empty_for_unknown(self, tmp_path: Path) -> None:
        """T39：卡头执行体不在注册表（未知）→ work.executor 仍保留卡头名（回退角色决策）。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        # 卡头写一个注册表里没有的执行体名
        self._write_card(tmp_path / "T97-ghost.md", "T97", "GhostTool", "待分派")
        store = FileBoardStore(tmp_path, reg)
        works = store.list_work()
        assert len(works) == 1
        w = works[0]
        # 未知执行体 → role 反查失败 → 空串；executor 保留卡头名供 decide_work 回退
        assert w.role == ""
        assert w.executor == "GhostTool"

    def test_list_work_propagates_manual_dispatch(self, tmp_path: Path) -> None:
        """T53：卡头「派发：manual」透传到 Work.dispatch（Engine 据此不自动拉）。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        card = tmp_path / "T53-m.md"
        card.write_text(
            "# 任务卡 T53 · 管理卡\n"
            "> 关联：TEST · 执行体：demo · 状态：待分派 · 派发：manual · 日期：2026-08-04\n"
            "\n## 目标\n管理席派发\n",
            encoding="utf-8",
        )
        store = FileBoardStore(tmp_path, reg)
        w = store.list_work()[0]
        assert w.dispatch == "manual"
        assert w.state is State.TODO

    def test_list_work_skips_unknown_state(self, tmp_path: Path) -> None:
        """未知状态不落入待分派，直接跳过。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T-bad.md", "Tbad", "demo", "乱七八糟")
        self._write_card(tmp_path / "T-ok.md", "Tok", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        works = store.list_work()
        assert [w.id for w in works] == ["Tok"]

    def test_list_work_skips_archived(self, tmp_path: Path) -> None:
        """索引 archived=true 的卡不进 Engine 队列。"""
        from server.board.loader import build_index_entry, load_dispatch_cards, parse_card, save_index_file

        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T-live.md", "Tlive", "demo", "待分派")
        self._write_card(tmp_path / "T-arch.md", "Tarch", "demo", "待分派")
        load_dispatch_cards(tmp_path)
        from server.board.loader import load_index_file

        entries = load_index_file(tmp_path)
        entries["Tarch"]["archived"] = True
        save_index_file(entries, tmp_path)
        store = FileBoardStore(tmp_path, reg)
        ids = [w.id for w in store.list_work()]
        assert "Tlive" in ids
        assert "Tarch" not in ids

    def test_reclaim_orphaned_running_with_marker(self, tmp_path: Path) -> None:
        """有 .running 标记的执行中 → 打回；无标记（manual 挂起）保留。

        遗留标记纯 ``1``（无 pid=）仍按孤儿回收。
        """
        from server.engine.main import reclaim_orphaned_running

        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        orphan = Work(id="auto1", role="开发执行体", state=State.RUNNING)
        manual = Work(id="man1", role="开发执行体", state=State.RUNNING, dispatch="manual")
        store.seed(orphan, manual)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "auto1.running").write_text("1", encoding="utf-8")
        n = reclaim_orphaned_running(store, log_dir)
        assert n == 1
        assert store.list_work(state=State.REJECTED)[0].id == "auto1"
        assert store.list_work(state=State.RUNNING)[0].id == "man1"
        assert not (log_dir / "auto1.running").exists()

    def test_reclaim_skips_live_owner_pid(self, tmp_path: Path) -> None:
        """标记 pid=<本进程> 且进程存活 → 不打回（防双 Engine 撞车）。"""
        import os

        from server.engine.main import reclaim_orphaned_running

        store = InMemoryBoardStore()
        live = Work(id="live1", role="开发执行体", state=State.RUNNING)
        dead = Work(id="dead1", role="开发执行体", state=State.RUNNING)
        store.seed(live, dead)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "live1.running").write_text(f"pid={os.getpid()}\n", encoding="utf-8")
        (log_dir / "dead1.running").write_text("pid=99999999\n", encoding="utf-8")
        n = reclaim_orphaned_running(store, log_dir)
        assert n == 1
        assert [w.id for w in store.list_work(state=State.RUNNING)] == ["live1"]
        assert store.list_work(state=State.REJECTED)[0].id == "dead1"
        assert (log_dir / "live1.running").is_file()
        assert not (log_dir / "dead1.running").exists()

    def test_reclaim_skips_live_child_pid(self, tmp_path: Path) -> None:
        """标记 child_pid 存活、engine_pid 已死 → 不打回（防 Engine 重启假打回）。"""
        import os

        from server.engine.main import reclaim_orphaned_running

        store = InMemoryBoardStore()
        live = Work(id="child1", role="开发执行体", state=State.RUNNING)
        store.seed(live)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "child1.running").write_text(
            f"engine_pid=99999998\npid={os.getpid()}\nchild_pid={os.getpid()}\n",
            encoding="utf-8",
        )
        n = reclaim_orphaned_running(store, log_dir)
        assert n == 0
        assert store.list_work(state=State.RUNNING)[0].id == "child1"

    def test_claim_running_marker_writes_pid(self, tmp_path: Path) -> None:
        import os

        from server.engine.main import _claim_running_marker, _parse_running_marker_pid

        marker = _claim_running_marker(tmp_path / "logs", "w1")
        raw = marker.read_text(encoding="utf-8")
        assert _parse_running_marker_pid(raw) == os.getpid()
        assert f"engine_pid={os.getpid()}" in raw

    def test_parent_blocks_dispatch(self) -> None:
        from server.engine.main import _parent_blocks_dispatch

        parent = Work(id="P1", role="开发执行体", state=State.DONE)
        child = Work(id="C1", role="开发执行体", state=State.TODO, parent="P1")
        by_id = {"P1": parent, "C1": child}
        assert _parent_blocks_dispatch(child, by_id)
        parent.state = State.CLOSED
        assert _parent_blocks_dispatch(child, by_id) is None

    def test_list_work_filters_by_state(self, tmp_path: Path) -> None:
        """list_work(state=X) 只返回匹配状态的卡。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T1.md", "T1", "demo", "待分派")
        self._write_card(tmp_path / "T2.md", "T2", "demo", "已关闭")
        store = FileBoardStore(tmp_path, reg)
        todo = store.list_work(state=State.TODO)
        assert [w.id for w in todo] == ["T1"]
        closed = store.list_work(state=State.CLOSED)
        assert [w.id for w in closed] == ["T2"]

    def test_list_work_scans_subdir_cards(self, tmp_path: Path) -> None:
        """T54：子目录 <prefix>/ 下新卡被扫入 work（根平铺 + 子目录混合）。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T9x-test.md", "T9x", "demo", "待分派")
        (tmp_path / "ccc").mkdir()
        self._write_card(tmp_path / "ccc" / "ccc100-test.md", "ccc100", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        works = store.list_work(state=State.TODO)
        assert {w.id for w in works} == {"T9x", "ccc100"}

    def test_list_work_skips_non_card_docs(self, tmp_path: Path) -> None:
        """T54：T-mapping.md 等说明文档（无卡头标题）不构成 work。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        (tmp_path / "T-mapping.md").write_text("# T 卡 → 前缀映射\n说明文档\n", encoding="utf-8")
        self._write_card(tmp_path / "T98.md", "T98", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        assert [w.id for w in store.list_work()] == ["T98"]

    def test_save_work_writes_back_status(self, tmp_path: Path) -> None:
        """save_work 回写卡头「状态」行（原子替换）。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        card = tmp_path / "T50.md"
        self._write_card(card, "T50", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        works = store.list_work(state=State.TODO)
        w = works[0]
        w.transition(State.RUNNING)
        store.save_work(w)
        # 重新读卡验证
        text = card.read_text(encoding="utf-8")
        assert "状态：执行中" in text
        assert "状态：待分派" not in text

    def test_save_work_preserves_other_metadata(self, tmp_path: Path) -> None:
        """回写状态不破坏卡头其他段（执行体/验收/日期）。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        card = tmp_path / "T51.md"
        self._write_card(card, "T51", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        w = store.list_work(state=State.TODO)[0]
        w.transition(State.RUNNING)
        store.save_work(w)
        text = card.read_text(encoding="utf-8")
        # 其他段仍在
        assert "执行体：demo" in text
        assert "验收：Codex" in text
        assert "日期：2026-08-03" in text

    def test_save_work_rejected_with_reason(self, tmp_path: Path) -> None:
        """打回时卡头状态含首个问题摘要。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        card = tmp_path / "T52.md"
        self._write_card(card, "T52", "demo", "执行中")
        store = FileBoardStore(tmp_path, reg)
        w = store.list_work(state=State.RUNNING)[0]
        w.transition(State.REJECTED, problems=["退出码非 0: 1（日志: /tmp/x.log）"])
        store.save_work(w)
        text = card.read_text(encoding="utf-8")
        assert "状态：打回（退出码非 0: 1（日志: /tmp/x.log））" in text

    def test_save_work_replace_state_strictly_in_metadata(self, tmp_path: Path) -> None:
        """F01：_replace_state_in_metadata 仅在卡头元数据行中替换，找不到则抛 ValueError 阻断且不误改正文。"""
        from server.engine.store import _replace_state_in_metadata

        # 场景 1：卡头正常，正文也含有「状态：」，应只修改卡头
        text_with_body_state = (
            "# 任务卡 T80 · 正常卡\n"
            "> 关联：TEST · 状态：待分派 · 执行体：demo\n"
            "\n"
            "## 目标\n"
            "我们要改变整个任务的当前状态：已完成。\n"
        )
        new_text = _replace_state_in_metadata(text_with_body_state, "执行中")
        assert "> 关联：TEST · 状态：执行中 · 执行体：demo\n" in new_text
        assert "状态：已完成。" in new_text  # 正文未被篡改

        # 场景 2：卡头缺失状态字段，正文含有「状态：」，应直接抛出 ValueError
        text_no_metadata_state = (
            "# 任务卡 T81 · 无状态卡\n"
            "> 关联：TEST · 执行体：demo\n"
            "\n"
            "## 目标\n"
            "我们要检查状态：已关闭。\n"
        )
        with pytest.raises(ValueError, match="未在卡头元数据行中找到「状态」段"):
            _replace_state_in_metadata(text_no_metadata_state, "执行中")

        # 场景 3：调用 save_work 回写无状态卡时，抛错被拦截，文件内容不被误改且不写盘
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        card = tmp_path / "T82.md"
        card.write_text(text_no_metadata_state, encoding="utf-8")
        store = FileBoardStore(tmp_path, reg)

        # 构造一个内存 work
        w = Work(
            id="T82",
            role="开发执行体",
            title="无状态卡",
            state=State.RUNNING,
            card_path=str(card.resolve()),
            executor="demo",
        )
        # 调用 save_work，异常应该被拦截，并且写盘被阻断，内容完全未变
        store.save_work(w)
        final_text = card.read_text(encoding="utf-8")
        assert final_text == text_no_metadata_state

    def test_end_to_end_dispatch_writes_back(self, tmp_path: Path) -> None:
        """端到端：真实卡 → Engine run_once → 卡头状态更新为「已回写」。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        card = tmp_path / "T60.md"
        self._write_card(card, "T60", "demo", "待分派")
        store = FileBoardStore(tmp_path, reg)
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
        }
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 1
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        # 卡头已回写
        text = card.read_text(encoding="utf-8")
        assert "状态：已回写" in text

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        """目录不存在 → list_work 返回空列表。"""
        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        store = FileBoardStore(tmp_path / "nonexistent", reg)
        assert store.list_work() == []


class TestParallelAndRelayGuard:
    """T59：并发派发与中继稳定性兜底测试。"""

    def test_parallel_dispatch_concurrency(self, tmp_path: Path) -> None:
        """两张卡并发派发，各自独立执行、收单正确、互不阻塞，总时间小于串行。"""
        import time
        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="1")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        # Launch two works
        store.seed(
            Work(id="p1", role="开发执行体", card_path=str(tmp_path / "p1.md")),
            Work(id="p2", role="开发执行体", card_path=str(tmp_path / "p2.md")),
        )
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "2",
            "EXECUTOR_PROBE_URL": "",  # Disable probe
        }

        start_time = time.time()
        summary = run_once(reg, store, cfg)  # wait=True 默认 drain
        end_time = time.time()

        # Parallel: both sleeps run concurrently, so total time is close to 1 second, definitely < 1.8 seconds.
        # Serial: would be 1 + 1 = 2 seconds, definitely > 2.0 seconds.
        duration = end_time - start_time
        assert duration < 1.8, f"Total execution time too long: {duration}s"
        assert summary["scanned"] == 2
        assert summary["dispatched"] == 2
        assert summary["collected"] == 2

        # Both works are DONE
        done = store.list_work(state=State.DONE)
        assert len(done) == 2
        assert {w.id for w in done} == {"p1", "p2"}

    def test_cross_round_slot_fill_no_batch_join(self, tmp_path: Path) -> None:
        """MAX=1：wait=False 不阻塞下一轮；槽满时后到卡不派；收单后下一轮补位。"""
        import time

        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="1")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(
            Work(id="c1", role="开发执行体", card_path=str(tmp_path / "c1.md")),
            Work(id="c2", role="开发执行体", card_path=str(tmp_path / "c2.md")),
        )
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }

        t0 = time.time()
        r1 = run_once(reg, store, cfg, wait=False)
        assert time.time() - t0 < 0.8, "wait=False 不得等 sleep 收单"
        assert r1["dispatched"] == 1
        assert r1["in_flight"] == 1
        assert len(store.list_work(state=State.TODO)) == 1

        r2 = run_once(reg, store, cfg, wait=False)
        assert r2["dispatched"] == 0, "槽满时不得再派"
        assert len(store.list_work(state=State.TODO)) == 1

        deadline = time.time() + 3.0
        r3 = None
        while time.time() < deadline:
            r3 = run_once(reg, store, cfg, wait=False)
            if r3["dispatched"] == 1:
                break
            time.sleep(0.15)
        assert r3 is not None and r3["dispatched"] == 1, "前卡结束后应补派第二张"

        # drain 收干净
        run_once(reg, store, cfg, wait=True)
        assert len(store.list_work(state=State.DONE)) == 2
        assert {w.id for w in store.list_work(state=State.DONE)} == {"c1", "c2"}

    def test_probe_success_dispatches_work(self, tmp_path: Path, monkeypatch) -> None:
        """探活成功：正常派发。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="pr1", role="开发执行体", card_path=str(tmp_path / "pr1.md")))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",  # Serial to be simpler
            "EXECUTOR_PROBE_URL": "http://mock-probe-url/",
        }

        # Mock probe_relay to return True (success)
        import server.engine.main
        monkeypatch.setattr(server.engine.main, "probe_relay", lambda url, timeout=5: True)

        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        assert len(store.list_work(state=State.DONE)) == 1

    def test_probe_failure_skips_work(self, tmp_path: Path, monkeypatch) -> None:
        """探活失败：跳过派发，仍留在待分派。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="pr2", role="开发执行体", card_path=str(tmp_path / "pr2.md")))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "http://mock-probe-url/",
        }

        # Mock probe_relay to return False (failure)
        import server.engine.main
        monkeypatch.setattr(server.engine.main, "probe_relay", lambda url, timeout=5: False)

        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 0
        assert summary["collected"] == 0
        # Remains in TODO
        pending = store.list_work(state=State.TODO)
        assert len(pending) == 1
        assert pending[0].id == "pr2"

    def test_auto_retry_once_on_timeout(self, tmp_path: Path) -> None:
        """上游波动超时：自动续作重派，状态重回待分派并附原因。"""
        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="10")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="ret1", role="开发执行体", card_path=str(tmp_path / "ret1.md")))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "1",  # Force timeout
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",  # Disable probe
            "EXECUTOR_RETRY_ONCE": "true",
        }

        summary = run_once(reg, store, cfg)
        # It was dispatched, but not collected or timed_out yet, because it went back to TODO!
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert summary["timed_out"] == 0

        pending = store.list_work(state=State.TODO)
        assert len(pending) == 1
        w = pending[0]
        assert w.id == "ret1"
        assert w.state is State.TODO
        assert w.retry_count == 1
        assert any("执行超时" in p for p in w.problems)

    def test_reject_after_retry_fails_again(self, tmp_path: Path) -> None:
        """重派仍失败：最终打回并附原问题。"""
        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="10")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        # Seed a work that has already been retried once! (retry_count=1)
        store.seed(Work(id="ret2", role="开发执行体", card_path=str(tmp_path / "ret2.md"), retry_count=1))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "1",  # Force timeout
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",  # Disable probe
            "EXECUTOR_RETRY_ONCE": "true",
        }

        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert summary["timed_out"] == 1  # Incremented

        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        w = rejected[0]
        assert w.id == "ret2"
        assert w.state is State.REJECTED
        assert any("执行超时" in p for p in w.problems)


class TestEngineWorktree:
    """测试 Engine 自动按卡创建 worktree 功能。"""

    def test_get_worktree_path(self) -> None:
        """验证 get_worktree_path 能正确替换各种占位符或追加 work_id。"""
        from server.engine.main import get_worktree_path

        # 1. 替换 <task>
        assert get_worktree_path("/path/to/ccc-dev-ws-<task>", "T64") == "/path/to/ccc-dev-ws-t64"
        # 2. 替换 {task}
        assert get_worktree_path("/path/to/ccc-dev-ws-{task}", "T64") == "/path/to/ccc-dev-ws-t64"
        # 3. 替换 <work_id>
        assert get_worktree_path("/path/to/ccc-dev-ws-<work_id>", "T64") == "/path/to/ccc-dev-ws-t64"
        # 4. 替换 {work_id}
        assert get_worktree_path("/path/to/ccc-dev-ws-{work_id}", "T64") == "/path/to/ccc-dev-ws-t64"
        # 5. 无占位符则追加
        assert get_worktree_path("/path/to/ccc-dev-ws", "T64") == "/path/to/ccc-dev-ws-t64"

    def test_run_once_with_worktree_enabled(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """配置了 worktree_base，自动创建 worktree，注入 {worktree} 占位符并在其中运行。

        ccc003：worktree 派发须产出 ≥1 新 commit（防 exit0 假成功），故执行体在 worktree 内
        落盘并提交一个文件 → 产物存在 → 收单为「已回写」。
        """
        # 1. 在 tmp_path 里初始化一个真实 git 仓库
        subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True)
        (tmp_path / "foo.txt").write_text("hello", encoding="utf-8")
        subprocess.run(["git", "add", "foo.txt"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", "origin/main"], cwd=str(tmp_path), check=True, capture_output=True)

        # 2. 切换当前进程的工作目录到 tmp_path
        monkeypatch.chdir(tmp_path)

        # 3. 设置 registry，配置 worktree_base 和 {worktree} 占位符。
        #    执行体在 worktree 内把两个占位符写入 work.txt 并提交（产物 = 新 commit）。
        worktree_base_dir = tmp_path / "wt"
        reg_path = _write_demo_registry(
            tmp_path,
            command="sh",
            args_template="-c 'echo work={work_id} wt={worktree} > work.txt && git add work.txt && git commit -m workdone'",
            worktree_base=str(worktree_base_dir),
        )
        reg = load_registry(reg_path)

        store = InMemoryBoardStore()
        # card_path 模拟卡 ID slug 派生分支名
        card_file = tmp_path / "T64-auto-worktree.md"
        card_file.write_text("Title: T64", encoding="utf-8")
        store.seed(Work(id="T64", role="开发执行体", card_path=str(card_file)))

        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }

        # 4. 执行 run_once
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1

        # 5. 验证 worktree 确实被创建，并且是真实的 git 仓库（主分支/对应分支）
        expected_worktree_path = tmp_path / "wt-t64"
        assert expected_worktree_path.exists()
        assert (expected_worktree_path / ".git").exists()

        # 6. 验证占位符被替换且产物已提交（work.txt 位于 worktree 内，日志产出 commit）
        work_output = (expected_worktree_path / "work.txt").read_text(encoding="utf-8")
        assert "work=T64" in work_output
        assert f"wt={expected_worktree_path}" in work_output
        log_file = tmp_path / "logs" / "T64.log"
        assert log_file.exists()
        assert "[codex/t64-auto-worktree" in log_file.read_text(encoding="utf-8")

    def test_run_once_with_worktree_failed_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """如果 git worktree 创建失败（例如不是 git 仓库），自动回退到默认工作目录而不丢失卡状态。"""
        # 不初始化 git 仓库，直接 chdir 到 tmp_path
        monkeypatch.chdir(tmp_path)

        # 设置 registry，配置 worktree_base
        worktree_base_dir = tmp_path / "wt"
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="work={work_id} wt={worktree}",
            worktree_base=str(worktree_base_dir),
        )
        reg = load_registry(reg_path)

        store = InMemoryBoardStore()
        store.seed(Work(id="T64", role="开发执行体", card_path=str(tmp_path / "T64.md")))

        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }

        # 执行 run_once 应该成功，因为有优雅的回退
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1

        # 验证 worktree 确实没有被成功创建
        expected_worktree_path = tmp_path / "wt-t64"
        assert not expected_worktree_path.exists()

        # 验证日志，由于回退，wt 占位符应该被替换为空字符串
        log_file = tmp_path / "logs" / "T64.log"
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "work=T64" in log_content
        assert "wt=" in log_content  # wt 被渲染为空字符串


class TestAcceptanceGuard:
    """T67 防线 2：派发前验收区预检——已验收卡（## 验收区 后 20 行内 ✅/判定：通过）不派发。"""

    @staticmethod
    def _write_card(path: Path, card_id: str, accepted: bool) -> None:
        body = "\n## 验收区\n✅ 判定：通过\n" if accepted else "\n## 目标\nx\n"
        path.write_text(
            f"# 任务卡 {card_id} · 测试\n"
            f"> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-05\n"
            f"{body}",
            encoding="utf-8",
        )

    def test_accepted_card_not_dispatched(self, tmp_path: Path, caplog) -> None:
        """已验收卡（卡头待分派漏网）→ 不派发、保持待分派、warning 记录。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T67-a.md", "T67-a", accepted=True)
        store = FileBoardStore(tmp_path, reg)
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "1",
               "EXECUTOR_PROBE_URL": ""}
        import logging
        with caplog.at_level(logging.WARNING, logger="ccc.engine"):
            summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 1
        assert summary["dispatched"] == 0
        assert summary["collected"] == 0
        # 保持原状态（待分派）
        pending = store.list_work(state=State.TODO)
        assert [w.id for w in pending] == ["T67-a"]
        # 未拉起执行体 → 无执行日志
        assert not (tmp_path / "logs" / "T67-a.log").exists()
        assert any("已验收卡不派发: work=T67-a" in r.message for r in caplog.records)

    def test_normal_pending_card_still_dispatched(self, tmp_path: Path) -> None:
        """无验收区正常待分派卡 → 行为不变，照常派发收单（回归防线 2 不误伤）。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T67-b.md", "T67-b", accepted=False)
        store = FileBoardStore(tmp_path, reg)
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "1",
               "EXECUTOR_PROBE_URL": ""}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        done = store.list_work(state=State.DONE)
        assert [w.id for w in done] == ["T67-b"]

    def test_accepted_skipped_in_parallel(self, tmp_path: Path) -> None:
        """并行模式：已验收卡跳过，正常卡照常派发。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T67-c.md", "T67-c", accepted=True)
        self._write_card(tmp_path / "T67-d.md", "T67-d", accepted=False)
        store = FileBoardStore(tmp_path, reg)
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "2",
               "EXECUTOR_PROBE_URL": ""}
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 2
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        pending = store.list_work(state=State.TODO)
        assert [w.id for w in pending] == ["T67-c"]
        done = store.list_work(state=State.DONE)
        assert [w.id for w in done] == ["T67-d"]

    def test_is_card_accepted_cached_by_mtime(self, tmp_path: Path) -> None:
        """is_card_accepted 按 mtime 缓存；文件变化后重新判定。"""
        import server.engine.main as m
        card = tmp_path / "T67-e.md"
        card.write_text("# 任务卡 T67-e\n> 状态：待分派\n## 验收区\n✅\n", encoding="utf-8")
        assert m.is_card_accepted(str(card)) is True
        # 未变化 → 命中缓存仍 True
        assert m.is_card_accepted(str(card)) is True
        # 文件更新为无验收区 → mtime 变化 → 重新判定 False
        card.write_text("# 任务卡 T67-e\n> 状态：待分派\n## 目标\nx\n", encoding="utf-8")
        assert m.is_card_accepted(str(card)) is False
        # 空路径/不存在文件 → False
        assert m.is_card_accepted("") is False
        assert m.is_card_accepted(str(tmp_path / "missing.md")) is False


def _init_src_repo(tmp_path: Path) -> None:
    """初始化一个带 origin/main 分支与初始 commit 的源仓库（worktree 的 `git worktree add` 来源）。"""
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "base.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base commit"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "origin/main"], cwd=str(tmp_path), check=True, capture_output=True)


class TestRunOnceFakeSuccessGuard:
    """ccc003 收单防假成功：worktree 派发 exit 0 但无产物 → 打回；有产物 → 已回写。"""

    @staticmethod
    def _make_worktree_registry(tmp_path: Path, command: str, worktree_base: Path) -> Path:
        """构造带 worktree_base 的开发执行体注册表（Executor=OpenCode，走 worktree 产物核验）。"""
        return _write_demo_registry(
            tmp_path,
            command=command,
            args_template="-c 'echo run'",
            worktree_base=str(worktree_base),
        )

    def _run_worktree_dispatch(self, tmp_path, command, card_state: str = "待分派") -> tuple:
        _init_src_repo(tmp_path)
        worktree_base = tmp_path / "wt"
        reg_path = self._make_worktree_registry(tmp_path, command, worktree_base)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_path = tmp_path / "T-fake.md"
        card_path.write_text(
            "# 任务卡 T-fake\n"
            f"> 关联：TEST · 执行体：demo · 状态：{card_state} · 日期：2026-08-06\n"
            "\n## 回写区\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake", role="开发执行体", card_path=str(card_path)))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "1",
               "EXECUTOR_PROBE_URL": ""}
        return run_once(reg, store, cfg), store, worktree_base

    def test_exit_zero_no_product_rejected(self, tmp_path: Path, monkeypatch) -> None:
        """① returncode 0 + worktree 无新 commit → 打回（机械门禁）。"""
        monkeypatch.chdir(tmp_path)
        summary, store, wt = self._run_worktree_dispatch(tmp_path, "echo")
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert rejected[0].id == "T-fake"
        assert any("无有效产物" in p or "无产物" in p for p in rejected[0].problems)

    def test_exit_zero_with_new_commit_collected(self, tmp_path: Path, monkeypatch) -> None:
        """② returncode 0 + worktree 内新增 commit 且非空 diff → 已回写。"""
        monkeypatch.chdir(tmp_path)
        # 执行体在 worktree 内落盘并提交 → 产物存在
        cmd = "sh"
        _script = "-c 'echo work > out.txt && git add out.txt && git commit -m done'"
        _init_src_repo(tmp_path)
        worktree_base = tmp_path / "wt"
        reg_path = _write_demo_registry(tmp_path, command=cmd, args_template=_script, worktree_base=str(worktree_base))
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_path = tmp_path / "T-fake2.md"
        card_path.write_text(
            "# 任务卡 T-fake2\n> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-06\n\n## 回写区\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake2", role="开发执行体", card_path=str(card_path)))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "1",
               "EXECUTOR_PROBE_URL": ""}
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        done = store.list_work(state=State.DONE)
        assert [w.id for w in done] == ["T-fake2"]

    def test_exit_zero_empty_commit_rejected(self, tmp_path: Path, monkeypatch) -> None:
        """③ returncode 0 + 空 commit（无文件 diff）→ 打回。"""
        monkeypatch.chdir(tmp_path)
        cmd = "sh"
        _script = "-c 'git commit --allow-empty -m empty'"
        _init_src_repo(tmp_path)
        worktree_base = tmp_path / "wt"
        reg_path = _write_demo_registry(tmp_path, command=cmd, args_template=_script, worktree_base=str(worktree_base))
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_path = tmp_path / "T-fake3.md"
        card_path.write_text(
            "# 任务卡 T-fake3\n> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-06\n\n## 回写区\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake3", role="开发执行体", card_path=str(card_path)))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "1",
               "EXECUTOR_PROBE_URL": ""}
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 0
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert any("无有效产物" in p for p in rejected[0].problems)

    def test_exit_zero_card_only_no_longer_collected(self, tmp_path: Path, monkeypatch) -> None:
        """④ 仅卡头已回写、无新 commit → 打回（取消卡头单独过门）。"""
        monkeypatch.chdir(tmp_path)
        _init_src_repo(tmp_path)
        worktree_base = tmp_path / "wt"
        reg_path = self._make_worktree_registry(tmp_path, "echo", worktree_base)
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_path = tmp_path / "T-fake4.md"
        card_path.write_text(
            "# 任务卡 T-fake4\n> 关联：TEST · 执行体：demo · 状态：已回写 · 日期：2026-08-06\n\n## 回写区\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake4", role="开发执行体", card_path=str(card_path)))
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
               "EXECUTOR_TIMEOUT_SECONDS": "30", "EXECUTOR_MAX_CONCURRENT": "1",
               "EXECUTOR_PROBE_URL": ""}
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 0
        assert store.list_work(state=State.REJECTED)

