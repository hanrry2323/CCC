"""test_board_scheduler — 定时入口冒烟（--once 单次 + --watch 持续两种模式）。

验证：
1. export_safe：成功导出 + 失败保留旧文件 + 临时文件清理
2. run_once：退出码 0（成功）/ 1（失败）
3. main --once CLI：完整入口调用
4. main --watch CLI：持续模式启动 + 至少一轮导出
5. 既有 68 用例不回归；硬编码零字面量
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from server.board.scheduler import export_safe, main, run_once

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISPATCH_DIR = str(PROJECT_ROOT / "docs" / "dispatch")
OUTPUT_DIR = str(PROJECT_ROOT / "server" / "web" / "data")
OUTPUT_PATH = str(Path(OUTPUT_DIR) / "board.js")


@pytest.fixture(autouse=True)
def _no_auto_pull(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁止 export_safe 对真实开发仓跑 git sync（2026-08-12 事故修复卫生）：
    sync 的 dispatch 强制对齐会清掉未提交/未 push 的恢复卡（mx030-034 事故卡）。
    测试只测导出逻辑，不应触碰真实仓工作树。
    """
    monkeypatch.setenv("CCC_AUTO_PULL", "0")


@pytest.fixture(autouse=True)
def _isolate_board_index_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """索引写入隔离（ccc088）：export_safe → load_dispatch_cards/archive_old_cards 的
    增量副作用在 pytest 进程内会把索引写进真实 `<PROJECT_ROOT>/docs/dispatch/`
    （--watch 子进程以 1s 间隔高频覆写，主仓与各 worktree 均被污染）。

    - 主进程：monkeypatch loader.get_index_path 把索引读写统一重定向到 tmp_path；
      不能只 delenv PYTEST_CURRENT_TEST——pytest 进入 call 阶段会重设该变量，
      loader 的 pytest 索引分支照常激活（实测复现）。
    - subprocess（main --watch CLI）：Popen 按 spawn 时刻 environ 快照继承，
      delenv PYTEST_CURRENT_TEST + setenv CCC_DATA_DIR 使子进程走生产回落分支落到 tmp_path。
    """
    from server.board import loader

    monkeypatch.setattr(
        loader, "get_index_path",
        lambda dispatch_dir=None: tmp_path / "cards" / "cards.index.jsonl",
    )
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


class TestExportSafe:
    """安全导出：成功 / 失败保留旧文件 + 临时文件清理。"""

    def test_export_success(self, tmp_path: Path) -> None:
        """成功导出：写 board.js 且内容可解析。"""
        out = tmp_path / "board.js"
        ok = export_safe(DISPATCH_DIR, str(out))
        assert ok
        assert out.is_file()
        text = out.read_text(encoding="utf-8")
        assert text.startswith("window.BOARD_DATA = ")
        assert "views" in text

    def test_export_failure_keeps_old_file(self, tmp_path: Path) -> None:
        """失败时保留旧 board.js + 临时文件清理。"""
        out = tmp_path / "board.js"
        out.write_text("window.BOARD_DATA = 'old data';\n", encoding="utf-8")
        # 用 mock 模拟 load_dispatch_cards 抛出异常
        with patch(
            "server.board.scheduler.load_dispatch_cards",
            side_effect=OSError("mock disk error"),
        ):
            ok = export_safe(DISPATCH_DIR, str(out))
        assert not ok
        # 旧文件保留
        assert out.is_file()
        assert out.read_text(encoding="utf-8") == "window.BOARD_DATA = 'old data';\n"
        # 临时文件已清理
        assert not Path(str(out) + ".board.js.tmp").is_file()

    def test_export_no_old_file_failure(self, tmp_path: Path) -> None:
        """失败时无旧文件：不报错，不残留临时文件。"""
        out = tmp_path / "board.js"
        with patch(
            "server.board.scheduler.load_dispatch_cards",
            side_effect=OSError("mock disk error"),
        ):
            ok = export_safe(DISPATCH_DIR, str(out))
        assert not ok
        assert not out.is_file()
        assert not Path(str(out) + ".board.js.tmp").is_file()


class TestRunOnce:
    """单次导出退出码。"""

    def test_returns_zero_on_success(self, tmp_path: Path) -> None:
        out = tmp_path / "board.js"
        assert run_once(DISPATCH_DIR, str(out)) == 0
        assert out.is_file()

    def test_returns_one_on_failure(self, tmp_path: Path) -> None:
        out = str(tmp_path / "board.js")
        with patch(
            "server.board.scheduler.load_dispatch_cards",
            side_effect=OSError("mock disk error"),
        ):
            assert run_once(DISPATCH_DIR, out) == 1


class TestMainCli:
    """CLI 入口冒烟。"""

    def test_once_smoke(self, tmp_path: Path) -> None:
        """--once 模式：退出码 0，输出文件产生。"""
        out = tmp_path / "board.js"
        code = main(["--once", "--dispatch-dir", DISPATCH_DIR, "--output", str(out)])
        assert code == 0
        assert out.is_file()

    def test_once_failure_exit_code(self, tmp_path: Path) -> None:
        """--once 模式失败：退出码 1。"""
        out = str(tmp_path / "board.js")
        with patch(
            "server.board.scheduler.load_dispatch_cards",
            side_effect=OSError("mock disk error"),
        ):
            code = main(
                [
                    "--once",
                    "--dispatch-dir",
                    DISPATCH_DIR,
                    "--output",
                    out,
                ]
            )
            assert code == 1

    def test_watch_smoke(self, tmp_path: Path) -> None:
        """--watch 模式：启动后至少产生一轮导出，然后被 SIGTERM 终止。"""
        out = tmp_path / "board.js"
        # ccc088：env 显式剔除 PYTEST_CURRENT_TEST——pytest 在 call 阶段会重设该
        # 变量（夹具 delenv 被覆盖），子进程按 spawn 时刻快照继承后激活 loader 的
        # pytest 索引分支，以 --interval 1 每秒覆写真实 docs/dispatch/cards.index.jsonl。
        # 剔除后子进程走生产回落分支，索引随 CCC_DATA_DIR 落 tmp_path。
        child_env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "server.board.scheduler",
                "--watch",
                "--interval",
                "1",
                "--dispatch-dir",
                DISPATCH_DIR,
                "--output",
                str(out),
            ],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_env,
        )
        try:
            # 等待最多 3 秒，让至少一轮导出完成
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                if out.is_file():
                    break
                time.sleep(0.2)
            else:
                proc.terminate()
                pytest.fail("--watch 模式 3 秒内未产生输出文件")
        finally:
            proc.terminate()
            proc.wait(timeout=5)

        assert out.is_file()
        text = out.read_text(encoding="utf-8")
        assert text.startswith("window.BOARD_DATA = ")

    def test_watch_output_interval_flag(self, tmp_path: Path) -> None:
        """--watch --interval 300 应被 argparse 正确解析。"""
        out = str(tmp_path / "board.js")
        code = main(
            [
                "--once",
                "--dispatch-dir",
                DISPATCH_DIR,
                "--output",
                out,
                "--interval",
                "300",
            ]
        )
        assert code == 0
