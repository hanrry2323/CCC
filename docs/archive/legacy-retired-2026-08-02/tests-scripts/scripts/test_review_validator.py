"""test_review_validator.py — _review_validator 模块单元测试 (v0.51.0 P1-10)

覆盖:
  - validate_review_json: 文件不存在 / JSON 损坏 / 顶层非 dict / 缺字段 /
    非法 source / 非法 generated_at / findings 非数组 / finding 缺字段 /
    非法 severity / 非法 category / summary 缺字段 / total 不一致 / 正常 valid
  - scan_review_dir: 目录不存在返回 [] / 多 JSON 批量扫描带 file 字段

业务关键性：engine 空闲时自动扫 review 报告，是审查质量门禁；误报/漏报都会污染审查流程。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _review_validator import (  # noqa: E402
    FINDING_REQUIRED,
    REQUIRED_FIELDS,
    SUMMARY_REQUIRED,
    scan_review_dir,
    validate_review_json,
)


def _valid_report() -> dict:
    """返回一份符合规范的合法报告模板（被各测试拷贝后微调）。"""
    return {
        "schema_version": "1.0",
        "generated_at": "2026-07-19T08:00:00+08:00",
        "project": "demo",
        "source": "daily-scan",
        "findings": [
            {
                "id": "F-001",
                "severity": "high",
                "category": "security",
                "title": "SQL injection",
                "description": "User input concatenated into SQL",
            }
        ],
        "summary": {
            "total": 1,
            "critical": 0,
            "high": 1,
            "medium": 0,
            "low": 0,
            "info": 0,
            "auto_fixable": 0,
        },
    }


def _write_report(tmp_path: Path, name: str, data: dict) -> Path:
    """写到 {tmp_path}/.ccc/reviews/{name}，返回完整路径。"""
    reviews_dir = tmp_path / ".ccc" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    p = reviews_dir / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ──────────────────────────────────────────────────────────────────
# validate_review_json — 文件层面
# ──────────────────────────────────────────────────────────────────


def test_validate_missing_file(tmp_path: Path):
    result = validate_review_json(str(tmp_path / "no_such.json"))
    assert result["valid"] is False
    assert any("文件不存在" in e for e in result["errors"])


def test_validate_corrupted_json(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not a json {{{", encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("JSON 解析错误" in e for e in result["errors"])


def test_validate_top_level_not_dict(tmp_path: Path):
    p = tmp_path / "arr.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("顶层结构必须是 dict" in e for e in result["errors"])


# ──────────────────────────────────────────────────────────────────
# validate_review_json — 字段层面
# ──────────────────────────────────────────────────────────────────


def test_validate_missing_top_level_fields(tmp_path: Path):
    """逐个缺顶层字段都应被检测到。"""
    for field in REQUIRED_FIELDS:
        data = _valid_report()
        del data[field]
        p = tmp_path / f"missing_{field}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = validate_review_json(str(p))
        assert result["valid"] is False, f"missing {field} should fail"
        assert any(f"缺顶层字段: {field}" in e for e in result["errors"]), (
            f"missing {field} not reported"
        )


def test_validate_invalid_source(tmp_path: Path):
    data = _valid_report()
    data["source"] = "totally-invalid-source"
    p = tmp_path / "bad_source.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("source 必须是" in e for e in result["errors"])


@pytest.mark.parametrize(
    "source", ["daily-scan", "adversarial", "doc-quality"]
)
def test_validate_all_valid_sources(source: str, tmp_path: Path):
    data = _valid_report()
    data["source"] = source
    p = tmp_path / f"src_{source}.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    assert validate_review_json(str(p))["valid"] is True


def test_validate_invalid_generated_at(tmp_path: Path):
    data = _valid_report()
    data["generated_at"] = "not-a-date"
    p = tmp_path / "bad_ts.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("generated_at 不是合法 ISO8601" in e for e in result["errors"])


def test_validate_findings_not_list(tmp_path: Path):
    data = _valid_report()
    data["findings"] = "not a list"
    p = tmp_path / "bad_findings.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("findings 必须是数组" in e for e in result["errors"])


def test_validate_finding_missing_field(tmp_path: Path):
    """逐个缺 finding 必填字段都应被检测到。"""
    for field in FINDING_REQUIRED:
        data = _valid_report()
        del data["findings"][0][field]
        p = tmp_path / f"missing_finding_{field}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = validate_review_json(str(p))
        assert result["valid"] is False, f"missing finding.{field} should fail"


def test_validate_invalid_severity(tmp_path: Path):
    data = _valid_report()
    data["findings"][0]["severity"] = "blocker"  # 不在 VALID_SEVERITIES 中
    p = tmp_path / "bad_sev.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("severity" in e and "不合法" in e for e in result["errors"])


def test_validate_invalid_category(tmp_path: Path):
    data = _valid_report()
    data["findings"][0]["category"] = "ui"  # 不在 VALID_CATEGORIES 中
    p = tmp_path / "bad_cat.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("category" in e and "不合法" in e for e in result["errors"])


# ──────────────────────────────────────────────────────────────────
# validate_review_json — summary 校验
# ──────────────────────────────────────────────────────────────────


def test_validate_summary_missing_field(tmp_path: Path):
    for field in SUMMARY_REQUIRED:
        data = _valid_report()
        del data["summary"][field]
        p = tmp_path / f"missing_summary_{field}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = validate_review_json(str(p))
        assert result["valid"] is False, f"missing summary.{field} should fail"


def test_validate_summary_total_mismatch(tmp_path: Path):
    data = _valid_report()
    data["summary"]["total"] = 999  # 与 len(findings)=1 不匹配
    p = tmp_path / "mismatch.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("summary.total" in e and "!=" in e for e in result["errors"])


def test_validate_summary_not_dict(tmp_path: Path):
    data = _valid_report()
    data["summary"] = "not a dict"
    p = tmp_path / "bad_summary.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is False
    assert any("summary 必须是 dict" in e for e in result["errors"])


# ──────────────────────────────────────────────────────────────────
# validate_review_json — 完整合法用例
# ──────────────────────────────────────────────────────────────────


def test_validate_valid_report(tmp_path: Path):
    p = _write_report(tmp_path, "valid.json", _valid_report())
    result = validate_review_json(str(p))
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_empty_findings_with_zero_total(tmp_path: Path):
    """空 findings + total=0 应通过。"""
    data = _valid_report()
    data["findings"] = []
    data["summary"]["total"] = 0
    data["summary"]["high"] = 0
    p = tmp_path / "empty_findings.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    result = validate_review_json(str(p))
    assert result["valid"] is True


def test_validate_multi_findings(tmp_path: Path):
    """多 findings 应正常通过。"""
    data = _valid_report()
    data["findings"] = [
        {
            "id": f"F-{i:03d}",
            "severity": sev,
            "category": cat,
            "title": f"finding {i}",
            "description": f"desc {i}",
        }
        for i, (sev, cat) in enumerate(
            [
                ("critical", "security"),
                ("high", "config"),
                ("medium", "code-quality"),
                ("low", "documentation"),
                ("info", "ops"),
            ]
        )
    ]
    data["summary"]["total"] = 5
    data["summary"]["critical"] = 1
    data["summary"]["high"] = 1
    data["summary"]["medium"] = 1
    data["summary"]["low"] = 1
    data["summary"]["info"] = 1
    p = tmp_path / "multi.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    assert validate_review_json(str(p))["valid"] is True


# ──────────────────────────────────────────────────────────────────
# scan_review_dir
# ──────────────────────────────────────────────────────────────────


def test_scan_review_dir_missing_dir_returns_empty(tmp_path: Path):
    """reviews 目录不存在时应返回空列表。"""
    assert scan_review_dir(str(tmp_path)) == []


def test_scan_review_dir_returns_results_with_file_field(tmp_path: Path):
    """扫描多个 JSON，每条结果应带 file 字段。"""
    _write_report(tmp_path, "valid1.json", _valid_report())

    bad = _valid_report()
    del bad["source"]
    _write_report(tmp_path, "invalid.json", bad)

    results = scan_review_dir(str(tmp_path))
    assert len(results) == 2
    # 每条都应有 file 字段
    assert all("file" in r for r in results)
    # 应有一条 valid 一条 invalid
    valid_results = [r for r in results if r["valid"]]
    invalid_results = [r for r in results if not r["valid"]]
    assert len(valid_results) == 1
    assert len(invalid_results) == 1
    assert "invalid.json" in invalid_results[0]["file"]


def test_scan_review_dir_returns_sorted(tmp_path: Path):
    """scan_review_dir 按 glob 排序，结果顺序应稳定。"""
    for name in ["c.json", "a.json", "b.json"]:
        _write_report(tmp_path, name, _valid_report())

    results = scan_review_dir(str(tmp_path))
    files = [Path(r["file"]).name for r in results]
    assert files == sorted(files)
    assert files == ["a.json", "b.json", "c.json"]
