"""test_board_visibility — 看板可见性统一（ccc-plan-048 P1）。

回归目标：
1. loader 移除 platform 前缀豁免后，CCC 平台卡正式入板；
2. registry 中每个 taskable/platform 项目在看板可见集合中至少有 1 张卡（无项目黑洞）。

密闭化（rebuild/phase2 打回修复）：round-1 清场（老板拍板旧卡清零）后真实
docs/dispatch 只剩 tst 卡，原「基于真实数据断言每项目有卡」不再成立——改为
tmp dispatch 构造合成卡验证 loader 行为（平台卡入板 / 无项目黑洞），与数据量无关。
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from server.board.loader import load_dispatch_cards
from server.board.registry import load_projects, platform_prefixes

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CARD_TMPL = (
    "# 任务卡 {cid} · 可见性回归\n"
    "> 关联：t · 执行体：DSH · 验收：Claude Code · 状态：{state} · 派发：engine · 项目：{project} · 日期：2026-08-28\n\n"
    "## 目标\nx\n\n"
    "## 实现\n仅测试卡。\n\n"
    "## 回写区\n- 日期：2026-08-28\n"
)


@pytest.fixture(autouse=True)
def _isolate_board_index_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """索引写入隔离（ccc088）：真实 docs/dispatch 只许读不许写。

    pytest 进程内 get_index_path 对非空 dispatch_dir 返回
    `<dispatch_dir>/cards.index.jsonl`，load_dispatch_cards 的增量副作用会把
    索引写进真实仓。重定向 get_index_path 到 tmp_path 后本文件断言不受影响。
    """
    from server.board import loader

    monkeypatch.setattr(
        loader, "get_index_path",
        lambda dispatch_dir=None: tmp_path / "cards" / "cards.index.jsonl",
    )
    monkeypatch.setenv("CCC_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


def _write_card(d: Path, project: str, cid: str, state: str = "待分派") -> None:
    sub = d / project
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"{cid}.md").write_text(
        _CARD_TMPL.format(cid=cid, state=state, project=project),
        encoding="utf-8",
    )


def test_loader_includes_platform_cards(tmp_path: Path) -> None:
    """平台卡入板：load_dispatch_cards 结果必须含 ccc 前缀卡（不被 platform 豁免过滤）。"""
    d = tmp_path / "dispatch"
    _write_card(d, "tst", "tst998-visible", "已回写")
    _write_card(d, "ccc", "ccc999-platform", "已回写")
    items = load_dispatch_cards(d, include_archived=True)
    ids = {i.id for i in items}
    assert "ccc999-platform" in ids, (
        "平台卡未入板：load_dispatch_cards 结果不含 ccc 前缀卡"
        "（ccc-plan-048 要求移除 items 层 platform 过滤）"
    )
    assert "tst998-visible" in ids


def test_no_project_blackhole(tmp_path: Path) -> None:
    """无项目黑洞：registry 每个 taskable/platform 项目均被 loader 装载（不丢项目）。"""
    d = tmp_path / "dispatch"
    expected = [
        p.prefix
        for p in load_projects()
        if p.prefix and (p.taskable or p.category == "platform")
    ]
    assert expected, "registry 未解析出任何 taskable/platform 项目前缀"
    for pfx in expected:
        _write_card(d, pfx, f"{pfx}001-blackhole", "待分派")
    items = load_dispatch_cards(d, include_archived=True)
    counts = Counter(i.project for i in items)
    missing = [pfx for pfx in sorted(expected) if counts.get(pfx, 0) < 1]
    assert not missing, (
        f"registry 项目在看板可见集合中无任何卡片: {missing}；"
        f"实际计数: {dict(sorted(counts.items()))}"
    )
    # 平台前缀与 taskable 集合非空，防止断言因 registry 解析失败而空转
    assert "ccc" in platform_prefixes(), "registry 应含 platform 前缀 ccc"
