"""test_t53_console_roadmap — T53 前端渲染契约（控制台后台任务进程面板 + 线路图按项目）。

仓库无 JS 测试运行时（零新依赖红线），以静态契约断言验证前端渲染结构：
- consolePage.js：新增「后台任务进程」面板、/tasks/running 数据源、8 秒轮询、空态文案；
- roadmapPage.js：按 /board/roadmap by_project 渲染 + 项目名/计数分隔修正。
真实浏览器渲染由 Codex 验收时 headless 验证（验收标准 3）。
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGES_DIR = PROJECT_ROOT / "server" / "web" / "legacy-chat" / "js" / "pages"


def _page(name: str) -> str:
    return (PAGES_DIR / name).read_text(encoding="utf-8")


class TestConsolePage:
    """控制台：后台任务进程面板渲染契约。"""

    @staticmethod
    def _console() -> str:
        return _page("consolePage.js")

    def test_has_running_panel_markup(self) -> None:
        text = self._console()
        assert "后台任务进程" in text
        assert "console-running" in text
        assert "当前无后台任务" in text

    def test_polls_tasks_running_every_8s(self) -> None:
        text = self._console()
        assert "/tasks/running" in text
        assert "8000" in text  # 8 秒轮询（T53；SSE 实时推送后置 T49）
        assert "pollRunning" in text

    def test_running_card_renders_process_fields(self) -> None:
        text = self._console()
        for token in ("log_tail", "elapsed_s", "last_activity_at", "日志尾", "已用时", "indeterminate"):
            assert token in text, f"后台任务进程卡片缺渲染字段: {token}"

    def test_keeps_board_poll(self) -> None:
        text = self._console()
        assert "15000" in text  # 看板快照轮询仍在


class TestRoadmapPage:
    """线路图：按项目聚合渲染契约。"""

    @staticmethod
    def _roadmap() -> str:
        return _page("roadmapPage.js")

    def test_renders_by_project_data(self) -> None:
        text = self._roadmap()
        assert "by_project" in text
        assert "roadmap-proj-row" in text

    def test_project_name_count_separated(self) -> None:
        """修正「INT-12047」「阶段 3 P12」乱分组：项目名与计数之间加分隔。"""
        text = self._roadmap()
        assert "roadmap-proj-total" in text
        # 项目名与计数显式用「· 共 N 卡」分隔，不再数字紧贴
        assert "· 共 " in text and " 卡" in text

    def test_hint_mentions_project_aggregation(self) -> None:
        text = self._roadmap()
        assert "按项目聚合" in text
