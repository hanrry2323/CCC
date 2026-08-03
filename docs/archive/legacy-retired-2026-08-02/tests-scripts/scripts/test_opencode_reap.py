"""Unit tests for scripts/_opencode_reap.py."""
from __future__ import annotations

import os
from pathlib import Path

from _opencode_reap import (
    claimed_alive_pids,
    etime_to_sec,
    list_opencode_for_workspace,
    pid_alive,
    reap_opencode_workspace,
)


def test_etime_to_sec_variants():
    assert etime_to_sec("05:01") == 5 * 60 + 1
    assert etime_to_sec("1:02:03") == 3600 + 120 + 3
    assert etime_to_sec("2-01:00:00") == 2 * 86400 + 3600


def test_claimed_alive_skips_dead_pid(tmp_path: Path):
    pids = tmp_path / ".ccc" / "pids"
    pids.mkdir(parents=True)
    (pids / "dead.pid").write_text("999999991\n")
    (pids / "self.pid").write_text(f"{os.getpid()}\n")
    claimed = claimed_alive_pids(tmp_path)
    assert os.getpid() in claimed
    assert 999999991 not in claimed


def test_reap_kills_unclaimed_old(tmp_path: Path, monkeypatch):
    ws = tmp_path.resolve()
    ps_out = (
        f" 11111 45:00 opencode run --model x --dir {ws} do stuff\n"
        f" 22222 00:05 opencode run --model x --dir {ws} young\n"
    )
    killed: list[tuple[int, int]] = []

    def fake_check_output(*_a, **_k):
        return ps_out

    def fake_killpg(pid, sig):
        killed.append((pid, sig))

    monkeypatch.setattr(
        "subprocess.check_output", fake_check_output
    )
    monkeypatch.setattr("os.killpg", fake_killpg)
    monkeypatch.setattr("os.kill", fake_killpg)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    out = reap_opencode_workspace(ws, max_age_sec=600, grace_sec=0)
    assert 11111 in out
    assert 22222 not in out


def test_reap_immediate_age_zero(tmp_path: Path, monkeypatch):
    ws = tmp_path.resolve()
    ps_out = f" 33333 00:01 opencode run --dir {ws} leaf\n"
    killed: list[int] = []

    monkeypatch.setattr(
        "subprocess.check_output", lambda *_a, **_k: ps_out
    )

    def fake_killpg(pid, sig):
        killed.append(pid)

    monkeypatch.setattr("os.killpg", fake_killpg)
    monkeypatch.setattr("os.kill", fake_killpg)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    out = reap_opencode_workspace(ws, max_age_sec=0, grace_sec=0)
    assert out == [33333]
    assert 33333 in killed


def test_list_filters_other_workspace(tmp_path: Path, monkeypatch):
    ws = tmp_path.resolve()
    other = Path("/tmp/other-ws-xyz")
    ps_out = (
        f" 1 01:00 opencode run --dir {other} a\n"
        f" 2 01:00 opencode run --dir {ws} b\n"
    )
    monkeypatch.setattr(
        "subprocess.check_output", lambda *_a, **_k: ps_out
    )
    found = list_opencode_for_workspace(ws)
    assert found == [(2, 60)]


def test_pid_alive_self():
    assert pid_alive(os.getpid()) is True
    assert pid_alive(0) is False
