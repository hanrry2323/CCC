"""inbox proposals parse / transfer body."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from chat_server.services import proposals as prop  # noqa: E402


def test_parse_and_transfer_body(tmp_path, monkeypatch):
    monkeypatch.setattr(prop.config, "PROJECT_ROOT", tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "adopted").mkdir()
    sample = inbox / "demo-prop.md"
    sample.write_text(
        "---\n"
        "project: ccc-demo\n"
        "title: Demo Prop\n"
        "action: transfer\n"
        "acceptance: a|b\n"
        "---\n\n"
        "Body goal paragraph.\n",
        encoding="utf-8",
    )
    items = prop.list_proposals()
    assert any(i["id"] == "demo-prop" for i in items)
    p = prop.get_proposal("demo-prop")
    assert p and p["project_id"] == "ccc-demo"
    body = prop.proposal_to_transfer_body(p, client_request_id="cr1")
    assert body["project_id"] == "ccc-demo"
    assert body["feasibility"] == "ok"
    assert "a" in body["acceptance"]
    dst = prop.mark_adopted("demo-prop")
    assert dst is not None and dst.is_file()
    assert not sample.exists()
