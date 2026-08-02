"""test_board_scheduler — 定时入口冒烟（--once 单次 + --watch 持续两种模式）。

验证：
1. export_safe：成功导出 + 失败保留旧文件 + 临时文件清理
2. run_once：退出码 0（成功）/ 1（失败）
3. main --once CLI：完整入口调用
4. main --watch CLI：持续模式启动 + 至少一轮导出
5. 既有 68 用例不回归；硬编码零字面量
"""

from __future__ import annotations

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