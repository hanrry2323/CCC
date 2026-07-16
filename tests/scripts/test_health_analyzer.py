"""Unit tests for ccc-health-analyzer."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "ccc_health_analyzer", SCRIPTS / "ccc-health-analyzer.py"
)
ccc_health_analyzer = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ccc_health_analyzer)

make_finding = ccc_health_analyzer.make_finding
_parse_vulture_output = ccc_health_analyzer._parse_vulture_output
_parse_radon_cc = ccc_health_analyzer._parse_radon_cc
_parse_radon_mi = ccc_health_analyzer._parse_radon_mi
_analyze_circular_deps = ccc_health_analyzer._analyze_circular_deps
_relative_path = ccc_health_analyzer._relative_path


def test_make_finding_defaults():
    """make_finding 返回标准结构，默认值正确"""
    f = make_finding("medium", "dead_code", "foo.py", 42, "test finding")
    assert f["severity"] == "medium"
    assert f["category"] == "dead_code"
    assert f["file"] == "foo.py"
    assert f["line"] == 42
    assert f["title"] == "test finding"
    assert f["description"] == "test finding"
    assert f["tool"] == "ast"
    assert f["confidence"] == "medium"


def test_make_finding_description():
    """description 可覆盖"""
    f = make_finding("high", "complexity", "bar.py", 10, "hi", "详细描述")
    assert f["description"] == "详细描述"


def test_make_finding_severity_validation():
    """不合法的 severity 应 assert"""
    with pytest.raises(AssertionError):
        make_finding("unknown", "dead_code", "x.py", 1, "x")


def test_parse_vulture_output():
    """解析 vulture 标准文本输出"""
    text = """foo.py:42: unused variable 'x' (60% confidence)
bar.py:10: unused function 'old_func' (80% confidence)
baz.py:5: unused import 'os' (70% confidence)"""
    findings = _parse_vulture_output(text, "/project")
    assert len(findings) == 3
    assert findings[0]["file"] == "foo.py"
    assert findings[0]["line"] == 42
    assert findings[0]["category"] == "dead_code"
    assert findings[0]["tool"] == "vulture"
    assert findings[0]["severity"] == "low"  # unused variable → low
    assert findings[1]["severity"] == "medium"  # unused function
    assert findings[1]["confidence"] == "high"  # 80%
    assert findings[2]["severity"] == "low"  # unused import → low


def test_parse_vulture_output_empty():
    """空字符串 → 空列表"""
    assert _parse_vulture_output("", "/p") == []
    assert _parse_vulture_output("   ", "/p") == []


def test_parse_radon_cc():
    """解析 radon cc -j 输出"""
    fake_json = json.dumps(
        {
            "/project/foo.py": [
                {
                    "name": "complex_func",
                    "type": "function",
                    "lineno": 42,
                    "complexity": 25,
                },
                {
                    "name": "simple_func",
                    "type": "function",
                    "lineno": 1,
                    "complexity": 3,
                },
            ]
        }
    )
    findings = _parse_radon_cc(fake_json, "/project")
    assert len(findings) == 1  # 只有 25 >= 20 (high threshold) → medium
    assert findings[0]["severity"] == "medium"
    assert findings[0]["title"].startswith("圈复杂度 25")
    assert findings[0]["confidence"] == "high"
    assert findings[0]["line"] == 42


def test_parse_radon_cc_very_high():
    """圈复杂度 >= 40 → high"""
    fake_json = json.dumps(
        {
            "/project/foo.py": [
                {"name": "monster", "type": "function", "lineno": 1, "complexity": 45},
            ]
        }
    )
    findings = _parse_radon_cc(fake_json, "/project")
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"


def test_parse_radon_cc_invalid_json():
    """非 JSON → 空列表"""
    assert _parse_radon_cc("not json", "/p") == []


def test_parse_radon_mi_float():
    """解析 radon mi -j 旧格式（裸 float）"""
    fake_json = json.dumps(
        {
            "/project/bad_module.py": 35.0,
            "/project/good_module.py": 75.0,
        }
    )
    findings = _parse_radon_mi(fake_json, "/project")
    assert len(findings) == 1  # 只有 35 < 50
    assert findings[0]["file"] == "bad_module.py"
    # 实现约定：MI < 50 一律 severity=low
    assert findings[0]["severity"] == "low"
    assert findings[0]["tool"] == "radon"


def test_parse_radon_mi_nested():
    """解析 radon 6.x 嵌套格式 {"mi": float, "rank": str}"""
    fake_json = json.dumps(
        {
            "/project/weak.py": {"mi": 22.5, "rank": "C"},
            "/project/ok.py": {"mi": 80.0, "rank": "A"},
        }
    )
    findings = _parse_radon_mi(fake_json, "/project")
    assert len(findings) == 1
    assert findings[0]["file"] == "weak.py"
    assert findings[0]["severity"] == "low"


def test_relative_path(tmp_path):
    """路径相对化"""
    base = tmp_path / "a"
    nested = base / "b"
    nested.mkdir(parents=True)
    f = nested / "c.py"
    f.write_text("#\n")
    assert _relative_path(str(f), str(base)) == "b/c.py"


def test_relative_path_no_prefix():
    """不在 prefix 下时返回原路径"""
    result = _relative_path("/x/y.py", "/a")
    assert result == "/x/y.py"


def test_analyze_circular_deps(tmp_path):
    """AST 检测 a↔b 循环依赖"""
    (tmp_path / "mod_a.py").write_text("import mod_b\n", encoding="utf-8")
    (tmp_path / "mod_b.py").write_text("import mod_a\n", encoding="utf-8")
    (tmp_path / "solo.py").write_text("x = 1\n", encoding="utf-8")

    findings = _analyze_circular_deps(str(tmp_path))
    assert len(findings) >= 1
    assert all(f["category"] == "circular_dependency" for f in findings)
    assert all(f["tool"] == "ast" for f in findings)
    titles = " ".join(f["title"] for f in findings)
    assert "mod_a" in titles and "mod_b" in titles


def test_analyze_circular_deps_self_import_ignored(tmp_path):
    """自引用不算循环依赖"""
    (tmp_path / "self_mod.py").write_text("import self_mod\n", encoding="utf-8")
    findings = _analyze_circular_deps(str(tmp_path))
    assert findings == []


def test_analyze_circular_deps_skips_venv(tmp_path):
    """跳过 .venv / __pycache__"""
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "pkg.py").write_text("import other\n", encoding="utf-8")
    (venv / "other.py").write_text("import pkg\n", encoding="utf-8")
    findings = _analyze_circular_deps(str(tmp_path))
    assert findings == []
