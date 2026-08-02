"""test_board_loader — 任务卡解析 + 字段缺失容错。"""

from __future__ import annotations

from pathlib import Path

from server.board.loader import load_dispatch_cards, parse_card

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DISPATCH_DIR = PROJECT_ROOT / "docs" / "dispatch"

SAMPLE = """# 任务卡 T99 · 示例任务（示例执行体）

> 关联：PRJ-X（示例）· 契约：测试契约 · 管理席：Codex
> 执行体：示例执行体（CLI）· 验收：Codex · 状态：执行中 · 日期：2026-07-28
> 依赖：T1

## 正文

## 回写区

**执行体**：示例执行体（CLI）
**日期**：2026-08-01
**实现 commit**：abc123
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestParseCard:
    """解析完整字段。"""

    def test_parse_full(self, tmp_path: Path) -> None:
        item = parse_card(_write(tmp_path, "T99.md", SAMPLE))
        assert item.id == "T99"
        assert item.state == "执行中"
        assert item.project == "PRJ-X"          # 关联取括号前
        assert item.executor == "示例执行体"      # 执行体取括号前
        assert item.dispatched_at == "2026-07-28"  # 元数据日期
        assert item.written_at == "2026-08-01"     # 回写区日期
        assert item.reject_count == 0

    def test_parse_explicit_reject_count(self, tmp_path: Path) -> None:
        content = SAMPLE + "\n打回次数：2\n"
        item = parse_card(_write(tmp_path, "T98.md", content))
        assert item.reject_count == 2

    def test_state_rejected_implies_reject(self, tmp_path: Path) -> None:
        content = "# 任务卡 T97 · 被拒\n\n> 执行体：某工具 · 状态：打回 · 日期：2026-08-01\n"
        item = parse_card(_write(tmp_path, "T97.md", content))
        assert item.state == "打回"
        assert item.reject_count == 1

    def test_missing_fields_unknown(self, tmp_path: Path) -> None:
        """字段缺失容错：标「未知」不崩溃，ID 回退文件名。"""
        item = parse_card(_write(tmp_path, "minimal.md", "# 随便写的东西\n没有任务卡格式\n"))
        assert item.id == "minimal"
        assert item.state == "未知"
        assert item.project == "未知"
        assert item.executor == "未知"
        assert item.dispatched_at == "未知"
        assert item.written_at == "未知"
        assert item.reject_count == 0

    def test_executor_without_parenthesis(self, tmp_path: Path) -> None:
        content = "# 任务卡 T96 · 无括号\n\n> 执行体：纯名字 · 状态：待分派\n"
        item = parse_card(_write(tmp_path, "T96.md", content))
        assert item.executor == "纯名字"

    def test_parse_state_with_parenthesis(self, tmp_path: Path) -> None:
        """带括号状态变体：明细保留全串；基础态=打回 → 隐含打回次数 1。"""
        content = "# 任务卡 T95 · 变体\n\n> 执行体：某工具 · 状态：打回（原因） · 日期：2026-08-01\n"
        item = parse_card(_write(tmp_path, "T95.md", content))
        assert item.state == "打回（原因）"
        assert item.reject_count == 1


class TestLoadDispatchCards:
    """扫描目录 + 真实任务卡。"""

    def test_load_directory(self, tmp_path: Path) -> None:
        _write(tmp_path, "any-name.md", SAMPLE)
        items = load_dispatch_cards(tmp_path)
        # ID 取标题（T99）而非文件名
        assert [i.id for i in items] == ["T99"]

    def test_real_dispatch_cards(self) -> None:
        """真实 docs/dispatch 4 张卡全部可解析。"""
        items = load_dispatch_cards(DISPATCH_DIR)
        ids = {item.id for item in items}
        assert {"T1", "T1-R", "T2", "T3"} <= ids
        for item in items:
            assert item.state in {"待分派", "执行中", "已回写", "已关闭", "打回", "未知"}
