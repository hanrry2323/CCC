"""test_board_visibility — 看板可见性统一（ccc-plan-048 P1）。

回归目标：
1. loader 移除 platform 前缀豁免后，CCC 平台卡（docs/dispatch/ccc/）正式入板；
2. registry 中每个 taskable/platform 项目在看板可见集合中至少有 1 张卡（无项目黑洞）。

基于真实 docs/dispatch 数据断言，不 mock 卡文件。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from server.board.loader import load_dispatch_cards
from server.board.registry import load_projects, platform_prefixes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISPATCH_DIR = PROJECT_ROOT / "docs" / "dispatch"


@pytest.fixture(autouse=True)
def _isolate_board_index_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """索引写入隔离（ccc088）：真实 docs/dispatch 只许读不许写。

    pytest 进程内 get_index_path 对非空 dispatch_dir 返回
    `<dispatch_dir>/cards.index.jsonl`，load_dispatch_cards 的增量副作用会把
    索引写进真实仓（主仓/worktree 双双中招）。重定向 get_index_path 到
    tmp_path 后本文件的纯读断言不受影响；不能只 delenv PYTEST_CURRENT_TEST——
    pytest 进入 call 阶段会重设该变量（实测复现）。
    """
    from server.board import loader

    monkeypatch.setattr(
        loader, "get_index_path",
        lambda dispatch_dir=None: tmp_path / "cards" / "cards.index.jsonl",
    )
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def _visible_items():
    return load_dispatch_cards(DISPATCH_DIR, include_archived=True)


def test_loader_includes_platform_cards() -> None:
    """平台卡入板：load_dispatch_cards 结果必须含 id 前缀 ccc 的卡。"""
    items = _visible_items()
    ccc_ids = [i.id for i in items if i.id.startswith("ccc")]
    assert ccc_ids, (
        "平台卡未入板：load_dispatch_cards 结果不含任何 ccc 前缀卡"
        "（ccc-plan-048 要求移除 items 层 platform 过滤）"
    )
    # 与磁盘实况对齐：docs/dispatch/ccc/ 下任务卡应全部出现在结果中
    disk_ccc = {
        p.stem.split("-")[0]
        for p in (DISPATCH_DIR / "ccc").glob("*.md")
    }
    loaded_ccc = {i.id for i in items if i.id.startswith("ccc")}
    assert disk_ccc <= loaded_ccc, f"磁盘 ccc 卡缺失于装载结果: {sorted(disk_ccc - loaded_ccc)}"


def test_no_project_blackhole() -> None:
    """无项目黑洞：registry 每个 taskable/platform 项目的卡片数 >= 1。"""
    items = _visible_items()
    counts = Counter(i.project for i in items)
    expected = [
        p.prefix
        for p in load_projects()
        if p.prefix and (p.taskable or p.category == "platform")
    ]
    missing = [pfx for pfx in sorted(expected) if counts.get(pfx, 0) < 1]
    assert not missing, (
        f"registry 项目在看板可见集合中无任何卡片: {missing}；"
        f"实际计数: {dict(sorted(counts.items()))}"
    )
    # 平台前缀与 taskable 集合非空，防止断言因 registry 解析失败而空转
    assert "ccc" in platform_prefixes(), "registry 应含 platform 前缀 ccc"
    assert expected, "registry 未解析出任何 taskable/platform 项目前缀"
