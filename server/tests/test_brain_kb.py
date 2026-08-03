"""test_brain_kb — 大脑知识库检索注入测试（T37）。

覆盖：
1. 命中注入：构造小索引 → 断言 prompt 含「【知识库参考】」与命中片段
2. 未命中降级：查询无命中 → 不注入，prompt 不含参考段落
3. 未配置降级：CCC_BRAIN_KB 未开启 → 不检索不注入
4. 检索异常降级：search 抛异常 → 不注入不报错
5. 非知识问题不注入：纯数学/闲聊类查询无 BM25 命中 → 不注入
6. 现有 brain 测试不回归：开关关闭时 _build_prompt 与原行为一致
"""

from __future__ import annotations

import pytest

from server.kb.indexer import KbDocument, save_index
from server.kb.search import reset_engine
from server.web.brain import _build_prompt, _retrieve_kb_context


# ── 夹具 ──

@pytest.fixture(autouse=True)
def _reset_kb_and_env(monkeypatch):
    """每个测试前重置 KB 全局引擎 + 清理 brain KB env，避免跨用例污染。"""
    reset_engine()
    for k in ("CCC_BRAIN_KB", "CCC_BRAIN_KB_TOP_K", "CCC_KB_INDEX_DIR"):
        monkeypatch.delenv(k, raising=False)
    yield
    reset_engine()


@pytest.fixture
def small_index(tmp_path) -> str:
    """构造小索引目录（含 nodes-paths / projects / decisions / lessons 各一条）。"""
    docs = [
        KbDocument(
            "nodes-paths::m1",
            "nodes-paths",
            "M1 开发机 IP 192.168.3.140 macOS 运行 CCC 服务",
            "test/01-nodes-paths.json",
        ),
        KbDocument(
            "nodes-paths::mac2017",
            "nodes-paths",
            "Mac2017 重活节点 IP 192.168.3.116 16GB 运行 qb 7788",
            "test/01-nodes-paths.json",
        ),
        KbDocument(
            "projects::ccc",
            "projects",
            "CCC 项目 主仓 路径 /Users/apple/program/CCC/ 自动化平台底座",
            "test/02-project-metadata.json",
        ),
        KbDocument(
            "decisions::D1",
            "decisions",
            "CCC 重构方案 薄驱动 Engine 文档流转 看板 HTTP 服务",
            "test/03-key-decisions.json",
        ),
        KbDocument(
            "lessons::L1",
            "lessons",
            "Plan 必须用自然语言 不能写具体命令 避免 agent 被当成 shell 执行器",
            "test/04-lessons.json",
        ),
    ]
    index_dir = tmp_path / "index"
    save_index(docs, index_dir)
    return str(index_dir)


def _enable_kb(monkeypatch, index_dir: str) -> None:
    """开启 KB 检索并指向给定索引目录。"""
    monkeypatch.setenv("CCC_BRAIN_KB", "1")
    monkeypatch.setenv("CCC_KB_INDEX_DIR", index_dir)
    reset_engine()


# ════════════════════════════════════════════════════════════
# 1. 命中注入
# ════════════════════════════════════════════════════════════

class TestHitInjection:
    """命中注入：检索命中时 prompt 含知识库参考段落。"""

    def test_kb_context_returns_reference_block(self, small_index, monkeypatch):
        """_retrieve_kb_context 命中时返回「【知识库参考】」段落。"""
        _enable_kb(monkeypatch, small_index)
        ctx = _retrieve_kb_context("M1 开发机 IP")
        assert ctx.startswith("【知识库参考】")
        assert "nodes-paths" in ctx
        # 命中片段应包含索引中的关键词
        assert "192.168.3.140" in ctx or "M1" in ctx

    def test_prompt_contains_kb_reference_on_hit(self, small_index, monkeypatch):
        """_build_prompt 在命中时注入参考段落（置于系统人格与历史之间）。"""
        _enable_kb(monkeypatch, small_index)
        prompt = _build_prompt("M1 开发机 IP", [])
        assert "【知识库参考】" in prompt
        assert "nodes-paths" in prompt
        # 参考段落应位于系统人格之后、当前问题之前
        sys_pos = prompt.index("大脑 Agent")
        kb_pos = prompt.index("【知识库参考】")
        q_pos = prompt.index("【当前问题】")
        assert sys_pos < kb_pos < q_pos

    def test_prompt_contains_section_title_snippet(self, small_index, monkeypatch):
        """注入格式为「域：标题：片段」。"""
        _enable_kb(monkeypatch, small_index)
        prompt = _build_prompt("CCC 项目 主仓 路径", [])
        assert "projects" in prompt
        # 标题取 doc_id 中 :: 之后的部分
        assert "ccc" in prompt.lower()
        assert "/Users/apple/program/CCC/" in prompt

    def test_top_k_limit(self, small_index, monkeypatch):
        """CCC_BRAIN_KB_TOP_K 限制返回条数。"""
        _enable_kb(monkeypatch, small_index)
        monkeypatch.setenv("CCC_BRAIN_KB_TOP_K", "1")
        reset_engine()
        ctx = _retrieve_kb_context("M1 Mac2017 CCC")
        # 参考段落 = 1 行标题 + top_k 条目
        body_lines = [line for line in ctx.splitlines() if line and not line.startswith("【")]
        assert len(body_lines) <= 1


# ════════════════════════════════════════════════════════════
# 2. 未命中降级
# ════════════════════════════════════════════════════════════

class TestNoHitDegrade:
    """未命中降级：查询有 token 但无匹配 → 不注入。"""

    def test_no_hit_no_injection(self, small_index, monkeypatch):
        """查询无命中时 _retrieve_kb_context 返回空串。"""
        _enable_kb(monkeypatch, small_index)
        ctx = _retrieve_kb_context("ZZZZNOTEXIST")
        assert ctx == ""

    def test_no_hit_prompt_has_no_kb_block(self, small_index, monkeypatch):
        """未命中时 prompt 不含「【知识库参考】」。"""
        _enable_kb(monkeypatch, small_index)
        prompt = _build_prompt("ZZZZNOTEXIST", [])
        assert "【知识库参考】" not in prompt


# ════════════════════════════════════════════════════════════
# 3. 未配置降级
# ════════════════════════════════════════════════════════════

class TestNotConfiguredDegrade:
    """未配置降级：CCC_BRAIN_KB 未开启 → 不检索不注入。"""

    def test_disabled_no_retrieval(self, small_index, monkeypatch):
        """开关关闭时 _retrieve_kb_context 返回空串。"""
        # 不设置 CCC_BRAIN_KB（默认关闭）
        ctx = _retrieve_kb_context("M1 开发机 IP")
        assert ctx == ""

    def test_disabled_prompt_no_kb_block(self, small_index, monkeypatch):
        """开关关闭时 prompt 不含参考段落。"""
        prompt = _build_prompt("M1 开发机 IP", [])
        assert "【知识库参考】" not in prompt
        # 系统人格 + 当前问题仍在
        assert "大脑 Agent" in prompt
        assert "M1 开发机 IP" in prompt

    def test_explicit_disable(self, small_index, monkeypatch):
        """CCC_BRAIN_KB=0 显式关闭 → 不注入。"""
        monkeypatch.setenv("CCC_BRAIN_KB", "0")
        monkeypatch.setenv("CCC_KB_INDEX_DIR", small_index)
        ctx = _retrieve_kb_context("M1 开发机 IP")
        assert ctx == ""


# ════════════════════════════════════════════════════════════
# 4. 检索异常降级
# ════════════════════════════════════════════════════════════

class TestRetrievalExceptionDegrade:
    """检索异常降级：search 抛异常 → 不注入不报错。"""

    def test_search_exception_no_injection(self, monkeypatch):
        """search 抛异常时 _retrieve_kb_context 静默返回空串。"""
        monkeypatch.setenv("CCC_BRAIN_KB", "1")

        import server.kb.search as kb_mod

        def _boom(*args, **kwargs):
            raise RuntimeError("kb exploded")

        monkeypatch.setattr(kb_mod, "search", _boom)
        ctx = _retrieve_kb_context("anything")
        assert ctx == ""

    def test_search_exception_prompt_intact(self, monkeypatch):
        """检索异常时 prompt 仍含系统人格与当前问题（不报错中断）。"""
        monkeypatch.setenv("CCC_BRAIN_KB", "1")

        import server.kb.search as kb_mod

        def _raise(*args, **kwargs):
            raise OSError("io failure")

        monkeypatch.setattr(kb_mod, "search", _raise)

        prompt = _build_prompt("hello", [])
        assert "大脑 Agent" in prompt
        assert "hello" in prompt
        assert "【知识库参考】" not in prompt


# ════════════════════════════════════════════════════════════
# 5. 非知识问题不注入
# ════════════════════════════════════════════════════════════

class TestNonKnowledgeNoInjection:
    """非知识问题不注入：纯数学/闲聊类查询无 BM25 命中 → 不注入。

    BM25 分词只取中文字符与英文单词（不含数字），「1+1=?」无 token → 无命中。
    """

    def test_math_question_no_injection(self, small_index, monkeypatch):
        """纯数学题（无中英 token）不触发注入。"""
        _enable_kb(monkeypatch, small_index)
        ctx = _retrieve_kb_context("1+1=?")
        assert ctx == ""

    def test_math_question_prompt_no_kb_block(self, small_index, monkeypatch):
        """纯数学题 prompt 不含参考段落。"""
        _enable_kb(monkeypatch, small_index)
        prompt = _build_prompt("1+1=?", [])
        assert "【知识库参考】" not in prompt
        assert "1+1=?" in prompt


# ════════════════════════════════════════════════════════════
# 6. 现有 brain 测试不回归（开关关闭时行为不变）
# ════════════════════════════════════════════════════════════

class TestNoRegressionWhenDisabled:
    """开关关闭时 _build_prompt 与 T29 原行为一致（系统人格 + 历史 + 当前问题）。"""

    def test_prompt_structure_unchanged(self, small_index):
        """开关关闭时 prompt 结构 = 系统人格 + 历史对话 + 当前问题。"""
        history = [
            {"role": "user", "message": "前面问的"},
            {"role": "assistant", "message": "前面答的"},
        ]
        prompt = _build_prompt("当前问题", history)
        assert "大脑 Agent" in prompt
        assert "【历史对话】" in prompt
        assert "前面问的" in prompt
        assert "前面答的" in prompt
        assert "当前问题" in prompt
        # 不应出现参考段落
        assert "【知识库参考】" not in prompt

    def test_empty_history_prompt(self, small_index):
        """空历史时 prompt 仍正常（无历史段落）。"""
        prompt = _build_prompt("单问", [])
        assert "大脑 Agent" in prompt
        assert "单问" in prompt
        assert "【历史对话】" not in prompt
        assert "【知识库参考】" not in prompt
