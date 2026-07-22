"""Hub transfer client_request_id 硬幂等 + fingerprint。"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from chat_server import config
from chat_server.services import flow_events


@pytest.fixture()
def desktop_chat_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "CHAT_DIR", tmp_path / "chat")
    config.CHAT_DIR.mkdir(parents=True, exist_ok=True)
    return config.CHAT_DIR


def test_remember_stores_fingerprint(desktop_chat_dir: Path):
    body = {
        "title": "t",
        "goal": "g",
        "acceptance": ["a"],
        "pipeline": "dev",
        "feasibility": "ok",
        "executor_intent": "opencode",
        "complexity": "small",
    }
    fp = flow_events._transfer_payload_fingerprint(body)
    assert fp
    flow_events.remember_last_epic(
        "demo",
        "epic-1",
        "t",
        thread_id="demo::main",
        client_request_id="crid-x",
        payload_fingerprint=fp,
    )
    hit = flow_events.lookup_transfer_by_client_request("demo", "crid-x", payload_fingerprint=fp)
    assert hit and hit["epic_id"] == "epic-1"
    # 不同 payload → 不命中幂等
    other = dict(body)
    other["goal"] = "other"
    fp2 = flow_events._transfer_payload_fingerprint(other)
    assert fp2 != fp
    assert (
        flow_events.lookup_transfer_by_client_request("demo", "crid-x", payload_fingerprint=fp2)
        is None
    )


def test_client_request_mutex_serializes(desktop_chat_dir: Path):
    order: list[str] = []
    lock = flow_events.client_request_mutex("demo", "crid-lock")

    def run(tag: str, hold: float) -> None:
        with lock:
            order.append(f"{tag}-in")
            import time

            time.sleep(hold)
            flow_events.remember_last_epic(
                "demo",
                f"epic-{tag}",
                tag,
                client_request_id="crid-lock",
                payload_fingerprint="fp",
            )
            order.append(f"{tag}-out")

    t1 = threading.Thread(target=run, args=("a", 0.05))
    t2 = threading.Thread(target=run, args=("b", 0.01))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    # 后写覆盖前写，但串行无交错
    assert ("a-out" in order and "b-in" in order)
    assert order.index("a-out") < order.index("b-in") or order.index("b-out") < order.index(
        "a-in"
    )
    hit = flow_events.lookup_transfer_by_client_request("demo", "crid-lock")
    assert hit and hit["epic_id"] in ("epic-a", "epic-b")
