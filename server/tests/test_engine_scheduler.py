"""test_engine_scheduler — 定时任务框架：注册/执行/CLI 冒烟。

验证：
1. TaskRegistry：注册、分类筛选
2. run_tasks：只读巡检执行 / 变更类条件执行 / 跳过
3. main --once CLI：完整入口调用
4. 既有 83 用例不回归
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from server.engine.scheduler import (
    TASK_TYPE_CHANGE,
    TASK_TYPE_READONLY,
    ScheduledTask,
    TaskRegistry,
    main,
    run_once,
    run_tasks,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _dummy_readonly_ok(cfg: dict) -> tuple[bool, dict]:
    return True, {"msg": "readonly ok"}


def _dummy_readonly_fail(cfg: dict) -> tuple[bool, dict]:
    return False, {"msg": "readonly fail"}


def _dummy_change_ok(cfg: dict) -> tuple[bool, dict]:
    return True, {"msg": "change ok", "card": "T-ops-001"}


def _write_env(tmp_path: Path) -> str:
    """写一份可用的 config.env。"""
    env = tmp_path / "config.env"
    env.write_text(
        "\n".join(
            [
                "ENGINE_PORT=8101",
                "BOARD_PORT=8102",
                "WEB_PORT=8103",
                "DATA_DIR=/tmp/ccc2/data",
                "LOG_DIR=/tmp/ccc2/logs",
                "EXECUTOR_REGISTRY_PATH=/tmp/ccc2/executors.json",
                "SCHEDULER_INTERVAL=60",
                "SCHEDULER_DISPATCH_DIR=",
                "CLUSTER_TARGETS=",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return str(env)


class TestTaskRegistry:
    """注册表：注册、分类筛选。"""

    def test_register_and_list(self) -> None:
        registry = TaskRegistry()
        t1 = ScheduledTask(name="t1", task_type=TASK_TYPE_READONLY, run=_dummy_readonly_ok)
        t2 = ScheduledTask(name="t2", task_type=TASK_TYPE_CHANGE, run=_dummy_change_ok)
        registry.register(t1)
        registry.register(t2)
        assert len(registry.list_readonly()) == 1
        assert len(registry.list_change()) == 1
        assert registry.list_readonly()[0].name == "t1"
        assert registry.list_change()[0].name == "t2"

    def test_empty_registry(self) -> None:
        registry = TaskRegistry()
        assert registry.list_readonly() == []
        assert registry.list_change() == []


class TestRunTasks:
    """任务执行逻辑。"""

    def test_readonly_tasks_always_run(self) -> None:
        registry = TaskRegistry()
        registry.register(
            ScheduledTask(
                name="r1",
                task_type=TASK_TYPE_READONLY,
                run=_dummy_readonly_ok,
            )
        )
        results = run_tasks(registry, {"SCHEDULER_DISPATCH_DIR": ""})
        assert len(results) == 1
        assert results[0]["name"] == "r1"
        assert results[0]["ok"] is True

    def test_change_tasks_skipped_without_dispatch_dir(self) -> None:
        registry = TaskRegistry()
        registry.register(
            ScheduledTask(
                name="c1",
                task_type=TASK_TYPE_CHANGE,
                run=_dummy_change_ok,
            )
        )
        results = run_tasks(registry, {"SCHEDULER_DISPATCH_DIR": ""})
        assert len(results) == 1
        assert results[0]["name"] == "c1"
        assert results[0]["ok"] is True
        assert results[0]["summary"]["skipped"] is True

    def test_change_tasks_run_with_dispatch_dir(self) -> None:
        registry = TaskRegistry()
        registry.register(
            ScheduledTask(
                name="c1",
                task_type=TASK_TYPE_CHANGE,
                run=_dummy_change_ok,
            )
        )
        results = run_tasks(registry, {"SCHEDULER_DISPATCH_DIR": "/tmp/dispatch"})
        assert len(results) == 1
        assert results[0]["name"] == "c1"
        assert results[0]["ok"] is True
        assert results[0]["summary"]["card"] == "T-ops-001"

    def test_mixed_tasks(self) -> None:
        registry = TaskRegistry()
        registry.register(
            ScheduledTask(
                name="r1",
                task_type=TASK_TYPE_READONLY,
                run=_dummy_readonly_ok,
            )
        )
        registry.register(
            ScheduledTask(
                name="r2",
                task_type=TASK_TYPE_READONLY,
                run=_dummy_readonly_fail,
            )
        )
        registry.register(
            ScheduledTask(
                name="c1",
                task_type=TASK_TYPE_CHANGE,
                run=_dummy_change_ok,
            )
        )
        results = run_tasks(registry, {"SCHEDULER_DISPATCH_DIR": "/tmp/dispatch"})
        assert len(results) == 3
        names = [r["name"] for r in results]
        assert names == ["r1", "r2", "c1"]

    def test_run_once_wrapper(self) -> None:
        registry = TaskRegistry()
        registry.register(
            ScheduledTask(
                name="r1",
                task_type=TASK_TYPE_READONLY,
                run=_dummy_readonly_ok,
            )
        )
        results = run_once(registry, {"SCHEDULER_DISPATCH_DIR": ""})
        assert len(results) == 1

    def test_exception_task_isolated(self) -> None:
        """任务抛异常：打日志标记 crashed，不中断后续任务（P0 加固）。"""

        def _boom(cfg: dict) -> tuple[bool, dict]:
            raise RuntimeError("boom")

        registry = TaskRegistry()
        registry.register(ScheduledTask(name="boom", task_type=TASK_TYPE_READONLY, run=_boom))
        registry.register(ScheduledTask(name="ok", task_type=TASK_TYPE_READONLY, run=_dummy_readonly_ok))
        results = run_tasks(registry, {"SCHEDULER_DISPATCH_DIR": ""})
        by_name = {r["name"]: r for r in results}
        assert by_name["boom"]["ok"] is False
        assert by_name["boom"].get("crashed") is True
        assert by_name["ok"]["ok"] is True
        # 顺序保持注册序：boom 在前、ok 在后
        assert [r["name"] for r in results] == ["boom", "ok"]

    def test_timeout_task_abandoned(self) -> None:
        """任务超时：超时自动放弃（ok=False/crashed），不阻塞后续任务（P0 加固）。"""

        def _hang(cfg: dict) -> tuple[bool, dict]:
            time.sleep(10)
            return True, {}

        registry = TaskRegistry()
        registry.register(ScheduledTask(name="hang", task_type=TASK_TYPE_READONLY, run=_hang))
        registry.register(ScheduledTask(name="fast", task_type=TASK_TYPE_READONLY, run=_dummy_readonly_ok))
        results = run_tasks(registry, {"SCHEDULER_DISPATCH_DIR": "", "SCHEDULER_TASK_TIMEOUT": "1"})
        by_name = {r["name"]: r for r in results}
        assert by_name["hang"]["ok"] is False
        assert by_name["hang"].get("crashed") is True
        assert by_name["hang"]["summary"].get("timeout") is True
        assert by_name["fast"]["ok"] is True


class TestMainCli:
    """CLI 入口冒烟。"""

    def test_missing_config_argument(self) -> None:
        """缺 --config：argparse 以退出码 2 报错。"""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    def test_once_smoke(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """--once 有配置：退出码 0，输出 JSON 结果。"""
        env = _write_env(tmp_path)
        code = main(["--config", env, "--once"])
        out = capsys.readouterr().out
        assert code == 0
        results = json.loads(out)
        assert isinstance(results, list)
        # 默认注册表含 cluster-collect 任务
        assert any(r["name"] == "cluster-collect" for r in results)

    def test_once_with_interval_override(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """--once 可搭配 --interval（虽不影响单次，但应被解析）。"""
        env = _write_env(tmp_path)
        code = main(["--config", env, "--once", "--interval", "120"])
        assert code == 0
        out = capsys.readouterr().out
        results = json.loads(out)
        assert isinstance(results, list)
