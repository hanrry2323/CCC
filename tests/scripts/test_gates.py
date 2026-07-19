"""test_gates.py — Phase 4.1: engine.gates verdict 解析 + 状态机"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine import gates


def _write_verdict(ws: Path, tid: str, content: str) -> None:
    vf = ws / ".ccc" / "verdicts" / f"{tid}.verdict.md"
    vf.parent.mkdir(parents=True, exist_ok=True)
    vf.write_text(content, encoding="utf-8")


def test_parse_verdict_status_pass(tmp_path):
    assert gates._parse_verdict_status("**Verdict:** PASS") == "PASS"
    assert gates._parse_verdict_status("verdict: pass") == "PASS"


def test_parse_verdict_status_fail(tmp_path):
    content = "# Verdict\n\n**Verdict:** FAIL\n\nreason: tests broken"
    assert gates._parse_verdict_status(content) == "FAIL"


def test_parse_verdict_status_timeout(tmp_path):
    content = "## Review\n\n**Verdict:** TIMEOUT\n"
    assert gates._parse_verdict_status(content) == "TIMEOUT"


def test_parse_verdict_status_none(tmp_path):
    assert gates._parse_verdict_status("no verdict line here") is None
    assert gates._parse_verdict_status("") is None


def test_verdict_is_valid_empty_file(tmp_path):
    ws = tmp_path / "ws"
    _write_verdict(ws, "t1", "")
    assert not gates._verdict_is_valid(ws, "t1")


def test_verdict_is_valid_nonexistent(tmp_path):
    ws = tmp_path / "ws"
    assert not gates._verdict_is_valid(ws, "t1")


def test_verdict_is_valid_nonempty(tmp_path):
    ws = tmp_path / "ws"
    _write_verdict(ws, "t1", "**Verdict:** PASS\n")
    assert gates._verdict_is_valid(ws, "t1")


def test_verdict_is_timeout_detection(tmp_path):
    ws = tmp_path / "ws"
    _write_verdict(ws, "t1", "**Verdict:** TIMEOUT\nreviewer LLM 超时")
    assert gates._verdict_is_timeout(ws, "t1")
    assert gates._verdict_is_valid(ws, "t1")


def test_clear_verdict(tmp_path):
    ws = tmp_path / "ws"
    _write_verdict(ws, "t1", "**Verdict:** PASS\n")
    gates._clear_verdict(ws, "t1")
    assert not gates._verdict_is_valid(ws, "t1")


def test_parse_verdict_status_fallback(tmp_path):
    assert gates._parse_verdict_status("**Verdict:** FALLBACK") == "FALLBACK"
    assert gates._parse_verdict_status("**Verdict:** QUARANTINED") == "QUARANTINED"
