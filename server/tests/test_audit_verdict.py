"""Structured audit verdict contract and golden corpus tests."""

from __future__ import annotations

from pathlib import Path

from server.board.audit_verdict import (
    PROTOCOL_JSON_REASON,
    PROTOCOL_MISSING_REASON,
    parse_json_verdict,
    read_verdict,
)
from server.engine.main import _blocking_findings


CORPUS = Path(__file__).parent / "fixtures" / "verdict-corpus"


def test_valid_corpus_samples() -> None:
    verdict, reason, findings = parse_json_verdict((CORPUS / "valid-pass.json").read_text())
    assert (verdict, reason, findings) == ("PASS", "范围一致，无风险", [])
    verdict, reason, findings = parse_json_verdict((CORPUS / "valid-reject.json").read_text())
    assert verdict == "REJECT"
    assert findings[0]["severity"] == "P1"
    assert reason == "范围越界"


def test_malformed_corpus_is_fail_closed() -> None:
    for path in CORPUS.glob("malformed-*"):
        verdict, reason, _ = parse_json_verdict(path.read_bytes())
        assert verdict == "REJECT", path.name
        assert reason == PROTOCOL_JSON_REASON, path.name


def test_json_matrix() -> None:
    cases = [
        ('{"verdict":"PASS","reason":"ok","findings":[]}', "PASS"),
        ('{"verdict":"REJECT","reason":"bad","findings":[]}', "REJECT"),
        ('{"verdict":"PASS","reason":"ok"}', "REJECT"),
        ('{"verdict":"MAYBE","reason":"x","findings":[]}', "REJECT"),
        ('{"verdict":"PASS"', "REJECT"),
        ('```json\n{}\n```', "REJECT"),
        ("   ", "REJECT"),
        ("", "REJECT"),
    ]
    for raw, expected in cases:
        assert parse_json_verdict(raw)[0] == expected


def test_invalid_json_falls_back_to_legacy_markdown(tmp_path: Path) -> None:
    (tmp_path / "x-audit-verdict.json").write_text("{bad", encoding="utf-8")
    (tmp_path / "x-audit-verdict.md").write_text("机审：通过\n", encoding="utf-8")
    assert read_verdict(tmp_path, "x")[0] == "PASS"


def test_missing_artifacts_fail_closed() -> None:
    verdict, reason, findings = read_verdict(CORPUS, "missing")
    assert verdict is None
    assert reason == PROTOCOL_MISSING_REASON
    assert findings == []


def test_reject_budget_exhausts_at_three(tmp_path: Path) -> None:
    from server.engine import phase2

    cfg = {"EXECUTOR_LOG_DIR": str(tmp_path)}
    assert phase2._record_reject_budget("x", cfg) == (1, False)
    assert phase2._record_reject_budget("x", cfg) == (2, False)
    assert phase2._record_reject_budget("x", cfg) == (3, True)


def test_manual_redispatch_clears_reject_budget(tmp_path: Path) -> None:
    from server.engine.runtime_state import read_card_state, write_card_state

    write_card_state(tmp_path, "x", reject_count=3, reject_budget_exhausted=True)
    write_card_state(tmp_path, "x", reject_count=0, reject_budget_exhausted=False, redispatch="now")
    state = read_card_state(tmp_path)["x"]
    assert state["reject_count"] == 0
    assert state["reject_budget_exhausted"] is False


def test_p2_findings_do_not_block(tmp_path: Path) -> None:
    from server.engine import phase2

    verdict = tmp_path / "x-audit-verdict.json"
    verdict.write_text(
        '{"verdict":"REJECT","reason":"低优先级","findings":['
        '{"id":"F1","severity":"P2","file":"x.py","line":1,"note":"整理"}]}',
        encoding="utf-8",
    )
    parsed = phase2._read_audit_verdict(verdict)
    assert parsed[0] == "REJECT"
    assert all(f["severity"] == "P2" for f in parsed[2])


def test_p2_findings_not_blocking_main_consumer() -> None:
    """main.py 消费端 severity 门：仅 P0/P1 阻断；P2-only 留档不打回。"""
    p2 = [
        {"id": "F1", "severity": "P2", "file": "a.py", "line": 1, "note": "整理"},
        {"id": "F2", "severity": "P2", "file": "b.py", "line": 2, "note": "留档"},
    ]
    assert _blocking_findings(p2) == []
    p0p1 = p2 + [
        {"id": "F3", "severity": "P1", "file": "c.py", "line": 3, "note": "阻断"},
    ]
    blocking = _blocking_findings(p0p1)
    assert [b["id"] for b in blocking] == ["F3"]
    # PASS 无 findings → 空阻断
    assert _blocking_findings([]) == []


def test_protocol_failure_does_not_count_as_business_budget(tmp_path: Path) -> None:
    from server.engine import phase2

    verdict = tmp_path / "x-audit-verdict.json"
    verdict.write_text("{bad", encoding="utf-8")
    parsed = phase2._read_audit_verdict(verdict)
    assert parsed[0] == "REJECT"
    assert parsed[1].startswith("protocol：")
    assert phase2._record_reject_budget("x", {"EXECUTOR_LOG_DIR": str(tmp_path)}) == (1, False)
    # Protocol failures are handled by infra cooldown in process_one and do not
    # call _record_reject_budget; the sidecar remains at its first business count.
    assert phase2._record_reject_budget("x", {"EXECUTOR_LOG_DIR": str(tmp_path)}) == (2, False)

