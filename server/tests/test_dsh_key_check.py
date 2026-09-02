"""scripts/dsh-key-check.sh 三态判定测试（P0-1）。

测试替身：PATH 前置一个「假 curl 桩」（绝不访问网络），按 FAKE_* 环境变量
输出伪 HTTP 结果，仅用于验证判定逻辑——不代表任何真实通道可用性。
所有非 PASS 场景断言退出码非 0（P0-1 红线：000/异常不得 PASS）。
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "dsh-key-check.sh"

_FAKE_CURL = textwrap.dedent(
    """\
    #!/bin/bash
    # 测试替身 curl（P0-1）：绝不访问网络；按 FAKE_* 输出伪 HTTP 结果。
    out=""
    wfmt=""
    want=""
    for a in "$@"; do
      case "$a" in
        -o) want=o ;;
        -w) want=w ;;
        *) if [[ "$want" == "o" ]]; then out="$a"; want=""; elif [[ "$want" == "w" ]]; then wfmt="$a"; want=""; fi ;;
      esac
    done
    code="${FAKE_HTTP_CODE:-200}"
    if [[ -n "$out" ]]; then
      printf '%s' "${FAKE_BODY-default}" > "$out"
    fi
    if [[ "$wfmt" == *"http_code"* ]]; then printf '%s' "$code"; fi
    exit "${FAKE_CURL_RC:-0}"
    """
)

_OK_BODY = '{"content":[{"type":"text","text":"ok"}],"model":"claude-4-5-haiku"}'


@pytest.fixture()
def fake_curl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "curl"
    stub.write_text(_FAKE_CURL, encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ.get('PATH', '')}")
    monkeypatch.setenv("OPENCODE_GO_API_KEY", "sk-test-fake-not-a-real-key")
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.delenv("DSH_PROBE_URL", raising=False)
    monkeypatch.delenv("DSH_PROBE_MODEL", raising=False)
    monkeypatch.delenv("CCC_CONFIG_ENV", raising=False)
    return {"tmp": tmp_path}


def _run(env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["bash", str(SCRIPT), "--quiet"],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
    )


def _set(monkeypatch: pytest.MonkeyPatch, **kw: str) -> None:
    for k, v in kw.items():
        monkeypatch.setenv(k, v)


def test_pass_on_200(fake_curl, monkeypatch) -> None:
    _set(monkeypatch, FAKE_HTTP_CODE="200", FAKE_BODY=_OK_BODY)
    assert _run().returncode == 0


def test_429_is_quota_and_ledger_alert(fake_curl, monkeypatch) -> None:
    """429 → QUOTA_EXHAUSTED(2) 且写隔离 ledger dsh_quota_alert（不碰生产账本）。"""
    _set(monkeypatch, FAKE_HTTP_CODE="429")
    r = _run()
    assert r.returncode == 2
    ledger = fake_curl["tmp"] / "ledger.jsonl"
    assert ledger.is_file(), "429 应写 ledger dsh_quota_alert（隔离临时账本）"
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any(x.get("action") == "dsh_quota_alert" for x in rows)


@pytest.mark.parametrize("code", ["401", "403"])
def test_auth_error(fake_curl, monkeypatch, code: str) -> None:
    _set(monkeypatch, FAKE_HTTP_CODE=code)
    assert _run().returncode == 3


@pytest.mark.parametrize("code", ["500", "502", "503"])
def test_upstream_error(fake_curl, monkeypatch, code: str) -> None:
    _set(monkeypatch, FAKE_HTTP_CODE=code)
    assert _run().returncode == 4


@pytest.mark.parametrize("rc", ["6", "7", "28", "35", "60"])
def test_network_failure_unavailable(fake_curl, monkeypatch, rc: str) -> None:
    """DNS(6)/连接拒绝(7)/超时(28)/TLS(35,60) + http=000 → PROBE_UNAVAILABLE(5)，绝不 PASS。"""
    _set(monkeypatch, FAKE_HTTP_CODE="000", FAKE_CURL_RC=rc)
    assert _run().returncode == 5


def test_empty_200_unavailable(fake_curl, monkeypatch) -> None:
    _set(monkeypatch, FAKE_HTTP_CODE="200", FAKE_BODY="")
    assert _run().returncode == 5


def test_unparseable_200_unavailable(fake_curl, monkeypatch) -> None:
    _set(monkeypatch, FAKE_HTTP_CODE="200", FAKE_BODY="not-json-garbage")
    assert _run().returncode == 5


def test_unknown_http_is_error(fake_curl, monkeypatch) -> None:
    _set(monkeypatch, FAKE_HTTP_CODE="418")
    assert _run().returncode == 7


def test_no_key_is_no_key(fake_curl, monkeypatch, tmp_path: Path) -> None:
    """无 key → NO_KEY(6)，不得用 PASS(0) 伪装跳过。HOME 隔离防 dsh-key.sh 读到真实 plist。"""
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    monkeypatch.delenv("OPENCODE_GO_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(empty_home))
    assert _run().returncode == 6
