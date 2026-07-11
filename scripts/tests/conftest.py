"""conftest.py — pytest 配置

v0.28.0: 让 tests/test_phase_lint.py 的 TestRunLint 写文件不报 FileNotFoundError
"""
from pathlib import Path


def pytest_configure(config):
    """pytest 启动时确保 cwd/.ccc/phases/ 存在"""
    cwd = Path.cwd()
    phases_dir = cwd / ".ccc" / "phases"
    phases_dir.mkdir(parents=True, exist_ok=True)