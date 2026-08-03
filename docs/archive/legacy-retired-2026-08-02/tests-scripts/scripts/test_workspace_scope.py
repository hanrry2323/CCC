"""workspace_scope must activate board.context + thread-local ctx."""
from __future__ import annotations

from pathlib import Path

from engine.workspace import (
    _activate_workspace,
    get_current_workspace,
    workspace_scope,
)


def test_workspace_scope_sets_ctx_and_clears(tmp_path: Path, monkeypatch) -> None:
    calls: list[Path] = []

    def _fake_activate(ws: Path) -> Path:
        resolved = ws.resolve()
        calls.append(resolved)
        return resolved

    monkeypatch.setattr("engine.workspace._activate_workspace", _fake_activate)
    monkeypatch.setattr(
        "engine.workspace._get_store",
        lambda ws: type("S", (), {"workspace": ws})(),
    )

    ws = tmp_path / "app"
    ws.mkdir()
    assert get_current_workspace() is None
    with workspace_scope(ws) as ctx:
        assert ctx.ws == ws.resolve()
        cur = get_current_workspace()
        assert cur is not None
        assert cur.ws == ws.resolve()
        assert calls == [ws.resolve()]
    assert get_current_workspace() is None


def test_workspace_scope_nests_restore_prev(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "engine.workspace._activate_workspace", lambda ws: ws.resolve()
    )
    monkeypatch.setattr(
        "engine.workspace._get_store",
        lambda ws: type("S", (), {"workspace": ws})(),
    )
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    with workspace_scope(a):
        assert get_current_workspace() is not None
        assert get_current_workspace().ws == a.resolve()
        with workspace_scope(b):
            assert get_current_workspace().ws == b.resolve()
        assert get_current_workspace().ws == a.resolve()
    assert get_current_workspace() is None


def test_activate_workspace_still_callable(tmp_path: Path, monkeypatch) -> None:
    seen: list[Path] = []

    def _set_ws(ws: Path | str) -> Path:
        p = Path(ws).resolve()
        seen.append(p)
        return p

    monkeypatch.setattr("engine.workspace.set_workspace", _set_ws)
    monkeypatch.setattr("engine.workspace._reset_board_lazy", lambda: None)
    ws = tmp_path / "w"
    ws.mkdir()
    out = _activate_workspace(ws)
    assert out == ws.resolve()
    assert seen == [ws.resolve()]
