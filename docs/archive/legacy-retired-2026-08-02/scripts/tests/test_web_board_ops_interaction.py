"""窗口 J 结构锁 — 看板筛选/排序 + 轮询竞态 + 运维只看红灯（源码断言）。

沿用 test_web_frontend_regression.py 模式：直接读前端源码断言修复不丢。
覆盖任务书 J 验收：筛选/排序入口可用、轮询与移卡竞态有锁、只看红灯聚合可用。
"""

from __future__ import annotations

from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
FE = SCRIPTS / "chat_server" / "frontend"


def _read(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


# ── 看板：筛选/排序 UI 入口 ────────────────────────────────────────


def test_board_page_uses_filter_pure_module():
    src = _read("js/pages/boardPage.js")
    assert "boardFilter" in src, "引用 boardFilter"
    assert "matchesKeyword" in src and "sortTasks" in src, "关键词 + 排序函数接入"


def test_board_page_split_status_filter():
    src = _read("js/pages/boardPage.js")
    assert "filterEpicsBySplit" in src, "大卡 split_status 筛选接入"


def test_board_page_filter_controls_present():
    src = _read("js/pages/boardPage.js")
    assert 'id="board-filter-q"' in src, "关键词输入框"
    assert 'id="board-filter-status"' in src, "大卡状态筛选控件"
    assert 'id="board-sort"' in src, "排序控件"


def test_board_page_filter_rerender_no_refetch():
    """筛选/排序变更只重绘不重新请求：loadBoard 仍是唯一拉取入口。"""
    src = _read("js/pages/boardPage.js")
    assert "renderCols()" in src, "筛选变更走 renderCols 重绘"


# ── 看板：轮询与移卡竞态锁 ─────────────────────────────────────────


def test_board_page_load_gate_wired():
    src = _read("js/pages/boardPage.js")
    assert "createLoadGate" in src, "竞态门导入"
    assert "_gate.suppress()" in src, "移卡期间 suppress"
    assert "_gate.resume()" in src, "移卡后 resume"
    assert "isLatest" in src, "latest-wins 丢弃旧响应"


def test_board_page_epic_progress_still_full_released():
    """epic 进度仍读完整 released 集（筛选不破坏进度条刷新）。"""
    src = _read("js/pages/boardPage.js")
    assert "cols.released" in src, "released 集合保持完整"


# ── 运维：只看红灯聚合 ─────────────────────────────────────────────


def test_ops_page_uses_red_pure_module():
    src = _read("js/pages/opsPage.js")
    assert "collectRedItems" in src, "引用 opsRed"
    assert "redCount" in src, "红灯计数"


def test_ops_page_red_toggle_present():
    src = _read("js/pages/opsPage.js")
    assert 'id="ops-red-toggle"' in src, "只看红灯开关"
    assert 'id="ops-red-aggregate"' in src, "红灯聚合区"
    assert "ops-red-only" in src, "red-only 根类切换"


def test_ops_page_red_aggregate_render():
    src = _read("js/pages/opsPage.js")
    assert "renderRedAggregate" in src, "聚合渲染函数"
    assert "RED_DOMAIN_LABELS" in src, "域中文标签"


def test_ops_page_existing_render_intact():
    """既有各域渲染与降级保持：poll 内原有 render 调用未被移除。"""
    src = _read("js/pages/opsPage.js")
    for frag in ("renderStatus", "renderAlerts", "renderLogistics", "renderRelay", "renderAuto"):
        assert frag in src, f"{frag} 保留"


# ── CSS：筛选栏 + red-only 样式 ────────────────────────────────────


def test_css_board_filter_toolbar():
    css = _read("css/shell.css")
    assert ".board-toolbar-filters" in css, "看板筛选栏样式"
    assert ".board-filter-input" in css, "关键词输入样式"


def test_css_ops_red_only_rules():
    css = _read("css/shell.css")
    assert ".ops-page.ops-red-only" in css, "red-only 隐藏规则"
    assert "#ops-red-aggregate" in css, "聚合区样式"
    assert ".ops-red-item" in css, "红灯条目样式"
