"""test_engine_main — 入口冒烟 + 真实派发/收单闭环。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engine.dispatch import load_registry
from server.engine.main import main, run_once
from server.engine.store import InMemoryBoardStore
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
