"""项目即对话：flow epic 列表 ::main 视图 + 迁移脚本。"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def flow_events_mod(tmp_path, monkeypatch):
    d = tmp_path / "chat"
    d.mkdir()
    monkeypatch.setenv("CCC_CHAT_DIR", str(d))
    import chat_server.config as config

    config.CHAT_DIR = d
    from chat_server.services import flow_events

    # 确保文件函数读到新 CHAT_DIR
    monkeypatch.setattr(flow_events.config, "CHAT_DIR", d)
    return d, flow_events


def test_list_recent_epics_main_is_project_view(flow_events_mod):
    _d, flow_events = flow_events_mod
    pid = "demo"
    flow_events.remember_last_epic(pid, "epic-old", "旧", thread_id="uuid-aaaa")
    flow_events.remember_last_epic(pid, "epic-new", "新", thread_id="demo::main")

    items = flow_events.list_recent_epics(pid, thread_id="demo::main", limit=20)
    ids = [x["epic_id"] for x in items]
    assert "epic-old" in ids
    assert "epic-new" in ids

    only = flow_events.list_recent_epics(pid, thread_id="uuid-aaaa", limit=20)
    assert [x["epic_id"] for x in only] == ["epic-old"]

    hint = flow_events.bound_hint_for_epics(items, thread_id="demo::main")
    assert hint == "epic-new"


def test_canonical_conversation_id(flow_events_mod):
    _, flow_events = flow_events_mod
    assert flow_events.canonical_conversation_id("foo") == "foo::main"
    assert flow_events.is_project_conversation_id("foo::main")
    assert not flow_events.is_project_conversation_id("uuid-1")


def test_migrate_rewrites_thread_ids(tmp_path):
    chat = tmp_path / "chat"
    desktop = chat / "_desktop" / "app1"
    desktop.mkdir(parents=True)
    hist = [
        {"epic_id": "e1", "title": "a", "thread_id": "old-uuid"},
        {"epic_id": "e2", "title": "b", "thread_id": "app1::main"},
    ]
    (desktop / "epic_history.json").write_text(json.dumps(hist), encoding="utf-8")
    (desktop / "last_epic.json").write_text(
        json.dumps({"epic_id": "e1", "thread_id": "old-uuid"}),
        encoding="utf-8",
    )
    sess_dir = chat / "app1"
    sess_dir.mkdir()
    (sess_dir / "old-uuid.json").write_text(
        json.dumps(
            {
                "session_id": "old-uuid",
                "project": "app1",
                "messages": [{"role": "user", "content": "hi"}],
            }
        ),
        encoding="utf-8",
    )

    spec = importlib.util.spec_from_file_location(
        "migrate_bind",
        ROOT / "scripts" / "migrate-desktop-conversation-bind.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    mod.migrate_chat_dir(chat, dry_run=False)

    new_hist = json.loads((desktop / "epic_history.json").read_text(encoding="utf-8"))
    assert all(x.get("thread_id") == "app1::main" for x in new_hist)
    last = json.loads((desktop / "last_epic.json").read_text(encoding="utf-8"))
    assert last["thread_id"] == "app1::main"
    main = json.loads((sess_dir / "app1::main.json").read_text(encoding="utf-8"))
    assert any(m.get("content") == "hi" for m in main.get("messages") or [])
    assert (sess_dir / "old-uuid.json.migrated").is_file()
