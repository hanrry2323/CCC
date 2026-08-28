"""任务三 · 单一事实源收敛测试（rebuild/phase2）。

- 卡片索引唯一化：get_index_path 永不回落仓内 data/，production=~/.ccc/data。
- loader 写入点唯一：子进程（无 pytest env）验证索引只落 DATA_DIR/cards。
- ledger 探针/真值打标：record_audit probe 字段。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from server.board import loader
from server.board import audit_ledger


def test_get_index_path_no_env_is_production(monkeypatch) -> None:
    """无 env 兜底 = ~/.ccc/data/cards/cards.index.jsonl（不再回落仓内 data/）。"""
    monkeypatch.delenv("CCC_DATA_DIR", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    p = loader.get_index_path(None)
    assert p == Path.home() / ".ccc" / "data" / "cards" / "cards.index.jsonl"
    assert "program/CCC/data" not in str(p)


def test_get_index_path_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    assert loader.get_index_path(None) == tmp_path / "cards" / "cards.index.jsonl"


def test_get_index_path_pytest_isolation(monkeypatch, tmp_path: Path) -> None:
    """pytest 下走 dispatch_dir 临时索引（测试隔离，非生产写点）。"""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "x")
    assert loader.get_index_path(tmp_path) == tmp_path / "cards.index.jsonl"


def test_loader_writes_single_path_only(tmp_path: Path) -> None:
    """子进程（无 pytest env）验证：DATA_DIR 唯一写点，仓内 data/ 与 dispatch 不再分叉。"""
    dispatch = tmp_path / "dispatch"
    (dispatch / "tst").mkdir(parents=True)
    card = dispatch / "tst" / "tst001-ssot.md"
    card.write_text(
        "# 任务卡 tst001 · SSOT\n"
        "> 关联：测试 · 执行体：DSH · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：tst · 日期：2026-08-28\n\n"
        "## 目标\nx\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "data-root"
    repo = str(Path(__file__).resolve().parents[2])
    script = (
        "import sys; sys.path.insert(0, {repo!r})\n"
        "from server.board.loader import load_dispatch_cards, get_index_path\n"
        "items = load_dispatch_cards({dispatch!r}, include_archived=False)\n"
        "print('items', len(items))\n"
        "print('index', get_index_path())\n"
    )
    script = script.format(repo=repo, dispatch=str(dispatch))
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    # 打回修复：全量测试序中其它用例可能泄漏 CCC_DATA_DIR/DATA_DIR 到 os.environ，
    # 子进程必须显式钉死唯一写点（防继承污染），否则 loader 写点漂移。
    env["CCC_DATA_DIR"] = str(data_dir)
    env["DATA_DIR"] = str(data_dir)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "items 1" in r.stdout
    # 唯一写点：data-root/cards/cards.index.jsonl
    assert (data_dir / "cards" / "cards.index.jsonl").is_file()
    # 仓内 data/ 与 dispatch 内不再出现索引副本
    assert not (dispatch / "cards.index.jsonl").exists()


def test_record_audit_probe_field(tmp_path: Path, monkeypatch) -> None:
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(ledger))
    audit_ledger.record_audit("tst001", "tst001", conclusion="不通过", probe=True)
    audit_ledger.record_audit("tst002", "tst002", conclusion="通过", probe=False)
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert rows[0]["probe"] is True
    assert rows[1]["probe"] is False
    assert rows[0]["kind"] == "audit"
