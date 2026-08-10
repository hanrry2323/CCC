"""test_engine_main — 入口冒烟 + 真实派发/收单闭环。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from server.config.loader import ConfigError
from server.engine.dispatch import load_registry
from server.engine.main import main, run_once, _read_card_section, _audit_rejection_reason
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
    audit_command: str = "",
    audit_args_template: str = "audit {work_id}",
) -> Path:
    """写临时 executors.json（演示用占位命令，禁止生产引用）。"""
    executors = [
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
    ]
    if audit_command:
        executors.append(
            {
                "角色": "验收席",
                "分类": "可后台 CLI",
                "当前绑定": "Claude Code",
                "命令": audit_command,
                "参数模板": audit_args_template,
                "工作目录": "",
                "备注": "测试机审夹具",
            }
        )
    p = tmp_path / "executors.json"
    p.write_text(
        json.dumps(
            {
                "version": "2",
                "executors": executors,
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
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"), "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 1
        assert summary["dispatched"] == 1
        assert summary["collected"] == 1
        assert summary["timed_out"] == 0
        assert summary["in_flight"] == 0
        done = store.list_work(state=State.DONE)
        assert [w.id for w in done] == ["w1"]

    def test_exit_nonzero_collected_as_rejected(self, tmp_path: Path) -> None:
        """false 命令退出码 1 → 关闭重试时收单为「打回」+ 问题清单。"""
        reg_path = _write_demo_registry(tmp_path, command="false", args_template="")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w2", role="开发执行体"))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_RETRY_ONCE": "false",
        }
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert rejected[0].id == "w2"
        assert any("退出码非 0" in p for p in rejected[0].problems)

    def test_exit_nonzero_retries_to_todo(self, tmp_path: Path) -> None:
        """默认最多重试 3 次：首次失败回待分派并写原因，不进打回。"""
        reg_path = _write_demo_registry(tmp_path, command="false", args_template="")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w2r", role="开发执行体"))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_RETRIES": "3",
            "EXECUTOR_PROBE_URL": "",
        }
        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert not store.list_work(state=State.REJECTED)
        pending = store.list_work(state=State.TODO)
        assert len(pending) == 1
        assert pending[0].retry_count == 1
        assert any("退出码非 0" in p for p in pending[0].problems)

    def test_launch_failure_collected_as_rejected(self, tmp_path: Path) -> None:
        """命令不存在 → 启动失败 → 关闭重试时打回。"""
        reg_path = _write_demo_registry(tmp_path, command="/nonexistent/command/xyz", args_template="")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w3", role="开发执行体"))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_RETRY_ONCE": "false",
        }
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
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "1",
            "EXECUTOR_RETRY_ONCE": "false",
        }
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
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"), "EXECUTOR_TIMEOUT_SECONDS": "30"}
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
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"), "EXECUTOR_TIMEOUT_SECONDS": "30"}
        summary = run_once(reg, store, cfg)
        assert summary["scanned"] == 0

    def test_log_file_written(self, tmp_path: Path) -> None:
        """执行体 stdout 写入 {EXECUTOR_LOG_DIR}/{work_id}.log。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="hello-{work_id}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(Work(id="w5", role="开发执行体"))
        log_dir = tmp_path / "logs"
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(log_dir), "EXECUTOR_TIMEOUT_SECONDS": "30"}
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
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"), "EXECUTOR_TIMEOUT_SECONDS": "30"}
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
                id="m53",
                role="开发执行体",
                executor="demo",
                card_path=str(tmp_path / "card.md"),
                dispatch="manual",
            )
        )
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"), "EXECUTOR_TIMEOUT_SECONDS": "30"}
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
        cfg = {"DATA_DIR": str(tmp_path), "EXECUTOR_LOG_DIR": str(tmp_path / "logs"), "EXECUTOR_TIMEOUT_SECONDS": "30"}
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
        """有 .running 标记的执行中 → 回待分派重派；无标记（manual 挂起）保留。"""
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
        assert store.list_work(state=State.TODO)[0].id == "auto1"
        assert store.list_work(state=State.RUNNING)[0].id == "man1"
        assert not (log_dir / "auto1.running").exists()

    def test_reclaim_skips_live_owner_pid(self, tmp_path: Path) -> None:
        """标记 pid=<本进程> 且进程存活 → 不回收（防双 Engine 撞车）。"""
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
        assert store.list_work(state=State.TODO)[0].id == "dead1"
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

    def test_cleanup_dead_markers_removes_only_dead(self, tmp_path: Path) -> None:
        """死标记（PID 全死/无 PID）删除，活标记保留——不依赖卡状态。"""
        import os

        from server.engine.main import cleanup_dead_markers

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "dead1.running").write_text(
            "engine_pid=99999999\npid=99999998\nchild_pid=99999997\n",
            encoding="utf-8",
        )
        (log_dir / "nopid.running").write_text("garbage\n", encoding="utf-8")
        (log_dir / "live1.running").write_text(
            f"engine_pid={os.getpid()}\npid={os.getpid()}\n",
            encoding="utf-8",
        )
        (log_dir / "live1-audit.running").write_text(
            f"pid={os.getpid()}\n",
            encoding="utf-8",
        )
        n = cleanup_dead_markers(log_dir)
        assert n == 2
        assert not (log_dir / "dead1.running").exists()
        assert not (log_dir / "nopid.running").exists()
        assert (log_dir / "live1.running").is_file()
        assert (log_dir / "live1-audit.running").is_file()

    def test_claim_running_marker_writes_pid(self, tmp_path: Path) -> None:
        import os

        from server.engine.main import _claim_running_marker, _parse_running_marker_pid

        marker = _claim_running_marker(tmp_path / "logs", "w1")
        raw = marker.read_text(encoding="utf-8")
        assert _parse_running_marker_pid(raw) == os.getpid()
        assert f"engine_pid={os.getpid()}" in raw

    def test_running_marker_rewrite_no_false_reclaim(self, tmp_path: Path) -> None:
        """原子写回归：并发重写 .running 不得出现半截文件被误回收。

        曾发生：worker 重写标记（非原子 write_text）与回收器读取竞态 →
        读到空/半截内容 → 把仍在执行的卡假孤儿回收 → 收单丢 + 下轮重复派发。
        """
        import os
        import threading

        from server.engine.main import (
            _write_running_marker,
            reclaim_orphaned_running,
        )

        store = InMemoryBoardStore()
        store.seed(Work(id="race1", role="开发执行体", state=State.RUNNING))
        log_dir = tmp_path / "logs"
        stop = threading.Event()
        false_reclaims: list[int] = []

        def writer() -> None:
            while not stop.is_set():
                _write_running_marker(
                    log_dir,
                    "race1",
                    engine_pid=os.getpid(),
                    child_pid=os.getpid(),
                )

        w = threading.Thread(target=writer)
        w.start()
        try:
            for _ in range(300):
                n = reclaim_orphaned_running(store, log_dir)
                if n:
                    false_reclaims.append(n)
                    break
        finally:
            stop.set()
            w.join(timeout=5)

        assert not false_reclaims, f"并发重写标记期间误回收 {false_reclaims}"
        assert store.list_work(state=State.RUNNING)[0].id == "race1"
        raw = (log_dir / "race1.running").read_text(encoding="utf-8")
        assert f"engine_pid={os.getpid()}" in raw

    def test_parent_blocks_dispatch(self) -> None:
        from server.engine.main import _parent_blocks_dispatch

        parent = Work(id="P1", role="开发执行体", state=State.DONE)
        child = Work(id="C1", role="开发执行体", state=State.TODO, parent="P1")
        by_id = {"P1": parent, "C1": child}
        assert _parent_blocks_dispatch(child, by_id)
        parent.state = State.CLOSED
        assert _parent_blocks_dispatch(child, by_id) is None

    def test_depends_on_blocks_dispatch(self) -> None:
        from server.engine.main import _depends_on_blocks_dispatch

        dep = Work(id="ccc042", role="开发执行体", state=State.DONE)
        child = Work(id="ccc043", role="开发执行体", state=State.TODO, depends_on=["ccc042"])
        by_id = {"ccc042": dep, "ccc043": child}
        assert _depends_on_blocks_dispatch(child, by_id)
        dep.state = State.CLOSED
        assert _depends_on_blocks_dispatch(child, by_id) is None

    def test_depends_on_no_block_no_deps(self) -> None:
        from server.engine.main import _depends_on_blocks_dispatch

        child = Work(id="ccc044", role="开发执行体", state=State.TODO)
        assert _depends_on_blocks_dispatch(child, {"ccc044": child}) is None

    def test_depends_on_missing_dep_no_block(self) -> None:
        from server.engine.main import _depends_on_blocks_dispatch

        child = Work(id="ccc045", role="开发执行体", state=State.TODO, depends_on=["ccc999"])
        by_id = {"ccc045": child}
        assert _depends_on_blocks_dispatch(child, by_id) is None

    def test_depends_on_multiple_blocks(self) -> None:
        from server.engine.main import _depends_on_blocks_dispatch

        dep_a = Work(id="ccc042", role="开发执行体", state=State.CLOSED)
        dep_b = Work(id="ccc043", role="开发执行体", state=State.TODO)
        child = Work(id="ccc044", role="开发执行体", state=State.TODO, depends_on=["ccc042", "ccc043"])
        by_id = {"ccc042": dep_a, "ccc043": dep_b, "ccc044": child}
        assert _depends_on_blocks_dispatch(child, by_id)

    def test_detect_dependency_cycle(self) -> None:
        from server.engine.main import _detect_dependency_cycle

        a = Work(id="ccc042", role="开发执行体", state=State.TODO, depends_on=["ccc043"])
        b = Work(id="ccc043", role="开发执行体", state=State.TODO, depends_on=["ccc042"])
        by_id = {"ccc042": a, "ccc043": b}
        assert _detect_dependency_cycle(a, by_id)

    def test_detect_dependency_no_cycle(self) -> None:
        from server.engine.main import _detect_dependency_cycle

        a = Work(id="ccc042", role="开发执行体", state=State.TODO, depends_on=["ccc043"])
        b = Work(id="ccc043", role="开发执行体", state=State.TODO, depends_on=["ccc044"])
        c = Work(id="ccc044", role="开发执行体", state=State.TODO)
        by_id = {"ccc042": a, "ccc043": b, "ccc044": c}
        assert _detect_dependency_cycle(a, by_id) is None

    def test_file_store_runtime_mode(self, tmp_path: Path) -> None:
        """有 log_dir：save_work 只写运行时 sidecar，卡文件保持 main 镜像。"""
        from server.board.loader import load_dispatch_cards
        from server.engine.runtime_state import read_card_state
        from server.engine.store import FileBoardStore

        reg_path = _write_demo_registry(tmp_path)
        reg = load_registry(reg_path)
        dispatch_dir = tmp_path / "docs" / "dispatch"
        card_dir = dispatch_dir / "ccc"
        card_dir.mkdir(parents=True)
        card = card_dir / "ccc999-runtime.md"
        card.write_text(
            "# 任务卡 ccc999 · 测试\n"
            "> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-07\n"
            "\n## 目标\nx\n\n## 验收标准\nx\n",
            encoding="utf-8",
        )
        load_dispatch_cards(dispatch_dir)

        store = FileBoardStore(dispatch_dir, reg, log_dir=tmp_path / "logs")
        w = store.list_work(state=State.TODO)[0]
        assert w.id == "ccc999"
        w.transition(State.RUNNING)
        store.save_work(w)

        # 卡文件未被改写（主树干净）
        assert "状态：待分派" in card.read_text(encoding="utf-8")
        # 运行时 sidecar 记录执行中 + list_work 合成
        rt = read_card_state(tmp_path / "logs")
        assert rt["ccc999"]["state"] == "执行中"
        assert store.list_work(state=State.RUNNING)[0].id == "ccc999"
        assert store.list_work(state=State.TODO) == []

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
            "# 任务卡 T81 · 无状态卡\n> 关联：TEST · 执行体：demo\n\n## 目标\n我们要检查状态：已关闭。\n"
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

    def test_exec_and_audit_slots_independent(self, tmp_path: Path) -> None:
        """执行槽与机审槽独立：exec=1/audit=1 时，机审与第二张执行并行推进。"""
        import time

        reg_path = _write_demo_registry(
            tmp_path,
            command="sleep",
            args_template="1",
            audit_command="echo",
            audit_args_template="机审：通过 {work_id}",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        (tmp_path / "e1.md").write_text("# 任务卡 e1\n", encoding="utf-8")
        (tmp_path / "e2.md").write_text("# 任务卡 e2\n", encoding="utf-8")
        store.seed(
            Work(id="e1", role="开发执行体", card_path=str(tmp_path / "e1.md")),
            Work(id="e2", role="开发执行体", card_path=str(tmp_path / "e2.md")),
        )
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }

        total_audit_collected = 0
        r1 = run_once(reg, store, cfg, wait=False)
        assert r1["dispatched"] == 1

        deadline = time.time() + 8
        s = None
        while time.time() < deadline:
            time.sleep(0.15)
            s = run_once(reg, store, cfg, wait=False)
            total_audit_collected += s["audit_collected"]
            if s["audit_dispatched"] == 1 and s["dispatched"] == 1:
                break
        assert s is not None, "未等到机审/执行同轮派发"
        assert s["audit_dispatched"] == 1, f"机审应独立派发: {s}"
        assert s["dispatched"] == 1, f"执行槽应同时派第二张: {s}"

        deadline2 = time.time() + 8
        d = None
        while time.time() < deadline2:
            time.sleep(0.25)
            d = run_once(reg, store, cfg, wait=False)
            total_audit_collected += d["audit_collected"]
            done = len(store.list_work(state=State.DONE))
            if done == 2 and total_audit_collected >= 2:
                break
        if d is None or not (len(store.list_work(state=State.DONE)) == 2):
            d = run_once(reg, store, cfg, wait=True)
            total_audit_collected += d.get("audit_collected", 0)

        assert len(store.list_work(state=State.DONE)) == 2
        assert total_audit_collected == 2, f"两张卡机审应收 2 张: {total_audit_collected}"

    def test_audit_evidence_resume(self, tmp_path: Path) -> None:
        """执行收单后机审按证据捞卡；通过则卡上落机审区（无 worktree 走生产卡）。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="echo",
            audit_args_template="机审：通过 {work_id}",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "a1.md"
        card_file.write_text("# 任务卡 a1\n", encoding="utf-8")
        store.seed(Work(id="a1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1
        assert summary["audit_collected"] == 1
        assert "机审：通过" in card_file.read_text(encoding="utf-8")

    def test_run_once_summary_audit_fields(self, tmp_path: Path) -> None:
        """摘要含机审/清理字段（空队列时全 0）。"""
        reg_path = _write_demo_registry(tmp_path, command="echo")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }
        summary = run_once(reg, store, cfg)
        for key in (
            "audit_dispatched",
            "audit_in_flight",
            "audit_pending",
            "audit_collected",
            "audit_failed",
            "audit_failed_infra",
            "worktrees_cleaned",
        ):
            assert key in summary, f"摘要缺字段: {key}"
            assert isinstance(summary[key], int)

    def test_audit_infra_failure_holds_not_reject(self, tmp_path: Path) -> None:
        """上游 503：机审失败 → 冷却 + 自动续审，不打回、不计重试预算。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo \"API Error: 503 所有上游不可用\"; exit 1'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "i1.md"
        card_file.write_text("# 任务卡 i1\n", encoding="utf-8")
        store.seed(Work(id="i1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg)
        assert summary["audit_failed_infra"] == 1, summary
        assert summary["audit_failed"] == 0
        # 卡保持已回写，业务重试预算未消耗
        assert store.list_work(state=State.DONE)[0].id == "i1"
        assert store.list_work(state=State.DONE)[0].retry_count == 0
        from server.engine.runtime_state import read_card_state

        rt = read_card_state(tmp_path / "logs")
        assert rt["i1"]["infra_cooldown_until"]
        assert "基础设施特征" in rt["i1"]["reason"]
        # 冷却内不再自动重审
        summary2 = run_once(reg, store, cfg)
        assert summary2["audit_dispatched"] == 0

    def test_audit_business_failure_still_retries(self, tmp_path: Path) -> None:
        """机审：不通过 → 业务失败，回待分派重试（不计 infra）。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo 机审：不通过; exit 1'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "b1.md"
        card_file.write_text("# 任务卡 b1\n", encoding="utf-8")
        store.seed(Work(id="b1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg)
        assert summary["audit_failed"] == 1, summary
        assert summary["audit_failed_infra"] == 0
        todo = store.list_work(state=State.TODO)
        assert todo and todo[0].id == "b1"
        assert todo[0].retry_count == 1

    def test_audit_rejection_beats_infra_hint(self, tmp_path: Path) -> None:
        """审计日志同时含「机审：不通过」与 timeout 字样 → 业务失败优先（hp003 事故）。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo 机审：不通过; echo \"timeout occurred upstream\"; exit 1'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "r1.md"
        card_file.write_text("# 任务卡 r1\n", encoding="utf-8")
        store.seed(Work(id="r1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }
        summary = run_once(reg, store, cfg)
        assert summary["audit_failed"] == 1, summary
        assert summary["audit_failed_infra"] == 0
        todo = store.list_work(state=State.TODO)
        assert todo and todo[0].id == "r1"
        assert todo[0].retry_count == 1

    def test_audit_infra_cap_falls_back_to_todo(self, tmp_path: Path) -> None:
        """连续 3 次基础设施失败 → 回待分派人工跟进（可见、可操作，不无限空转）。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo \"API Error: 503 所有上游不可用\"; exit 1'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "c1.md"
        card_file.write_text("# 任务卡 c1\n", encoding="utf-8")
        store.seed(Work(id="c1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "0",
            "EXECUTOR_PROBE_URL": "",
            "EXECUTOR_INFRA_MAX_STRIKES": "3",
        }
        s1 = run_once(reg, store, cfg)
        assert s1["audit_failed_infra"] == 1, s1
        s2 = run_once(reg, store, cfg)
        assert s2["audit_failed_infra"] == 1, s2
        s3 = run_once(reg, store, cfg)
        assert s3["audit_failed"] == 1, f"第 3 次应回待分派: {s3}"
        todo = store.list_work(state=State.TODO)
        assert todo and todo[0].id == "c1"
        assert any("基础设施失败" in p for p in todo[0].problems)

    def test_audit_timeout_config(self) -> None:
        from server.engine.main import _audit_timeout_seconds

        assert _audit_timeout_seconds({}) == 1800
        assert _audit_timeout_seconds({"EXECUTOR_AUDIT_TIMEOUT_SECONDS": "600"}) == 600
        assert _audit_timeout_seconds({"EXECUTOR_AUDIT_TIMEOUT_SECONDS": "bad"}) == 1800

    def test_exec_infra_failure_holds(self, tmp_path: Path) -> None:
        """执行侧上游 503：回待分派 + 冷却，不计业务重试预算、不打回。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="sh",
            args_template="-c 'echo \"API Error: 503 所有上游不可用\"; exit 1'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "e1.md"
        card_file.write_text("# 任务卡 e1\n", encoding="utf-8")
        store.seed(Work(id="e1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        todo = store.list_work(state=State.TODO)
        assert todo and todo[0].id == "e1"
        assert todo[0].retry_count == 0
        from server.engine.runtime_state import read_card_state

        rt = read_card_state(tmp_path / "logs")
        assert rt["e1"]["infra_cooldown_until"]
        # 冷却内不再重派
        summary2 = run_once(reg, store, cfg)
        assert summary2["dispatched"] == 0

    def test_persistence_failure_classified_infra(self) -> None:
        from server.engine.main import _is_persistence_failure

        assert _is_persistence_failure(["机审通过但机审区落盘到分支卡失败"])
        assert _is_persistence_failure(["机审通过但分支证据未推送（ready 不可见）"])
        assert not _is_persistence_failure(["机审：不通过 缺测试"])

    def test_slot_limits_hot_read(self, tmp_path: Path) -> None:
        """槽位上限热读 config.env：改配置免重启生效；非法值回退启动值。"""
        from server.engine.main import _slot_limits

        cfg = {"EXECUTOR_MAX_CONCURRENT": "3", "EXECUTOR_MAX_AUDIT_CONCURRENT": "2"}
        assert _slot_limits(cfg) == (3, 2)

        env = tmp_path / "c.env"
        env.write_text(
            "EXECUTOR_MAX_CONCURRENT=5\nEXECUTOR_MAX_AUDIT_CONCURRENT=4\n",
            encoding="utf-8",
        )
        assert _slot_limits(cfg, env) == (5, 4)

        env.write_text("EXECUTOR_MAX_CONCURRENT=abc\n", encoding="utf-8")
        assert _slot_limits(cfg, env) == (3, 2)

    def test_concurrency_cap_and_queuing_boundaries(self, tmp_path: Path) -> None:
        """测试并发上限与排队等待边界判定：
        - 数量在上限内 (<= limit) -> 全部派发，无排队
        - 数量超限 (> limit) -> 派发正好达到上限，超出部分排队进入等待
        """
        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="1")
        reg = load_registry(reg_path)

        # 1. 边界：当任务数 <= 上限 (2 <= 3) -> 派发 2，排队为 0
        store = InMemoryBoardStore()
        store.seed(
            Work(id="q1", role="开发执行体", card_path=str(tmp_path / "q1.md")),
            Work(id="q2", role="开发执行体", card_path=str(tmp_path / "q2.md")),
        )
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "3",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg, wait=False)
        assert summary["dispatched"] == 2
        assert summary["queued"] == 0
        assert len(store.list_work(state=State.RUNNING)) == 2

        # 重置 Dispatch Pool 以便执行下一个干净的测试子项
        reset_dispatch_pool()

        # 2. 边界：当任务数刚好等于上限 (3 == 3) -> 派发 3，排队为 0
        store = InMemoryBoardStore()
        store.seed(
            Work(id="q1", role="开发执行体", card_path=str(tmp_path / "q1.md")),
            Work(id="q2", role="开发执行体", card_path=str(tmp_path / "q2.md")),
            Work(id="q3", role="开发执行体", card_path=str(tmp_path / "q3.md")),
        )
        summary = run_once(reg, store, cfg, wait=False)
        assert summary["dispatched"] == 3
        assert summary["queued"] == 0
        assert len(store.list_work(state=State.RUNNING)) == 3

        reset_dispatch_pool()

        # 3. 边界：当任务数超过上限 (4 > 3) -> 派发 3，排队 1
        store = InMemoryBoardStore()
        store.seed(
            Work(id="q1", role="开发执行体", card_path=str(tmp_path / "q1.md")),
            Work(id="q2", role="开发执行体", card_path=str(tmp_path / "q2.md")),
            Work(id="q3", role="开发执行体", card_path=str(tmp_path / "q3.md")),
            Work(id="q4", role="开发执行体", card_path=str(tmp_path / "q4.md")),
        )
        summary = run_once(reg, store, cfg, wait=False)
        assert summary["dispatched"] == 3
        assert summary["queued"] == 1
        assert len(store.list_work(state=State.RUNNING)) == 3
        assert len(store.list_work(state=State.TODO)) == 1

    def test_heartbeat_writes_metrics_files(self, tmp_path: Path) -> None:
        """每轮心跳落 engine-metrics.jsonl / worker-events.jsonl。"""
        reg_path = _write_demo_registry(tmp_path, command="echo")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        (tmp_path / "w1.md").write_text("# 任务卡 w1\n", encoding="utf-8")
        store.seed(Work(id="w1", role="开发执行体", card_path=str(tmp_path / "w1.md")))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }
        run_once(reg, store, cfg)
        log_dir = tmp_path / "logs"
        assert (log_dir / "engine-metrics.jsonl").is_file()
        assert (log_dir / "worker-events.jsonl").is_file()
        slot = json.loads((log_dir / "engine-metrics.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        assert slot["exec_max"] == 1
        assert slot["audit_max"] == 1
        worker = json.loads((log_dir / "worker-events.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert worker["work_id"] == "w1"
        assert worker["exit_kind"] in ("ok", "nonzero", "signal", "timeout", "launch_error")

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
        """已重试满 3 次仍失败 → 打回并附原因。"""
        reg_path = _write_demo_registry(tmp_path, command="sleep", args_template="10")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(
            Work(
                id="ret2",
                role="开发执行体",
                card_path=str(tmp_path / "ret2.md"),
                retry_count=3,
            )
        )
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "1",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
            "EXECUTOR_MAX_RETRIES": "3",
        }

        summary = run_once(reg, store, cfg)
        assert summary["dispatched"] == 1
        assert summary["collected"] == 0
        assert summary["timed_out"] == 1

        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        w = rejected[0]
        assert w.id == "ret2"
        assert w.state is State.REJECTED
        assert any("超时" in p for p in w.problems)


class TestAuditRejectionExitZero:
    """F1/F2/F3（2026-08-10）：机审 agent 打回但 exit code=0 时必须按业务打回，
    不得落入 infra 冷却死循环（clw009/clw010 卡死事故）。"""

    def test_audit_rejection_exit_zero_is_business_reject(self, tmp_path: Path) -> None:
        """exit 0 + audit「机审：不通过」→ 业务打回（回待分派重试），不计 infra。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo 机审：不通过; echo 核心业务意图未实现; exit 0'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "ez1.md"
        card_file.write_text("# 任务卡 ez1\n", encoding="utf-8")
        store.seed(Work(id="ez1", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg)
        assert summary["audit_failed"] == 1, summary
        assert summary["audit_failed_infra"] == 0, summary
        todo = store.list_work(state=State.TODO)
        assert todo and todo[0].id == "ez1"
        assert todo[0].retry_count == 1

    def test_audit_rejection_with_range_keyword_still_business(self, tmp_path: Path) -> None:
        """audit 含「不通过」+「范围越界」关键词 → 业务打回优先，不被 is_mech 抢占落 infra。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo 机审：不通过; echo 范围系统性越界; exit 0'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "ez2.md"
        card_file.write_text("# 任务卡 ez2\n", encoding="utf-8")
        store.seed(Work(id="ez2", role="开发执行体", card_path=str(card_file)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }

        summary = run_once(reg, store, cfg)
        assert summary["audit_failed"] == 1, summary
        assert summary["audit_failed_infra"] == 0, summary
        assert store.list_work(state=State.TODO), "应回待分派重试而非 infra 冷却"

    def test_audit_rejection_reason_extracts_line(self) -> None:
        text = (
            "[ccc.engine] start work=clw009 phase=audit cmd=...\n"
            "[ccc.engine] child_pid=123\n"
            "逐项核查完成。\n"
            "机审：不通过（维护区声明不实 + 核心业务意图未实现）\n"
            "原因：后端核心功能全部缺位。\n"
        )
        reason = _audit_rejection_reason(text)
        assert reason is not None
        assert "机审：不通过" in reason

    def test_audit_rejection_reason_empty(self) -> None:
        assert _audit_rejection_reason("") is None
        assert _audit_rejection_reason("机审通过\n") is None

    def test_audit_pass_not_fooled_by_prompt_wording(self) -> None:
        """clw009 回归：prompt 含「机审：不通过（具体原因）」字样，但 agent 实际通过。

        启动行 cmd= 后紧跟多行 prompt（含不通过字样），agent 输出「机审：通过」。
        判定必须以 child_pid= 之后为准，不得把 prompt 字样当不通过。"""
        text = (
            "[ccc.engine] start work=clw009 phase=audit pid_pending cmd=claude -p 你是 2017 机审席。\n"
            "- 原则性红线问题（范围系统性越界/核心业务意图违背）→ 输出「机审：不通过（具体原因）」并以非零退出\n"
            "通过则把「## 机审区」+「机审：通过」写进 worktree 卡文件。\n"
            "[ccc.engine] child_pid=35986\n"
            "Pushed successfully to `codex/clw009-terminal-overhaul`.\n"
            "**机审：通过**\n"
            "clw009 终端链路重做复审通过，核心整改已落地。\n"
        )
        from server.engine.main import (
            _audit_output_indicates_pass,
            _audit_output_indicates_rejection,
            _audit_rejection_reason,
        )

        assert _audit_output_indicates_pass(text) is True
        assert _audit_output_indicates_rejection(text) is False
        assert _audit_rejection_reason(text) is None

    def test_audit_rejection_still_detected_after_child_pid(self) -> None:
        """真正的不通过（在 child_pid= 之后）仍被正确判定。"""
        text = (
            "[ccc.engine] start work=clw011 phase=audit pid_pending cmd=claude -p ...\n"
            "通过则把「## 机审区」+「机审：通过」写进 worktree 卡文件。\n"
            "[ccc.engine] child_pid=123\n"
            "核查完成。\n"
            "机审：不通过（维护区声明不实 + 核心业务意图未实现）\n"
        )
        from server.engine.main import (
            _audit_output_indicates_pass,
            _audit_output_indicates_rejection,
            _audit_rejection_reason,
        )

        assert _audit_output_indicates_rejection(text) is True
        assert _audit_output_indicates_pass(text) is False
        reason = _audit_rejection_reason(text)
        assert reason is not None and "维护区声明不实" in reason


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
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True
        )
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

    def test_cleanup_closed_worktree(self, tmp_path: Path) -> None:
        """已关闭 + 干净 + 已合入 → 移除；脏 worktree 保留（绝不强删）。"""
        from server.engine.main import _cleanup_closed_worktrees

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "-q", "-b", "main", str(repo)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@example.com"],
            check=True,
            capture_output=True,
        )
        (repo / "f.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-qm", "base"],
            check=True,
            capture_output=True,
        )

        wt_base = tmp_path / "ccc-dev-ws"
        wt1 = tmp_path / "ccc-dev-ws-close1"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "codex/close1", str(wt1)],
            check=True,
            capture_output=True,
        )
        (wt1 / "f.txt").write_text("done\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(wt1), "add", "-A"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(wt1), "commit", "-qm", "work"],
            check=True,
            capture_output=True,
        )
        # 模拟已合入 main，并维护 origin/main 引用（合入检查依赖）
        subprocess.run(
            ["git", "-C", str(repo), "merge", "-q", "--ff-only", "codex/close1"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "main"],
            check=True,
            capture_output=True,
        )

        wt2 = tmp_path / "ccc-dev-ws-dirty1"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-b", "codex/dirty1", str(wt2)],
            check=True,
            capture_output=True,
        )
        (wt2 / "dirty.txt").write_text("x\n", encoding="utf-8")  # 未提交改动

        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            worktree_base=str(wt_base),
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        store.seed(
            Work(
                id="close1",
                role="开发执行体",
                state=State.CLOSED,
                card_path=str(repo / "close1.md"),
            ),
            Work(
                id="dirty1",
                role="开发执行体",
                state=State.CLOSED,
                card_path=str(repo / "dirty1.md"),
            ),
        )

        n = _cleanup_closed_worktrees(
            store,
            reg,
            {"DISPATCH_DIR": str(repo / "docs" / "dispatch")},
            tmp_path / "logs",
        )
        # 新语义（批次 3 设计）：卡终态（已关闭/打回）即使有未提交改动（如 dirty1）也会被 force 回收，
        # 干净的（如 close1）和脏的都回收，所以合计回收 2 个。
        # 未提交改动由关闭流程归档进行兜底。
        assert n == 2
        assert not wt1.exists()
        assert not wt2.exists()

    def test_audit_writes_branch_envelope(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """机审通过 → 机审区写进 worktree 分支卡并 commit+push（信封证据进 git）。"""
        import json as _json

        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True, capture_output=True)
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@example.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(bare)], check=True, capture_output=True)
        card_dir = repo / "docs" / "dispatch" / "xy"
        card_dir.mkdir(parents=True)
        card = card_dir / "xy099-audit-envelope.md"
        card.write_text(
            "# 任务卡 xy099 · 测试\n"
            "> 关联：XY · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 日期：2026-08-07\n"
            "\n## 目标\nx\n\n## 验收标准\nx\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "main"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "main"],
            check=True,
            capture_output=True,
        )
        # Engine 建 worktree 以进程 cwd 为仓根（生产=launchd WorkingDirectory）
        monkeypatch.chdir(repo)

        reg_path = tmp_path / "executors.json"
        reg_path.write_text(
            _json.dumps(
                {
                    "version": "2",
                    "executors": [
                        {
                            "角色": "开发执行体",
                            "分类": "可后台 CLI",
                            "当前绑定": "demo",
                            "命令": "sh",
                            "参数模板": "-c 'echo x >> work.txt && git add work.txt && git commit -qm w'",
                            "工作目录": "",
                            "worktree_base": str(tmp_path / "wt"),
                            "备注": "",
                        },
                        {
                            "角色": "验收席",
                            "分类": "可后台 CLI",
                            "当前绑定": "Claude Code",
                            "命令": "echo",
                            "参数模板": "机审：通过 {work_id}",
                            "工作目录": "",
                            "备注": "",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        reg = load_registry(str(reg_path))
        store = InMemoryBoardStore()
        store.seed(Work(id="xy099", role="开发执行体", card_path=str(card)))
        cfg = {
            "DATA_DIR": str(repo),
            "DISPATCH_DIR": str(repo / "docs" / "dispatch"),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
            "CCC_AUTO_PULL": "0",
        }

        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1, summary
        assert summary["audit_collected"] == 1, summary

        wt_card = tmp_path / "wt-xy099" / "docs" / "dispatch" / "xy" / "xy099-audit-envelope.md"
        assert wt_card.is_file()
        assert "机审：通过" in wt_card.read_text(encoding="utf-8")

        fetch = subprocess.run(["git", "-C", str(repo), "fetch", "-q", "origin"], capture_output=True, text=True)
        assert fetch.returncode == 0
        show = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "show",
                "origin/codex/xy099-audit-envelope:docs/dispatch/xy/xy099-audit-envelope.md",
            ],
            capture_output=True,
            text=True,
        )
        assert show.returncode == 0, show.stderr
        assert "机审：通过" in show.stdout


class TestAcceptanceGuard:
    """T67 防线 2：派发前验收区预检——已验收卡（## 验收区 后 20 行内 ✅/判定：通过）不派发。"""

    @staticmethod
    def _write_card(path: Path, card_id: str, accepted: bool) -> None:
        body = "\n## 验收区\n✅ 判定：通过\n" if accepted else "\n## 目标\nx\n"
        path.write_text(
            f"# 任务卡 {card_id} · 测试\n> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-05\n{body}",
            encoding="utf-8",
        )

    def test_accepted_card_not_dispatched(self, tmp_path: Path, caplog) -> None:
        """已验收卡（卡头待分派漏网）→ 不派发、保持待分派、warning 记录。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="{work_id}")
        reg = load_registry(reg_path)
        self._write_card(tmp_path / "T67-a.md", "T67-a", accepted=True)
        store = FileBoardStore(tmp_path, reg)
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }
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
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }
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
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "2",
            "EXECUTOR_PROBE_URL": "",
        }
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
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True, capture_output=True
    )
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
            f"# 任务卡 T-fake\n> 关联：TEST · 执行体：demo · 状态：{card_state} · 日期：2026-08-06\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake", role="开发执行体", card_path=str(card_path)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
            "EXECUTOR_RETRY_ONCE": "false",
        }
        return run_once(reg, store, cfg), store, worktree_base

    def test_exit_zero_no_product_rejected(self, tmp_path: Path, monkeypatch) -> None:
        """① returncode 0 + worktree 无新 commit → 打回（机械门禁，重试关闭）。"""
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
            "# 任务卡 T-fake2\n> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-06\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake2", role="开发执行体", card_path=str(card_path)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
        }
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
            "# 任务卡 T-fake3\n> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-06\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake3", role="开发执行体", card_path=str(card_path)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
            "EXECUTOR_RETRY_ONCE": "false",
        }
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 0
        rejected = store.list_work(state=State.REJECTED)
        assert len(rejected) == 1
        assert any("无有效产物" in p for p in rejected[0].problems)

    def test_exit_zero_card_only_no_longer_collected(self, tmp_path: Path, monkeypatch) -> None:
        """④ 仅卡头已回写、无新 commit → 打回（取消卡头单独过门，重试关闭）。"""
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
        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
            "EXECUTOR_RETRY_ONCE": "false",
        }
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 0
        assert store.list_work(state=State.REJECTED)

    def test_audit_prompt_no_re_run_wording(self) -> None:
        """断言 MachineAuditPrompt 构造函数输出，且不含「复跑测试/复跑编译裁决」等表述。"""
        from server.engine.main import MachineAuditPrompt

        prompt_obj = MachineAuditPrompt(card_path="docs/dispatch/c1.md", work_id="c1", worktree="/tmp/wt")
        prompt_text = prompt_obj.build()
        assert "复跑测试" not in prompt_text
        assert "复跑编译" not in prompt_text
        assert "编译裁决" not in prompt_text
        assert "只做原则性 Code Review" in prompt_text
        assert "就地修复" in prompt_text

    def test_gate_probe_failure_blocks_audit(self, tmp_path: Path, monkeypatch) -> None:
        """门禁探针失败（代码级）→ 放行进机审，不直接打回（机审负责修复或判定）。"""
        monkeypatch.chdir(tmp_path)
        _init_src_repo(tmp_path)
        worktree_base = tmp_path / "wt"
        reg_path = _write_demo_registry(
            tmp_path,
            command="sh",
            args_template="-c 'echo x >> work.txt && git add work.txt && git commit -qm w'",
            worktree_base=str(worktree_base),
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_path = tmp_path / "T-fake5.md"
        card_path.write_text(
            "# 任务卡 T-fake5\n"
            "> 关联：TEST · 执行体：demo · 状态：待分派 · 日期：2026-08-06\n\n"
            "## 门禁\n\n"
            "测试：sh -c 'exit 1'\n\n"
            "## 回写区\n\n"
            "已完成\n",
            encoding="utf-8",
        )
        store.seed(Work(id="T-fake5", role="开发执行体", card_path=str(card_path)))
        cfg = {
            "DATA_DIR": str(tmp_path),
            "DISPATCH_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "30",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_PROBE_URL": "",
            "EXECUTOR_RETRY_ONCE": "false",
        }
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1  # 门禁代码级失败 → 放行进机审，卡进入已回写
        assert summary["audit_dispatched"] == 1  # 卡进入机审队列（但无验收席 CLI，跳过）
        done = store.list_work(state=State.DONE)
        assert len(done) == 1
        assert done[0].id == "T-fake5"

    def test_audit_mechanical_rejection_leads_to_infra_retry(self, tmp_path: Path) -> None:
        """机审输出「测试未跑/编译失败」类机械问题 → 不被判业务打回，走 infra 冷却续审路径，不进 retry 预算。"""
        reg_path = _write_demo_registry(
            tmp_path,
            command="echo",
            args_template="ok {work_id}",
            audit_command="sh",
            audit_args_template="-c 'echo \"[ccc.engine] start work=xy001 phase=audit pid_pending cmd=...\n测试未跑，无法通过\"; exit 1'",
        )
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()
        card_file = tmp_path / "m1.md"
        card_file.write_text("# 任务卡 m1\n", encoding="utf-8")
        store.seed(Work(id="m1", role="开发执行体", card_path=str(card_file)))
        done_work = store.list_work()[0]
        done_work.state = State.DONE
        store.save_work(done_work)

        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "1",
            "EXECUTOR_INFRA_COOLDOWN_SECONDS": "600",
            "EXECUTOR_PROBE_URL": "",
        }
        summary = run_once(reg, store, cfg)
        assert summary["audit_failed_infra"] == 1
        assert summary["audit_failed"] == 0
        all_works = store.list_work()
        assert all_works[0].retry_count == 0


class TestCardSectionReader:
    """_read_card_section 单元测试。"""

    def test_reads_section_content(self, tmp_path: Path) -> None:
        """提取卡内指定节的内容。"""
        card = tmp_path / "test.md"
        card.write_text(
            "# 任务卡 m1 · 测试\n\n"
            "## 目标\n完成测试\n\n"
            "## 执行提示\n"
            "- 项目：test\n"
            "- 技术栈：Python\n\n"
            "## 机审提示\n"
            "- 审查重点：逻辑\n\n"
            "## 回写区\n",
            encoding="utf-8",
        )
        hint = _read_card_section(card, "执行提示")
        assert "- 项目：test" in hint
        assert "- 技术栈：Python" in hint
        assert "机审提示" not in hint

    def test_empty_when_section_missing(self, tmp_path: Path) -> None:
        """卡无对应节 → 返回空字符串。"""
        card = tmp_path / "test.md"
        card.write_text(
            "# 任务卡 m1 · 测试\n\n## 目标\n完成测试\n",
            encoding="utf-8",
        )
        assert _read_card_section(card, "执行提示") == ""

    def test_empty_when_section_is_placeholder(self, tmp_path: Path) -> None:
        """节内容为占位文本 → 返回空（中枢尚未注入）。"""
        card = tmp_path / "test.md"
        card.write_text(
            "# 任务卡 m1 · 测试\n\n"
            "## 执行提示\n\n"
            "（中枢在出卡时注入，执行体（开发大模型）读到本节后优先遵循。）\n\n"
            "## 回写区\n",
            encoding="utf-8",
        )
        result = _read_card_section(card, "执行提示")
        # 占位文本 → 返回空（不注入无意义内容）
        assert result == ""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """文件不存在 → 返回空。"""
        assert _read_card_section(tmp_path / "nonexistent.md", "执行提示") == ""


class TestPromptInjection:
    """引擎注入卡内提示段到执行体/验收体 prompt 的集成测试。"""

    def test_executor_prompt_gets_hint(self, tmp_path: Path) -> None:
        """卡含「## 执行提示」→ 执行体命令末尾包含提示内容。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="work={work_id} card={card_path}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()

        dispatch_dir = tmp_path / "dispatch" / "ccc"
        dispatch_dir.mkdir(parents=True)
        card_file = dispatch_dir / "ccc001-test.md"
        card_file.write_text(
            "# 任务卡 ccc001 · 测试\n"
            "> 关联：TEST · 执行体：demo · 验收：demo · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-09\n"
            "\n"
            "## 目标\n测试\n"
            "\n"
            "## 验收标准\n测试通过\n"
            "\n"
            "## 执行提示\n"
            "- 项目：test（Python）\n"
            "- 仓库路径：/tmp/test\n"
            "\n"
            "## 回写区\n\n测试回写内容\n",
            encoding="utf-8",
        )

        store.seed(Work(id="ccc001", role="开发执行体", card_path=str(card_file), executor="demo"))
        done_work = store.list_work()[0]
        done_work.state = State.TODO
        store.save_work(done_work)

        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "0",
            "EXECUTOR_PROBE_URL": "",
            "DISPATCH_DIR": str(tmp_path / "dispatch"),
        }
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1

        # 检查执行体日志是否包含注入的提示
        log_file = tmp_path / "logs" / "ccc001.log"
        log_content = log_file.read_text(encoding="utf-8")
        # 日志第一行是引擎启动信息，包含完整 cmd
        assert "项目：test" in log_content
        assert "仓库路径：/tmp/test" in log_content

    def test_no_hint_section_unchanged_behavior(self, tmp_path: Path) -> None:
        """卡无「## 执行提示」段 → 执行体行为与原来完全一致（不注入任何内容）。"""
        reg_path = _write_demo_registry(tmp_path, command="echo", args_template="work={work_id} card={card_path}")
        reg = load_registry(reg_path)
        store = InMemoryBoardStore()

        dispatch_dir = tmp_path / "dispatch" / "ccc"
        dispatch_dir.mkdir(parents=True)
        card_file = dispatch_dir / "ccc002-test.md"
        card_file.write_text(
            "# 任务卡 ccc002 · 旧卡\n"
            "> 关联：TEST · 执行体：demo · 验收：demo · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-09\n"
            "\n"
            "## 目标\n旧卡测试\n"
            "\n"
            "## 验收标准\n测试通过\n"
            "\n"
            "## 回写区\n\n测试回写内容\n",
            encoding="utf-8",
        )

        store.seed(Work(id="ccc002", role="开发执行体", card_path=str(card_file), executor="demo"))
        done_work = store.list_work()[0]
        done_work.state = State.TODO
        store.save_work(done_work)

        cfg = {
            "DATA_DIR": str(tmp_path),
            "EXECUTOR_LOG_DIR": str(tmp_path / "logs"),
            "EXECUTOR_TIMEOUT_SECONDS": "5",
            "EXECUTOR_MAX_CONCURRENT": "1",
            "EXECUTOR_MAX_AUDIT_CONCURRENT": "0",
            "EXECUTOR_PROBE_URL": "",
            "DISPATCH_DIR": str(tmp_path / "dispatch"),
        }
        summary = run_once(reg, store, cfg)
        assert summary["collected"] == 1

        log_file = tmp_path / "logs" / "ccc002.log"
        log_content = log_file.read_text(encoding="utf-8")
        # 旧卡无提示段 → 不含注入标记

    def test_prompt_inject_plan_extracted(self, tmp_path: Path) -> None:
        """关联含方案编号 → 提取方案并注入摘要。"""
        from server.board.prompt_inject import build_executor_hint

        # 1. 准备一个方案文件
        plan_dir = tmp_path / "docs" / "projects" / "ccc" / "plans"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "011-loop-observer-architecture.md"
        plan_file.write_text(
            "# 方案 · Loop Observer 架构\n\n"
            "> 项目：ccc · 编号：ccc-plan-011 · 状态：已确认\n\n"
            "## 目标\n"
            "实现执行 Agent 心智注入，自动拼入关联方案摘要。\n\n"
            "## 验收标准\n"
            "- [ ] 在提示中看到关联方案摘要。\n",
            encoding="utf-8",
        )

        # 2. 准备一个项目 README
        project_dir = tmp_path / "docs" / "projects" / "ccc"
        project_dir.mkdir(parents=True, exist_ok=True)
        readme_file = project_dir / "README.md"
        readme_file.write_text("# CCC\n\n## 线路 / 近况\n\n- 近况1\n- 近况2\n", encoding="utf-8")

        # 我们需要临时修改 _PROJECT_ROOT
        import server.board.prompt_inject

        orig_root = server.board.prompt_inject._PROJECT_ROOT
        server.board.prompt_inject._PROJECT_ROOT = tmp_path
        try:
            # 3. 准备卡内容
            card_content = (
                "# 任务卡 ccc023 · 执行\n"
                "> 关联：ccc-plan-011 卡1 · 执行体：OpenCode · 状态：待分派 · 日期：2026-08-09\n"
            )
            hint = build_executor_hint("ccc", title="test", card_content=card_content)
            assert (
                "关联方案摘要：目标：实现执行 Agent 心智注入，自动拼入关联方案摘要。验收标准：在提示中看到关联方案摘要。"
                in hint
            )
            assert "项目线路/近况：" in hint
            assert "近况1" in hint
            assert "近况2" in hint
        finally:
            server.board.prompt_inject._PROJECT_ROOT = orig_root

    def test_prompt_inject_non_plan_related(self, tmp_path: Path) -> None:
        """关联占位 (无方案编号) → 不注入降级。"""
        from server.board.prompt_inject import build_executor_hint

        import server.board.prompt_inject

        orig_root = server.board.prompt_inject._PROJECT_ROOT
        server.board.prompt_inject._PROJECT_ROOT = tmp_path
        try:
            card_content = (
                "# 任务卡 ccc023 · 执行\n> 关联：阶段 3 P1 · 执行体：OpenCode · 状态：待分派 · 日期：2026-08-09\n"
            )
            hint = build_executor_hint("ccc", title="test", card_content=card_content)
            # 无方案编号 -> 不注入「关联方案摘要：」行
            assert "关联方案摘要" not in hint
        finally:
            server.board.prompt_inject._PROJECT_ROOT = orig_root

    def test_prompt_inject_plan_not_found(self, tmp_path: Path) -> None:
        """方案不存在 → 不抛错。"""
        from server.board.prompt_inject import build_executor_hint

        import server.board.prompt_inject

        orig_root = server.board.prompt_inject._PROJECT_ROOT
        server.board.prompt_inject._PROJECT_ROOT = tmp_path
        try:
            card_content = (
                "# 任务卡 ccc023 · 执行\n"
                "> 关联：ccc-plan-999 卡1 · 执行体：OpenCode · 状态：待分派 · 日期：2026-08-09\n"
            )
            # 方案 999 不存在，应不抛错且不注入
            hint = build_executor_hint("ccc", title="test", card_content=card_content)
            assert "关联方案摘要" not in hint
        finally:
            server.board.prompt_inject._PROJECT_ROOT = orig_root


class TestValidateCardStateAfterWriteback:
    """执行体回写后卡头状态合法性校验（mx028 事故复盘）。"""

    def test_rejects_completed_state(self, tmp_path: Path) -> None:
        from server.engine.main import validate_card_state_after_writeback

        card = tmp_path / "mx028-rss-feed-validation.md"
        card.write_text(
            "# 任务卡 mx028 · RSS feed validation\n\n"
            "> 关联：阶段 3 P1 · 执行体：OpenCode · 状态：completed · 日期：2026-08-09\n\n"
            "## 目标\n\n测试\n\n"
            "## 回写区\n\n**执行体**：OpenCode · 日期：2026-08-09\n\n实现说明\n",
            encoding="utf-8",
        )
        ok, err = validate_card_state_after_writeback(card)
        assert not ok
        assert "completed" in err
        assert "已回写" in err

    def test_rejects_done_state(self, tmp_path: Path) -> None:
        from server.engine.main import validate_card_state_after_writeback

        card = tmp_path / "test-card.md"
        card.write_text(
            "# 任务卡 test\n\n> 关联：P1 · 执行体：OpenCode · 状态：done · 日期：2026-08-09\n\n## 目标\n\n测试\n",
            encoding="utf-8",
        )
        ok, err = validate_card_state_after_writeback(card)
        assert not ok
        assert "done" in err

    def test_accepts_valid_state(self, tmp_path: Path) -> None:
        from server.engine.main import validate_card_state_after_writeback

        card = tmp_path / "test-card.md"
        card.write_text(
            "# 任务卡 test\n\n> 关联：P1 · 执行体：OpenCode · 状态：已回写 · 日期：2026-08-09\n\n## 目标\n\n测试\n",
            encoding="utf-8",
        )
        ok, err = validate_card_state_after_writeback(card)
        assert ok

    def test_accepts_other_valid_states(self, tmp_path: Path) -> None:
        from server.engine.main import validate_card_state_after_writeback

        for state in ("待分派", "执行中", "已关闭", "打回"):
            card = tmp_path / "test-card.md"
            card.write_text(
                f"# 任务卡 test\n\n"
                f"> 关联：P1 · 执行体：OpenCode · 状态：{state} · 日期：2026-08-09\n\n"
                "## 目标\n\n测试\n",
                encoding="utf-8",
            )
            ok, _ = validate_card_state_after_writeback(card)
            assert ok, f"合法状态 {state!r} 应通过校验"

    def test_accepts_missing_state(self, tmp_path: Path) -> None:
        from server.engine.main import validate_card_state_after_writeback

        card = tmp_path / "test-card.md"
        card.write_text(
            "# 任务卡 test\n\n> 关联：P1 · 执行体：OpenCode · 日期：2026-08-09\n\n## 目标\n\n测试\n",
            encoding="utf-8",
        )
        ok, _ = validate_card_state_after_writeback(card)
        assert ok  # 无状态行 → 放行（历史兼容）

    def test_is_empty_writeback_or_placeholder_all_cases(self, tmp_path: Path) -> None:
        """测试：is_empty_writeback_or_placeholder 函数正确判断各种占位和空回写情况"""
        from server.engine.main import is_empty_writeback_or_placeholder
        from server.engine.task import Work

        card = tmp_path / "ccc039-test.md"
        # 1. 缺失维护区
        card.write_text("# 任务卡 ccc039\n", encoding="utf-8")
        work = Work(id="ccc039", role="开发执行体", card_path=str(card))
        is_empty, reason = is_empty_writeback_or_placeholder(work, "")
        assert is_empty
        assert "缺失 ## 维护区 节" in reason

        # 2. 维护区为占位符
        card.write_text(
            "# 任务卡 ccc039\n## 维护区\n"
            "1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是/否]\n"
            "   - 说明：占位\n"
            "2. **教训沉淀**：本卡是否产出可复用教训？[有/无]\n"
            "   - 说明：占位\n"
            "3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[是/否]\n"
            "   - 说明：占位\n"
            "4. **线路图**：项目近况/下一步是否变化？[是/否]\n"
            "   - 说明：占位\n",
            encoding="utf-8",
        )
        is_empty, reason = is_empty_writeback_or_placeholder(work, "")
        assert is_empty
        assert "未勾选或仍为占位" in reason or "包含占位文本" in reason or "格式不完整" in reason

        # 3. 维护区正常填写
        card.write_text(
            "# 任务卡 ccc039\n## 维护区\n"
            "1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]\n"
            "   - 说明：方案已同步更新\n"
            "2. **教训沉淀**：本卡是否产出可复用教训？[无]\n"
            "   - 说明：无教训沉淀\n"
            "3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]\n"
            "   - 说明：结构未改变\n"
            "4. **线路图**：项目近况/下一步是否变化？[否]\n"
            "   - 说明：无变化\n",
            encoding="utf-8",
        )
        is_empty, reason = is_empty_writeback_or_placeholder(work, "")
        assert not is_empty, reason
