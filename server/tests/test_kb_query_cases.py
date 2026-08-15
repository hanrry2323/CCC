"""测试：知识库查询用例集（T51）。

从 ``knowledge/query-cases.md`` 解析查询用例表（≥10 题，覆盖四域），
经统一查询内核（server.kb.service）逐题验证：top-5 内命中预期域。

验收标准（任务卡 T51）：用例集 ≥10 题命中 ≥8。
实现按更强标准：全部用例命中预期域。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from server.kb import service

_CASES_FILE = Path(__file__).resolve().parents[2] / "knowledge" / "query-cases.md"
_MIN_HITS = 8  # 验收标准：≥8/≥10


def _load_cases() -> list[tuple[str, str]]:
    """解析 query-cases.md 表格，返回 [(查询, 预期域)]。"""
    text = _CASES_FILE.read_text(encoding="utf-8")
    cases: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\s*\|", line)
        if m:
            query = m.group(2).strip()
            domain = m.group(3).strip()
            if query and domain and query != "查询":
                cases.append((query, domain))
    return cases


def _all_cases() -> list[tuple[str, str]]:
    cases = _load_cases()
    assert len(cases) >= 10, f"用例集不足 10 题：{len(cases)}"
    return cases


# ════════════════════════════════════════════════════════════
# 逐题命中
# ════════════════════════════════════════════════════════════

@pytest.mark.parametrize("query,expected_domain", _all_cases(), ids=[q for q, _ in _load_cases()])
def test_query_hits_domain(query: str, expected_domain: str) -> None:
    """每题 top-5 内出现预期域文档。"""
    results = service.search(query, top_k=5)
    assert results, f"查询无结果: {query!r}"
    sections = {r["section"] for r in results}
    assert expected_domain in sections, (
        f"查询 {query!r} 未命中域 {expected_domain}；"
        f"top-5 域={sorted(sections)} 题号={[r['id'] for r in results[:5]]}"
    )


# ════════════════════════════════════════════════════════════
# 总量达标
# ════════════════════════════════════════════════════════════

def test_at_least_min_hits() -> None:
    """验收标准：≥10 题命中 ≥8。"""
    cases = _load_cases()
    hits = 0
    failures: list[str] = []
    for query, expected_domain in cases:
        results = service.search(query, top_k=5)
        if any(r["section"] == expected_domain for r in results):
            hits += 1
        else:
            failures.append(f"{query!r}→{expected_domain}")
    assert hits >= _MIN_HITS, f"命中 {hits}/{len(cases)} 低于 {_MIN_HITS}；失败: {failures}"
    assert hits >= len(cases) * 8 // 10


# ════════════════════════════════════════════════════════════
# 五域覆盖
# ════════════════════════════════════════════════════════════

def test_covers_five_domains() -> None:
    """用例集覆盖五域。"""
    domains = {d for _, d in _load_cases()}
    for expected in ("nodes-paths", "projects", "decisions", "lessons", "plans"):
        assert expected in domains, f"用例集缺域 {expected}"


def test_each_domain_at_least_three() -> None:
    """每域至少 3 题。"""
    from collections import Counter
    counts = Counter(d for _, d in _load_cases())
    for domain, count in counts.items():
        assert count >= 3, f"域 {domain} 仅 {count} 题"
