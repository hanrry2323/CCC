"""Unit tests for chat model resolve + attachment materialization (no live server)."""

from __future__ import annotations

import base64
import shutil
from pathlib import Path

import pytest
from fastapi import HTTPException

from chat_server.routers.chat import _materialize_attachments
from chat_server.services.claude_client import resolve_model


def test_resolve_model_allowlist():
    assert resolve_model("flash") == "flash"
    assert resolve_model("CODE") == "code"
    assert resolve_model("sonnet") == "sonnet"
    assert resolve_model("unknown-model") == "flash"
    assert resolve_model(None) == "flash"
    assert resolve_model("") == "flash"


def test_materialize_text_attachment(tmp_path: Path):
    sid = "unit-att-1"
    note = _materialize_attachments(
        [
            {
                "name": "note.txt",
                "content_base64": base64.b64encode(b"hello ccc").decode(),
            }
        ],
        project_path=str(tmp_path),
        session_id=sid,
    )
    assert "note.txt" in note
    files = list((tmp_path / ".ccc" / "chat-uploads" / sid).iterdir())
    assert len(files) == 1
    assert files[0].read_text() == "hello ccc"


def test_materialize_data_url_image(tmp_path: Path):
    png_header = b"\x89PNG\r\n\x1a\n"
    b64 = base64.b64encode(png_header).decode()
    note = _materialize_attachments(
        [{"name": "a.png", "content_base64": f"data:image/png;base64,{b64}"}],
        project_path=str(tmp_path),
        session_id="unit-att-2",
    )
    assert "a.png" in note


def test_materialize_rejects_exe(tmp_path: Path):
    with pytest.raises(HTTPException) as ei:
        _materialize_attachments(
            [
                {
                    "name": "bad.exe",
                    "content_base64": base64.b64encode(b"x").decode(),
                }
            ],
            project_path=str(tmp_path),
            session_id="unit-att-3",
        )
    assert ei.value.status_code == 400


def test_materialize_rejects_too_many(tmp_path: Path):
    atts = [
        {
            "name": f"f{i}.txt",
            "content_base64": base64.b64encode(b"x").decode(),
        }
        for i in range(9)
    ]
    with pytest.raises(HTTPException) as ei:
        _materialize_attachments(atts, project_path=str(tmp_path), session_id="unit-att-4")
    assert ei.value.status_code == 400
