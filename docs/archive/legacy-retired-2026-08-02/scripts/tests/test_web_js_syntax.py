"""前端 JS 语法自检 — node --check 全量。

窗口 A（web 前端修复）前端行为测试之一。沿用现有基建里的 node subprocess 用法
（test_epic_five_state.py 已内嵌 node 跑 pure-JS 单测）。CI 无 node 时优雅跳过，
不拖垮全绿。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
FRONTEND = SCRIPTS / "chat_server" / "frontend"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(
    NODE is None, reason="node 不在 PATH（CI 无 JS 依赖时优雅跳过）"
)


def _js_files() -> list[Path]:
    return sorted((FRONTEND / "js").rglob("*.js"))


def test_all_frontend_js_syntax():
    files = _js_files()
    assert files, "frontend/js 下应有 JS 文件"
    failures: list[str] = []
    for f in files:
        r = subprocess.run(
            [NODE, "--check", str(f)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            failures.append(f"{f.relative_to(SCRIPTS)}:\n{r.stderr.strip()}")
    assert not failures, "JS 语法错误:\n" + "\n".join(failures)
