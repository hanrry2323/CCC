"""test_engine_main — 入口：`--once` 冒烟 + 缺配置报错。"""

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


def _write_env(tmp_path: Path, registry_path: Path | str) -> str:
    """写一份可用的 config.env（测试夹具；字面值仅属测试数据）。"""
    env = tmp_path / "config.env"
    env.write_text(
        "\n".join(
            [
                "ENGINE_PORT=8101",
                "BOARD_PORT=8102",
                "WEB_PORT=8103",
                "RELAY_PORT=8104",
                "DATA_DIR=/tmp/ccc2/data",
                "LOG_DIR=/tmp/ccc2/logs",
                "RELAY_UPSTREAM_URL=http://example.com/v1",
                f"EXECUTOR_REGISTRY_PATH={registry_path}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return str(env)


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
        """--once 有配置：退出码 0，输出一行 JSON 统计。"""
        env = _write_env(tmp_path, REGISTRY_PATH)
        code = main(["--config", env, "--once"])
        out = capsys.readouterr().out
        assert code == 0
        summary = json.loads(out)
        assert summary["mode"] == "once"
        assert summary["scanned"] == 0
        assert summary["dispatched"] == 0
        assert summary["in_flight"] == 0


class TestRunOnce:
    """单次扫描 + 派发逻辑。"""

    def test_dispatches_pending_cli_work(self) -> None:
        """待分派「开发执行体」work → 派发为执行中（AUTO）。"""
        reg = load_registry(REGISTRY_PATH)
        store = InMemoryBoardStore()
        store.seed(Work(id="t1", role="开发执行体"))
        summary = run_once(reg, store)
        assert summary["scanned"] == 1
        assert summary["dispatched"] == 1
        assert summary["in_flight"] == 1
        running = store.list_work(state=State.RUNNING)
        assert [w.id for w in running] == ["t1"]

    def test_staff_work_not_dispatched(self) -> None:
        """管理席 work → 不派发，仍留在待分派。"""
        reg = load_registry(REGISTRY_PATH)
        store = InMemoryBoardStore()
        store.seed(Work(id="t2", role="管理席"))
        summary = run_once(reg, store)
        assert summary["dispatched"] == 0
        pending = store.list_work(state=State.TODO)
        assert [w.id for w in pending] == ["t2"]

    def test_done_work_not_rescanned(self) -> None:
        """已回写 work 不参与本次扫描。"""
        reg = load_registry(REGISTRY_PATH)
        store = InMemoryBoardStore()
        store.seed(Work(id="t3", role="开发执行体", state=State.DONE))
        summary = run_once(reg, store)
        assert summary["scanned"] == 0
