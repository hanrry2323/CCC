import ast
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.engine.observer import _get_current_state, should_run, run_observer

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ast_import_whitelist():
    """AST 校验 observer import 白名单：禁止导入写接口和变更函数。"""
    observer_file = PROJECT_ROOT / "server" / "engine" / "observer.py"
    assert observer_file.exists()

    code = observer_file.read_text(encoding="utf-8")
    tree = ast.parse(code)

    forbidden_modules = {"server.engine.store"}
    allowed_from_plans = {"list_plans"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                assert name.name not in forbidden_modules, f"Forbidden import: {name.name}"
                assert "store" not in name.name, f"Forbidden store import: {name.name}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module:
                assert module not in forbidden_modules, f"Forbidden import from module: {module}"
                assert "store" not in module, f"Forbidden store import from module: {module}"
                if "plans" in module:
                    for name in node.names:
                        assert name.name in allowed_from_plans, f"Forbidden plans import: {name.name}"


def test_should_run_scenarios(tmp_path):
    """测试不同场景下的调度门槛（last-run 时间戳和变更触发）。"""
    cfg = {"DATA_DIR": str(tmp_path)}
    observer_dir = tmp_path / "observer"
    observer_dir.mkdir(parents=True, exist_ok=True)
    last_run_file = observer_dir / "last-run.json"

    # 1. 首次运行：没有 last-run.json，应该运行
    current = {
        "timestamp": time.time(),
        "git_commit": "commit1",
        "cards_index_mtime": 100.0,
        "cards_index_size": 1000,
    }
    ok, reason = should_run(cfg, current)
    assert ok is True
    assert "first run" in reason

    # 写入 last-run.json 作为基准
    last_run_file.write_text(json.dumps(current))

    # 2. 24 小时未过，且无任何变更：应该跳过
    current_same = current.copy()
    current_same["timestamp"] += 1000  # 只过了 1000 秒
    ok, reason = should_run(cfg, current_same)
    assert ok is False
    assert "thresholds not met" in reason

    # 3. 24 小时已过：应该运行
    current_later = current.copy()
    current_later["timestamp"] += 86500  # 过了 24 小时多
    ok, reason = should_run(cfg, current_later)
    assert ok is True
    assert "24 hours passed" in reason

    # 4. 24 小时未过，但是 git commit 变更：应该运行
    current_new_commit = current.copy()
    current_new_commit["timestamp"] += 1000
    current_new_commit["git_commit"] = "commit2"
    ok, reason = should_run(cfg, current_new_commit)
    assert ok is True
    assert "new merge commit" in reason

    # 5. 24 小时未过，但是 cards.index.jsonl mtime 变更：应该运行
    current_new_mtime = current.copy()
    current_new_mtime["timestamp"] += 1000
    current_new_mtime["cards_index_mtime"] = 101.0
    ok, reason = should_run(cfg, current_new_mtime)
    assert ok is True
    assert "cards.index.jsonl changed" in reason


@patch("server.engine.observer.load_projects")
@patch("server.engine.observer.load_dispatch_cards")
@patch("server.engine.observer.list_plans")
def test_run_observer_output(mock_list_plans, mock_load_dispatch_cards, mock_load_projects, tmp_path):
    """测试 run_observer 在决定运行时，是否能正常输出 snapshot 和 last-run。"""
    cfg = {
        "DATA_DIR": str(tmp_path),
        "OBSERVER_FORCE": "true",  # 强行运行以跳过 should_run 限制
    }

    # 模拟数据
    mock_load_projects.return_value = []
    mock_load_dispatch_cards.return_value = []
    mock_list_plans.return_value = []

    ok, summary = run_observer(cfg)
    assert ok is True
    assert "projects_count" in summary
    assert "cards_count" in summary
    assert "plans_count" in summary

    observer_dir = tmp_path / "observer"
    assert (observer_dir / "last-run.json").exists()
    assert (observer_dir / "snapshot.json").exists()

    # 读取并验证内容
    with open(observer_dir / "snapshot.json", "r", encoding="utf-8") as f:
        snapshot = json.load(f)
        assert snapshot["projects_count"] == 0
        assert snapshot["cards_count"] == 0
        assert snapshot["plans_count"] == 0
