"""test_board_loader — 任务卡解析 + 字段缺失容错。"""

from __future__ import annotations

from pathlib import Path

from server.board.loader import load_dispatch_cards, parse_card
from server.board.models import base_state

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
        """字段缺失容错：标「未知」不崩溃，ID 回退文件名；项目归「未分类」（T53）。"""
        item = parse_card(_write(tmp_path, "minimal.md", "# 随便写的东西\n没有任务卡格式\n"))
        assert item.id == "minimal"
        assert item.state == "未知"
        assert item.project == "未分类"
        assert item.executor == "未知"
        assert item.dispatched_at == "未知"
        assert item.written_at == "未知"
        assert item.reject_count == 0
        assert item.dispatch == "engine"  # 缺省派发方式

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

    # ── T53：项目 / 派发 字段 ──

    def test_project_field_overrides_related(self, tmp_path: Path) -> None:
        """卡头「项目」字段优先于「关联」推导。"""
        content = "# 任务卡 T94 · 项目字段\n\n> 关联：阶段 3 P1 · 项目：ccc · 执行体：某工具 · 状态：待分派\n"
        item = parse_card(_write(tmp_path, "T94.md", content))
        assert item.project == "ccc"

    def test_project_derived_from_related_first_segment(self, tmp_path: Path) -> None:
        """无「项目」字段 → 从「关联」首段推导（冒号/空格前 + 去括号）。"""
        content = "# 任务卡 T93 · 推导\n\n> 关联：INT-120（CCC 重构）· 状态：待分派\n"
        item = parse_card(_write(tmp_path, "T93.md", content))
        assert item.project == "INT-120"

    def test_project_derived_space_segment(self, tmp_path: Path) -> None:
        """关联含空格 → 取空格前首段。"""
        content = "# 任务卡 T92 · 空格段\n\n> 关联：阶段 3 P1 · 状态：待分派\n"
        item = parse_card(_write(tmp_path, "T92.md", content))
        assert item.project == "阶段"

    def test_project_derived_garbled_unclassified(self, tmp_path: Path) -> None:
        """关联首段含引号/括号（长句上下文）→ 归「未分类」。"""
        content = "# 任务卡 T91 · 乱码\n\n> 关联：新阶段「双壳可用 + 心智升级」收口 · 状态：待分派\n"
        item = parse_card(_write(tmp_path, "T91.md", content))
        assert item.project == "未分类"

    def test_dispatch_default_engine(self, tmp_path: Path) -> None:
        """无「派发」字段 → 缺省 engine。"""
        content = "# 任务卡 T90 · 缺省派发\n\n> 关联：PRJ-X · 状态：待分派\n"
        item = parse_card(_write(tmp_path, "T90.md", content))
        assert item.dispatch == "engine"

    def test_dispatch_manual(self, tmp_path: Path) -> None:
        """「派发：manual」→ manual。"""
        content = "# 任务卡 T89 · 手动派发\n\n> 关联：PRJ-X · 状态：待分派 · 派发：manual\n"
        item = parse_card(_write(tmp_path, "T89.md", content))
        assert item.dispatch == "manual"

    def test_dispatch_invalid_falls_back_engine(self, tmp_path: Path) -> None:
        """「派发」非法值 → 回落 engine。"""
        content = "# 任务卡 T88 · 非法派发\n\n> 关联：PRJ-X · 状态：待分派 · 派发：whatever\n"
        item = parse_card(_write(tmp_path, "T88.md", content))
        assert item.dispatch == "engine"


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
        # T54：T-mapping.md 是说明文档（无卡头标题），不得作为任务卡混入看板
        assert "T-mapping" not in ids
        for item in items:
            # 契约 §2 允许括号变体（如「打回（原因）」），断言按基础态归并
            assert base_state(item.state) in {"待分派", "执行中", "已回写", "已关闭", "打回", "未知"}


class TestSubdirScan:
    """T54 子目录扫描：根平铺旧卡 + <前缀>/ 子目录新卡共存；说明文档跳过。"""

    def test_scan_mixed_root_and_subdir(self, tmp_path: Path) -> None:
        """根目录旧卡 + 子目录新卡都被扫到。"""
        _write(tmp_path, "T99-old.md", SAMPLE)
        (tmp_path / "ccc").mkdir()
        new_card = (
            "# 任务卡 ccc100 · 子目录新卡\n"
            "> 关联：CCC · 执行体：X · 验收：Codex · 状态：待分派 · 日期：2026-08-04\n"
            "\n## 目标\n测试\n"
        )
        _write(tmp_path / "ccc", "ccc100-subdir.md", new_card)
        items = load_dispatch_cards(tmp_path)
        ids = {item.id for item in items}
        assert "T99" in ids
        assert "ccc100" in ids

    def test_scan_skips_non_card_doc(self, tmp_path: Path) -> None:
        """T-mapping.md 等说明文档（无 `# 任务卡` 卡头）不参与扫描。"""
        _write(tmp_path, "T-mapping.md", "# T 卡 → 前缀映射\n说明文档，无卡头标题\n")
        _write(tmp_path, "T1-ok.md", SAMPLE)
        items = load_dispatch_cards(tmp_path)
        assert {i.id for i in items} == {"T99"}

    def test_scan_one_level_subdir_only(self, tmp_path: Path) -> None:
        """只扫一层子目录；二层（ccc/sub/）不扫（T54 目录规则）。"""
        (tmp_path / "ccc" / "deep").mkdir(parents=True)
        deep_card = (
            "# 任务卡 ccc101 · 二层\n"
            "> 关联：CCC · 执行体：X · 状态：待分派 · 日期：2026-08-04\n"
        )
        _write(tmp_path / "ccc" / "deep", "ccc101-deep.md", deep_card)
        assert load_dispatch_cards(tmp_path) == []

    def test_scan_skips_invalid_utf8_binary_card(self, tmp_path: Path) -> None:
        """F02: 扫描时跳过非 UTF-8 编码的二进制文件，不抛错，其余卡正常返回。"""
        # 写一个正常任务卡
        _write(tmp_path, "T1-ok.md", SAMPLE)

        # 写一个包含非 UTF-8 字节的二进制文件（模拟损坏的非 UTF-8 卡）
        invalid_card = tmp_path / "T2-invalid.md"
        invalid_card.write_bytes(b"\x80\x81\xff\x00\x01\x02# \xcc\xdd\xee\xff")

        items = load_dispatch_cards(tmp_path)
        # 校验：仅有正常卡返回，非 UTF-8 损坏文件被安全跳过，不崩溃
        assert [i.id for i in items] == ["T99"]
