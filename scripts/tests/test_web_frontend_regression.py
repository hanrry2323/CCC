"""第一波修复回归锁 — 直接读前端源码断言修复不丢（窗口 A2 回归固化）。

锁住 task-A（b75e084）的 6 项修复 + 本轮 A2 的契约/聊天修复标记：
- CSS：--ops-amber、.ops-pill-green、.board-ws、.att-file-icon
- JS：无硬编码 192.168.3.140、用 dialogueEntryUrl/agentUrl('/health')
- 契约：ops 日审读 dailyItems（含 reports）
- 聊天：错误气泡标记 + removeStreamingCursors
"""

from __future__ import annotations

from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
FE = SCRIPTS / "chat_server" / "frontend"


def _read(rel: str) -> str:
    return (FE / rel).read_text(encoding="utf-8")


def test_css_ops_amber_var():
    assert "--ops-amber" in _read("css/variables.css")


def test_css_ops_pill_green():
    assert ".ops-pill-green" in _read("css/shell.css")


def test_css_board_ws_class():
    assert ".board-ws {" in _read("css/shell.css")


def test_css_att_file_icon():
    assert ".att-file-icon" in _read("css/components.css")


def test_board_page_no_hardcoded_m1_ip():
    src = _read("js/pages/boardPage.js")
    assert "192.168.3.140" not in src, "看板页不得硬编码 M1 IP"
    assert "dialogueEntryUrl" in src, "看板页用 dialogueEntryUrl"


def test_ops_page_no_hardcoded_m1_ip():
    src = _read("js/pages/opsPage.js")
    assert "192.168.3.140" not in src, "运维页不得硬编码 M1 IP"
    assert "dialogueEntryUrl" in src, "运维页用 dialogueEntryUrl"


def test_composer_uses_agent_url_health():
    src = _read("js/components/composer.js")
    assert "agentUrl('/health')" in src, "composer 用 agentUrl('/health')"
    assert "fetch('/health')" not in src, "composer 不得裸 fetch('/health')"


def test_ops_daily_reads_reports():
    assert "dailyItems" in _read("js/pages/opsPage.js"), "ops 页用 dailyItems"
    assert "d.reports" in _read("js/opsSelectors.js"), "dailyItems 兼容 reports"


def test_chat_error_bubble_markers():
    src = _read("js/components/message.js")
    assert "renderErrorBubble" in src, "错误气泡渲染"
    assert "removeStreamingCursors" in src, "取消后清光标"
    assert "kind: 'error'" in src or "kind === 'error'" in src, "错误消息持久化标记"


def test_chat_composer_cancel_clears_cursor():
    src = _read("js/components/composer.js")
    assert "removeStreamingCursors" in src, "composer 取消 handler 清光标"
