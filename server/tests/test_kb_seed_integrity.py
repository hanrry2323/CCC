"""测试：知识库种子包完整性 + 检索命中 + 敏感字段扫描（T36 M4 刷新）。

覆盖：
1. 种子包 schema 完整性（四类 JSON 都有 schema/section/updated_at/source/note）
2. updated_at = 2026-08-03（M4 刷新标记）
3. 新增决策 ≥6 条、新增教训 ≥4 条
4. 索引重建后 5 个查询词各命中对应域
5. 无敏感字段（密钥/密码/token 模式扫描零命中）
6. 已退役端口在现行文档零残留（仅在 retired_ports_authoritative 等显式清单中允许）
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from server.kb.indexer import reindex
from server.kb.search import reset_engine, search


# ── 路径夹具 ──

def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def knowledge_root() -> Path:
    return _project_root() / "knowledge"


@pytest.fixture
def seed_dir(knowledge_root: Path) -> Path:
    return knowledge_root / "seed"


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    return tmp_path / ".index"


@pytest.fixture(scope="module")
def rebuilt_index(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """模块级索引重建：用临时目录生成索引，全模块共享。"""
    idx = tmp_path_factory.mktemp("kb_index") / ".index"
    root = _project_root() / "knowledge"
    reindex(root, idx)
    reset_engine()
    return idx


# ════════════════════════════════════════════════════════════
# 1. 种子包 schema 完整性
# ════════════════════════════════════════════════════════════

class TestSeedSchema:
    """四类种子 JSON 的 schema 字段完整。"""

    REQUIRED_KEYS = {"schema", "section", "updated_at", "source", "note"}

    @pytest.mark.parametrize("filename", [
        "01-nodes-paths.json",
        "02-project-metadata.json",
        "03-key-decisions.json",
        "04-lessons.json",
    ])
    def test_seed_has_required_keys(self, seed_dir: Path, filename: str) -> None:
        filepath = seed_dir / filename
        assert filepath.is_file(), f"种子文件缺失：{filename}"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        missing = self.REQUIRED_KEYS - set(data.keys())
        assert not missing, f"{filename} 缺字段：{missing}"

    @pytest.mark.parametrize("filename", [
        "01-nodes-paths.json",
        "02-project-metadata.json",
        "03-key-decisions.json",
        "04-lessons.json",
    ])
    def test_seed_updated_at_m4_refresh(self, seed_dir: Path, filename: str) -> None:
        """M4 刷新标记：updated_at = 2026-08-03。"""
        filepath = seed_dir / filename
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["updated_at"] == "2026-08-03", (
            f"{filename} updated_at={data['updated_at']}（应为 2026-08-03 M4 刷新）"
        )

    @pytest.mark.parametrize("filename", [
        "01-nodes-paths.json",
        "02-project-metadata.json",
        "03-key-decisions.json",
        "04-lessons.json",
    ])
    def test_seed_schema_value(self, seed_dir: Path, filename: str) -> None:
        filepath = seed_dir / filename
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["schema"] == "ccc-kb-seed-v1", (
            f"{filename} schema={data['schema']}（应为 ccc-kb-seed-v1）"
        )


# ════════════════════════════════════════════════════════════
# 2. 新增决策 ≥6 条、新增教训 ≥4 条
# ════════════════════════════════════════════════════════════

class TestNewEntries:
    """M4 刷新新增条目数量达标。"""

    EXPECTED_NEW_DECISIONS = {
        "D1-D10",                       # 重构方案 v2（v2 升级）
        "D11-Relay-Dual-Track",         # 中转站双轨决议
        "Closeout-Reeval-2026-08-03",   # 收口重评
        "T31-T35-Closeout-Done",        # T31–T35 收口完成
        "M2-Production-Verified",       # M2 生产验证通过
        "D10-Hardcode-Discipline",      # D10 硬编码纪律细则
    }

    EXPECTED_NEW_LESSONS = {"LC1", "LC2", "LC3", "LC4"}

    def test_decisions_count_ge_6(self, seed_dir: Path) -> None:
        filepath = seed_dir / "03-key-decisions.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        decisions = data.get("decisions", [])
        ids = {d.get("id") for d in decisions}
        missing = self.EXPECTED_NEW_DECISIONS - ids
        assert not missing, f"决策缺条目：{missing}（应有 ≥6 条新增）"

    def test_lessons_count_ge_4(self, seed_dir: Path) -> None:
        filepath = seed_dir / "04-lessons.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        closeout_lessons = data.get("ccc_closeout_lessons_2026_08", [])
        ids = {lc.get("id") for lc in closeout_lessons}
        missing = self.EXPECTED_NEW_LESSONS - ids
        assert not missing, f"教训缺条目：{missing}（应有 ≥4 条新增 LC1-LC4）"


# ════════════════════════════════════════════════════════════
# 3. 索引重建后 5 个查询词各命中对应域
# ════════════════════════════════════════════════════════════

class TestRetrievalHits:
    """M4 刷新后 5 个查询词实测命中对应域文档。"""

    QUERIES = [
        ("2017 单端", None, "nodes-paths"),       # 节点/路径域
        ("中转站 双轨", None, "decisions"),        # 决策域（D11）
        ("CCC 重构方案 v2", None, "decisions"),    # 决策域（D1-D10）
        ("文档口径分裂", None, "lessons"),         # 教训域（LC1）
        ("QuantHive 独立轨道", None, "projects"),  # 项目域
    ]

    @pytest.mark.parametrize("query,domain,expected_section", QUERIES)
    def test_query_hits_expected_domain(
        self, rebuilt_index: Path, query: str, domain: str | None, expected_section: str
    ) -> None:
        reset_engine()
        results = search(query, domain=domain, index_dir=str(rebuilt_index), top_k=5)
        assert len(results) > 0, f"查询 {query!r} 无结果（应命中 {expected_section}）"
        sections = {r["section"] for r in results}
        # 期望至少一个命中 section 与 expected_section 相关
        # 注意：seed JSON 的 section 形如 "01-nodes-paths"，domains MD 的 section 形如 "nodes-paths"
        matched = any(
            expected_section in s or s in expected_section
            for s in sections
        )
        assert matched, (
            f"查询 {query!r} 命中 sections={sections}，未含 {expected_section}"
        )


# ════════════════════════════════════════════════════════════
# 4. 无敏感字段（密钥/密码/token 模式扫描零命中）
# ════════════════════════════════════════════════════════════

class TestNoSensitiveFields:
    """种子包不含密钥/密码/token 等敏感信息。"""

    # 敏感模式：sk- 开头的 API key、ghp_ 开头的 GitHub token、password=xxx 等
    SENSITIVE_PATTERNS = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),       # OpenAI/Anthropic API key
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),       # GitHub personal access token
        re.compile(r"gho_[a-zA-Z0-9]{36}"),       # GitHub OAuth token
        re.compile(r"password\s*[:=]\s*\S{6,}", re.IGNORECASE),  # password=xxx
        re.compile(r"api[_-]?key\s*[:=]\s*[a-zA-Z0-9]{20,}", re.IGNORECASE),
        re.compile(r"secret\s*[:=]\s*[a-zA-Z0-9]{20,}", re.IGNORECASE),
        re.compile(r"token\s*[:=]\s*[a-zA-Z0-9]{20,}", re.IGNORECASE),
    ]

    @pytest.mark.parametrize("filename", [
        "01-nodes-paths.json",
        "02-project-metadata.json",
        "03-key-decisions.json",
        "04-lessons.json",
    ])
    def test_no_sensitive_in_seed_json(self, seed_dir: Path, filename: str) -> None:
        filepath = seed_dir / filename
        content = filepath.read_text(encoding="utf-8")
        for pattern in self.SENSITIVE_PATTERNS:
            matches = pattern.findall(content)
            assert not matches, (
                f"{filename} 含敏感字段（pattern={pattern.pattern}）：{matches[:3]}"
            )

    @pytest.mark.parametrize("domain_dir", [
        "nodes-paths",
        "projects",
        "decisions",
        "lessons",
    ])
    def test_no_sensitive_in_domains_md(
        self, knowledge_root: Path, domain_dir: str
    ) -> None:
        filepath = knowledge_root / "domains" / domain_dir / "seed.md"
        assert filepath.is_file(), f"域文件缺失：{filepath}"
        content = filepath.read_text(encoding="utf-8")
        for pattern in self.SENSITIVE_PATTERNS:
            matches = pattern.findall(content)
            assert not matches, (
                f"{filepath.name} 含敏感字段（pattern={pattern.pattern}）：{matches[:3]}"
            )


# ════════════════════════════════════════════════════════════
# 5. 已退役端口在现行文档零残留
# ════════════════════════════════════════════════════════════

class TestNoRetiredPortResidue:
    """现行知识库文档中不得出现已退役端口作为「现行服务」的表述。

    例外：retired_ports_authoritative / retired_services / 已退役端口 等显式归档清单
    可列出退役端口（必须标注「已退役/T34 归档」等）。
    """

    # 已退役端口（来自 01-nodes-paths.json retired_ports_authoritative）
    RETIRED_PORTS = ["17777", "7775", "7778", "11434"]

    # 允许出现退役端口的上下文（必须含这些关键词之一才算合法）
    ALLOWED_CONTEXTS = [
        "已退役", "retired", "T31", "T34", "归档", "移除", "离线",
        "retired_ports_authoritative", "retired_services", "已退役端口",
        "17777 —", "7775 —", "7778 —", "11434 —",
        "17777（", "7775（", "7778（", "11434（",
    ]

    @pytest.mark.parametrize("filename", [
        "02-project-metadata.json",
        "03-key-decisions.json",
        "04-lessons.json",
    ])
    def test_no_retired_port_in_non_nodes_seed(
        self, seed_dir: Path, filename: str
    ) -> None:
        """非 nodes-paths 种子不得出现退役端口（除 7777/4000 这种仍可能在历史上下文出现的）。"""
        filepath = seed_dir / filename
        content = filepath.read_text(encoding="utf-8")
        # 17777/7775/7778/11434 是确定退役的，不允许出现
        for port in ["17777", "7775", "7778", "11434"]:
            assert port not in content, (
                f"{filename} 含退役端口 {port}（非 nodes-paths 域不应出现）"
            )

    @pytest.mark.parametrize("domain_dir", [
        "projects",
        "decisions",
        "lessons",
    ])
    def test_no_retired_port_in_non_nodes_domains(
        self, knowledge_root: Path, domain_dir: str
    ) -> None:
        """非 nodes-paths 域 MD 不得出现退役端口。"""
        filepath = knowledge_root / "domains" / domain_dir / "seed.md"
        content = filepath.read_text(encoding="utf-8")
        for port in ["17777", "7775", "7778", "11434"]:
            assert port not in content, (
                f"{domain_dir}/seed.md 含退役端口 {port}"
            )

    def test_retired_ports_in_nodes_paths_have_context(
        self, knowledge_root: Path
    ) -> None:
        """nodes-paths 中出现的退役端口必须在归档清单上下文里。"""
        # 检查 seed JSON 的 retired_ports_authoritative 字段存在
        seed_file = knowledge_root / "seed" / "01-nodes-paths.json"
        data = json.loads(seed_file.read_text(encoding="utf-8"))
        retired_list = data.get("retired_ports_authoritative", [])
        assert len(retired_list) >= 5, (
            f"retired_ports_authoritative 应至少 5 条，实际 {len(retired_list)}"
        )
        # 每条都应含「已退役」或「归档」字样
        for entry in retired_list:
            assert "已退役" in entry or "归档" in entry or "离线" in entry or "移除" in entry, (
                f"退役端口条目缺归档标注：{entry}"
            )
