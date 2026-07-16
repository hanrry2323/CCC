"""Unit tests for _evolve.py (自动进化引擎)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from _evolve import (
    _deduplicate,
    _filter_noise,
    _fingerprint,
    _load_fingerprints,
    _post_finding,
    _save_fingerprint,
    _score_finding,
    evolve_run,
)


def test_fingerprint():
    f = {
        "file": "src/main.py",
        "line": 42,
        "category": "dead_code",
        "tool": "vulture",
    }
    fp = _fingerprint(f)
    assert fp == "src/main.py:42:dead_code:vulture"


def test_fingerprint_no_line():
    f = {
        "file": "src/main.py",
        "line": None,
        "category": "complexity",
        "tool": "radon",
    }
    fp = _fingerprint(f)
    assert fp == "src/main.py:?:complexity:radon"


def test_fingerprint_missing_line_key():
    f = {"file": "a.py", "category": "cve", "tool": "pip-audit"}
    assert _fingerprint(f) == "a.py:?:cve:pip-audit"


def test_score_finding():
    """higher severity + higher confidence + important category → higher score"""
    crit = {"severity": "critical", "confidence": "high", "category": "cve"}
    low = {"severity": "low", "confidence": "low", "category": "complexity"}
    assert _score_finding(crit) > _score_finding(low)


def test_score_finding_category_bonus():
    """同 severity/confidence 时 cve 分高于 complexity"""
    a = {"severity": "medium", "confidence": "medium", "category": "cve"}
    b = {"severity": "medium", "confidence": "medium", "category": "complexity"}
    assert _score_finding(a) > _score_finding(b)


def test_filter_noise():
    """B101 assert 在 test 文件中被过滤"""
    findings = [
        {
            "file": "tests/test_app.py",
            "description": "[B101] assert used",
            "tool": "bandit",
            "severity": "medium",
            "confidence": "high",
            "category": "security",
            "line": 1,
            "title": "assert",
        },
        {
            "file": "src/app.py",
            "description": "hardcoded password",
            "tool": "bandit",
            "severity": "high",
            "confidence": "high",
            "category": "security",
            "line": 10,
            "title": "pwd",
        },
    ]
    filtered = _filter_noise(findings)
    assert len(filtered) == 1
    assert filtered[0]["file"] == "src/app.py"


def test_filter_noise_downgrades_other_test_security():
    """tests/ 下非 B101 的 security 发现降一级，不完全过滤"""
    findings = [
        {
            "file": "tests/test_x.py",
            "description": "[B108] temp dir",
            "tool": "bandit",
            "severity": "medium",
            "confidence": "high",
            "category": "security",
            "line": 3,
            "title": "temp",
        }
    ]
    filtered = _filter_noise(findings)
    assert len(filtered) == 1
    assert filtered[0]["severity"] == "low"


def test_filter_noise_empty():
    assert _filter_noise([]) == []


def test_deduplicate():
    """同 fingerprint 只保留一条（分数更高者）"""
    findings = [
        {
            "file": "a.py",
            "line": 1,
            "category": "dead_code",
            "tool": "vulture",
            "title": "first",
            "severity": "low",
            "confidence": "medium",
            "description": "",
        },
        {
            "file": "a.py",
            "line": 1,
            "category": "dead_code",
            "tool": "vulture",
            "title": "second",
            "severity": "high",
            "confidence": "high",
            "description": "",
        },
    ]
    deduped = _deduplicate(findings)
    assert len(deduped) == 1
    assert deduped[0]["title"] == "second"  # 更高分


def test_deduplicate_no_dupes():
    """不同 fingerprint 全保留"""
    findings = [
        {
            "file": "a.py",
            "line": 1,
            "category": "dead_code",
            "tool": "vulture",
            "title": "a",
            "severity": "low",
            "confidence": "medium",
            "description": "",
        },
        {
            "file": "b.py",
            "line": 1,
            "category": "dead_code",
            "tool": "vulture",
            "title": "b",
            "severity": "low",
            "confidence": "medium",
            "description": "",
        },
    ]
    assert len(_deduplicate(findings)) == 2


def test_load_fingerprints_missing(tmp_path):
    """文件不存在 → 空 set，不抛错"""
    assert _load_fingerprints(tmp_path) == set()


def test_save_and_load_fingerprints(tmp_path):
    _save_fingerprint(tmp_path, "a.py:1:dead_code:vulture")
    _save_fingerprint(tmp_path, "b.py:2:security:bandit")
    fps = _load_fingerprints(tmp_path)
    assert "a.py:1:dead_code:vulture" in fps
    assert "b.py:2:security:bandit" in fps
    path = tmp_path / ".ccc" / "evolve" / "fingerprints.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert isinstance(data, list)
    assert len(data) == 2


def test_post_finding_creates_backlog_task(tmp_path):
    finding = {
        "file": "src/x.py",
        "line": 9,
        "category": "security",
        "tool": "bandit",
        "severity": "high",
        "confidence": "high",
        "title": "Use of eval",
        "description": "[B307] eval used",
    }
    tid = _post_finding(tmp_path, finding)
    assert tid is not None
    assert tid.startswith("evolve-security-")
    backlog = tmp_path / ".ccc" / "board" / "backlog"
    files = list(backlog.glob("evolve-*.jsonl"))
    assert len(files) == 1
    task = json.loads(files[0].read_text().splitlines()[0])
    assert task["status"] == "backlog"
    assert "evolve" in task["tags"]
    assert "security" in task["tags"]


def test_evolve_run_posts_and_dedups(tmp_path, monkeypatch):
    """mock 分析器：首次投递 top-N，第二次 posted=0"""
    findings = [
        {
            "file": "a.py",
            "line": 1,
            "category": "security",
            "tool": "bandit",
            "severity": "high",
            "confidence": "high",
            "title": "sec-a",
            "description": "[B301] pickle",
        },
        {
            "file": "b.py",
            "line": 2,
            "category": "dead_code",
            "tool": "vulture",
            "severity": "medium",
            "confidence": "medium",
            "title": "dead-b",
            "description": "unused",
        },
        {
            "file": "c.py",
            "line": 3,
            "category": "complexity",
            "tool": "radon",
            "severity": "low",
            "confidence": "high",
            "title": "cc-c",
            "description": "cc 12",
        },
    ]

    health_mod = MagicMock()
    health_mod.analyze_health.return_value = findings[:1]
    sec_mod = MagicMock()
    sec_mod.analyze_security.return_value = findings[1:]

    def fake_load(name, filename):
        if "health" in name:
            return health_mod
        return sec_mod

    import _evolve as evolve_mod

    monkeypatch.setattr(evolve_mod, "_load_analyzer", fake_load)

    r1 = evolve_run(str(tmp_path), max_tasks=2)
    assert r1["posted"] == 2
    assert r1["total"] == 3
    assert len(r1["posted_tasks"]) == 2
    assert all(t.startswith("evolve-") for t in r1["posted_tasks"])

    r2 = evolve_run(str(tmp_path), max_tasks=2)
    assert r2["posted"] == 0
    assert r2["posted_tasks"] == []
