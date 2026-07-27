"""docs-only / doc_only stamps must skip forced full-repo pytest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_docs_only_scope_skips_forced_pytest(tmp_path: Path):
    from _ccc_hygiene import scopes_are_docs_only, task_skips_forced_pytest

    assert scopes_are_docs_only(["docs/reports/stamp.md"]) is True
    assert scopes_are_docs_only(["scripts/x.py"]) is False

    ws = tmp_path / "app"
    tid = "doc-w1"
    (ws / ".ccc" / "phases").mkdir(parents=True)
    (ws / ".ccc" / "reports").mkdir(parents=True)
    (ws / ".ccc" / "phases" / f"{tid}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": ["docs/reports/ccc-layer1-golden-path-v3.md"]})
        + "\n",
        encoding="utf-8",
    )
    task = {
        "id": tid,
        "title": "Layer1 文档戳记报告 v3",
        "tags": ["exec:opencode"],
    }
    assert task_skips_forced_pytest(ws, tid, task) is True

    # path=doc_only also skips even with empty scopes
    tid2 = "doc-w2"
    (ws / ".ccc" / "phases" / f"{tid2}.phases.json").write_text(
        json.dumps({"phase": 1, "scope": []}) + "\n", encoding="utf-8"
    )
    (ws / ".ccc" / "reports" / f"{tid2}.result.json").write_text(
        json.dumps({"path": "doc_only"}) + "\n", encoding="utf-8"
    )
    assert task_skips_forced_pytest(ws, tid2, {"id": tid2, "title": "x"}) is True
