"""test_ccc_status_smoke.py — Smoke tests for ccc-status.sh (v1.0).

Validates:
  - 文本输出包含 "CCC 4-file contract"
  - --json 输出可解析且含 4 个 key
  - 输出含 "ok" 状态 (说明 .ccc/ 契约文件被检测)
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
STATUS_SH = ROOT / "scripts" / "ccc-status.sh"


def _run(args, workspace=None):
    """Run ccc-status.sh with given args, return (returncode, stdout, stderr)."""
    if workspace is None:
        workspace = ROOT
    proc = subprocess.run(
        ["bash", str(STATUS_SH), *args],
        capture_output=True,
        timeout=10,
        cwd=str(workspace),
    )
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()


def test_status_text_output():
    """文本输出应含 'CCC 4-file contract' 段头."""
    rc, out, _ = _run([])
    assert rc == 0, f"expected exit 0, got {rc}"
    assert "CCC 4-file contract" in out, f"missing contract header in: {out!r}"


def test_status_json_output():
    """--json 输出应可解析为含 4 个 key 的 dict."""
    rc, out, _ = _run(["--json"])
    assert rc == 0, f"expected exit 0, got {rc}: {out}"
    data = json.loads(out)
    assert isinstance(data, dict), f"expected dict, got {type(data).__name__}"
    expected_keys = {"profile", "state", "plans", "tasks"}
    assert set(data.keys()) == expected_keys, (
        f"expected keys {expected_keys}, got {set(data.keys())}"
    )


def test_status_handles_missing_verdict():
    """即使 .ccc/verdicts/ 为空,输出也应含 'ok' (说明其他契约文件存在)."""
    rc, out, _ = _run([])
    assert rc == 0
    assert "ok" in out, f"expected 'ok' marker in output: {out!r}"