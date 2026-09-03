"""网关环境自包含 + 配额预检测试（ccc-plan-053 阶段3）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.engine import dsh_gateway, phase2
from server.engine.dispatch import ExecutorEntry, ExecutorRegistry
from server.engine.main import _build_dispatch_gates
from server.engine.gates import GateContext
from server.engine.pool import DispatchPool
from server.engine.store import InMemoryBoardStore
from server.engine.task import State, Work


@pytest.fixture()
def iso_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("CCC_AUDIT_LEDGER", str(ledger))
    return ledger


def _ledger_actions(ledger: Path) -> list[dict]:
    import json

    if not ledger.is_file():
        return []
    return [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_cli_env_self_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    """env -i 语境：cli_env 显式导出网关三件 + key 单源注入（不含裸 env 依赖）。"""
    monkeypatch.setattr(dsh_gateway, "resolve_key", lambda: "sk-test-fake")
    env = dsh_gateway.cli_env(base_env={})
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:3456/v1/messages"
    assert env["ANTHROPIC_MODEL"] == "Code"
    assert env["ANTHROPIC_API_KEY"] == "sk-test-fake"
    assert env["OPENCODE_GO_API_KEY"] == "sk-test-fake"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "Code"


def test_cli_env_never_prints_key_in_detail() -> None:
    """key 值不得进入任何 detail/日志字符串（泄漏红线）。"""
    assert "sk-" not in dsh_gateway.ANTHROPIC_BASE_URL
    assert "sk-" not in dsh_gateway.ANTHROPIC_MODEL


def test_preflight_missing_key_refuses_and_alerts(iso_ledger: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """拔 key：预检拒单 + ledger dsh_quota_alert 留痕。"""
    monkeypatch.setattr(dsh_gateway, "resolve_key", lambda: "")
    ok, detail = dsh_gateway.preflight_gateway(force=True)
    assert ok is False
    assert "拔 key" in detail or "无 OPENCODE_GO_API_KEY" in detail
    rows = [r for r in _ledger_actions(iso_ledger) if r.get("action") == "dsh_quota_alert"]
    assert len(rows) == 1
    assert rows[0]["source"] == "engine"


def test_preflight_429_refuses(iso_ledger: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """429（脚本 exit 2）→ 拒单；脚本自身负责 ledger 告警，此处不重复。"""
    monkeypatch.setattr(dsh_gateway, "resolve_key", lambda: "sk-test-fake")

    class FakeProc:
        returncode = 2
        stdout = ""
        stderr = ""

    monkeypatch.setattr(dsh_gateway.subprocess, "run", lambda *a, **k: FakeProc())
    ok, detail = dsh_gateway.preflight_gateway(force=True)
    assert ok is False
    assert "429" in detail


def test_preflight_ok_caches(iso_ledger: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """探针 200（exit 0）→ 放行；TTL 内不再打网关。"""
    monkeypatch.setattr(dsh_gateway, "resolve_key", lambda: "sk-test-fake")
    calls = {"n": 0}

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*a, **k):
        calls["n"] += 1
        return FakeProc()

    monkeypatch.setattr(dsh_gateway.subprocess, "run", fake_run)
    ok1, _ = dsh_gateway.preflight_gateway(force=True)
    ok2, _ = dsh_gateway.preflight_gateway()  # TTL 内缓存
    assert ok1 and ok2
    assert calls["n"] == 1


@pytest.mark.parametrize("rc", [3, 4, 5, 6, 7])
def test_preflight_nonpass_rc_refuses(iso_ledger: Path, monkeypatch: pytest.MonkeyPatch, rc: int) -> None:
    """P0-1：AUTH/UPSTREAM/UNAVAILABLE/NO_KEY/ERROR 退出码一律拒单，不得静默放行。"""
    monkeypatch.setattr(dsh_gateway, "resolve_key", lambda: "sk-test-fake")

    class FakeProc:
        returncode = rc
        stdout = ""
        stderr = ""

    monkeypatch.setattr(dsh_gateway.subprocess, "run", lambda *a, **k: FakeProc())
    ok, detail = dsh_gateway.preflight_gateway(force=True)
    assert ok is False
    assert "拒单" in detail


def test_preflight_probe_spawn_failure_blocks(iso_ledger: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P0-1：预检进程自身起不来（OSError）→ 拒单（探针不可用=明确错误态），不再放行。"""
    monkeypatch.setattr(dsh_gateway, "resolve_key", lambda: "sk-test-fake")

    def boom(*a, **k):
        raise OSError("bash not found")

    monkeypatch.setattr(dsh_gateway.subprocess, "run", boom)
    ok, detail = dsh_gateway.preflight_gateway(force=True)
    assert ok is False
    assert "unavailable" in detail or "不可用" in detail


def test_phase2_audit_refuses_on_preflight_fail(iso_ledger: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """phase2 审核：预检拒单 → verdict ERROR + attempts=0 + ledger phase2_alert，卡不烧重试。"""

    def boom(*a, **k):
        raise AssertionError("预检拒单后不得调用 claude")

    monkeypatch.setattr(phase2, "preflight_gateway", lambda **k: (False, "429 周配额耗尽，拒单"))
    monkeypatch.setattr(phase2, "_run_claude", boom)
    res = phase2.audit_card({"id": "tst998"}, Path("x.md"), "codex/x", {}, audit_driver="real")
    assert res["verdict"] == "ERROR"
    assert res["attempts"] == 0
    assert "网关预检拒单" in res["reasons"]
    rows = [r for r in _ledger_actions(iso_ledger) if r.get("action") == "phase2_alert"]
    assert len(rows) == 1
    assert "网关预检拒单" in rows[0]["detail"]


def _mk_ctx(tmp_path: Path, work: Work, registry: ExecutorRegistry) -> GateContext:
    class _StubPool:
        pass

    return GateContext(
        work=work,
        registry=registry,
        by_id={work.id: work},
        runtime={},
        now_ts=1000.0,
        store=InMemoryBoardStore(),
        log_dir=tmp_path / "logs",
        cfg={},
        pool=_StubPool(),  # type: ignore[arg-type]
        probe_url="",
        slots=1,
        max_concurrent=1,
        timeout=30,
    )


def _dsh_quota_gate():
    gates = {g.name: g for g in _build_dispatch_gates().ordered()}
    return gates["dsh_quota"]


def test_engine_gate_only_guards_dsh_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """engine 门禁：dsh-executor 命令才预检；demo/echo 命令零打扰。"""
    reg = ExecutorRegistry(
        (
            ExecutorEntry(role="开发执行体", category="可后台 CLI", binding="demo", note="", command="echo"),
        )
    )
    work = Work(id="t1", role="开发执行体", card_path=str(tmp_path / "t1.md"), state=State.TODO)
    monkeypatch.setattr(
        "server.engine.main.preflight_gateway",
        lambda **k: (_ for _ in ()).throw(AssertionError("非 DSH 命令不应预检")),
    )
    res = _dsh_quota_gate().check(_mk_ctx(tmp_path, work, reg))
    assert res.passed  # demo 命令不被 dsh_quota 拦截


def test_engine_gate_blocks_dsh_on_preflight_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """engine 门禁：dsh-executor 命令 + 预检失败 → 拒单（reason=dsh_quota）。"""
    reg = ExecutorRegistry(
        (
            ExecutorEntry(
                role="开发执行体",
                category="可后台 CLI",
                binding="DSH",
                note="",
                command="/Users/fan/program/CCC/scripts/dsh-executor.sh",
            ),
        )
    )
    work = Work(id="t2", role="开发执行体", card_path=str(tmp_path / "t2.md"), state=State.TODO)
    monkeypatch.setattr("server.engine.main.preflight_gateway", lambda **k: (False, "429"))
    res = _dsh_quota_gate().check(_mk_ctx(tmp_path, work, reg))
    assert res.passed is False and res.reason == "dsh_quota"
