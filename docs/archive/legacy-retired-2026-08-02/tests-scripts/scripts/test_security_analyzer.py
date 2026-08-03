"""Unit tests for ccc-security-analyzer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "ccc_security_analyzer", SCRIPTS / "ccc-security-analyzer.py"
)
ccc_security_analyzer = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ccc_security_analyzer)

make_finding = ccc_security_analyzer.make_finding
_parse_bandit_json = ccc_security_analyzer._parse_bandit_json
_parse_pip_audit_json = ccc_security_analyzer._parse_pip_audit_json


def test_make_finding():
    f = make_finding("high", "security", "app.py", 15, "Hardcoded password")
    assert f["severity"] == "high"
    assert f["category"] == "security"
    assert f["file"] == "app.py"
    assert f["line"] == 15
    assert f["title"] == "Hardcoded password"
    # 默认 tool 是 bandit（与实现一致）
    assert f["tool"] == "bandit"
    assert f["confidence"] == "medium"


def test_make_finding_severity_validation():
    with pytest.raises(AssertionError):
        make_finding("bogus", "security", "x.py", 1, "x")


def test_parse_bandit_json(tmp_path):
    """解析 bandit -f json 输出"""
    app = tmp_path / "app.py"
    app.write_text("x=1\n")
    fake_data = {
        "results": [
            {
                "issue_severity": "HIGH",
                "issue_confidence": "MEDIUM",
                "filename": str(app),
                "line_number": 42,
                "issue_text": "Use of insecure MD5 hash",
                "test_id": "B324",
                "code": "md5()",
            }
        ]
    }
    findings = _parse_bandit_json(fake_data, str(tmp_path))
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["confidence"] == "medium"
    assert findings[0]["file"] == "app.py"
    assert findings[0]["line"] == 42
    assert findings[0]["tool"] == "bandit"
    assert findings[0]["category"] == "security"
    assert "B324" in findings[0]["description"]


def test_parse_bandit_json_empty():
    assert _parse_bandit_json({"results": []}, "/p") == []


def test_parse_bandit_json_no_results():
    assert _parse_bandit_json({}, "/p") == []


def test_parse_pip_audit_json_dict():
    data = {
        "dependencies": [
            {
                "name": "requests",
                "version": "2.0.0",
                "vulns": [
                    {
                        "id": "PYSEC-1",
                        "aliases": ["CVE-2023-0001"],
                        "description": "demo vuln",
                        "severity": "HIGH",
                    }
                ],
            }
        ]
    }
    findings = _parse_pip_audit_json(data)
    assert len(findings) == 1
    assert findings[0]["category"] == "cve"
    assert findings[0]["tool"] == "pip-audit"
    assert findings[0]["severity"] == "high"
    assert "CVE-2023-0001" in findings[0]["title"]


def test_parse_pip_audit_json_list():
    data = [
        {
            "name": "urllib3",
            "version": "1.0",
            "vulns": [
                {
                    "id": "GHSA-x",
                    "aliases": [],
                    "description": "issue",
                    "severity": "MEDIUM",
                }
            ],
        }
    ]
    findings = _parse_pip_audit_json(data)
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
