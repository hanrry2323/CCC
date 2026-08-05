"""test_engine_main — 入口冒烟 + 真实派发/收单闭环。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.config.loader import ConfigError
from server.engine.dispatch import load_registry
from server.engine.main import main, run_once
from server.engine.store import FileBoardStore, InMemoryBoardStore
from server.engine.task import State, Work

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
               "EXECUTOR_TIMEOUT_SECONDS": "1"}
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
        }

        start_time = time.time()
        summary = run_once(reg, store, cfg)
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
