"""Smoke tests for ccc-zcode-bridge.sh.

Verifies:
1. --dry-run 模式生成 UUID 并校验 prompt 文件
2. 缺参数 exit 2
3. role 非法 exit 2
4. prompt 文件缺失 exit 1
5. UUID 复用(第二次读现有 UUID,不重生成)

非 dry-run 模式需要真跑 claude,不在 smoke 范围。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "ccc-zcode-bridge.sh"


def _run_bridge(*args: str, cwd: Path | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """Create a fake workspace with .ccc/plans/ ready."""
    (tmp_path / ".ccc" / "plans").mkdir(parents=True)
    (tmp_path / ".ccc" / "dispatches").mkdir(parents=True)
    return tmp_path


def test_help_exits_zero():
    """-h 应直接打印帮助退出 0。"""
    p = _run_bridge("-h")
    assert p.returncode == 0
    assert "ccc-zcode-bridge.sh" in p.stdout
    assert "用法" in p.stdout or "usage" in p.stdout.lower()


def test_missing_args_exits_2():
    """缺任何必填参数 → exit 2。"""
    p = _run_bridge()
    assert p.returncode == 2
    assert "用法" in p.stderr or "usage" in p.stderr.lower()


def test_only_workspace_exits_2():
    """只传 workspace 不够。"""
    p = _run_bridge("/tmp")
    assert p.returncode == 2


def test_invalid_role_exits_2(sandbox: Path):
    """role 非法(非 executor/verifier)→ exit 2。"""
    p = _run_bridge(str(sandbox), "demo", "planner")  # planner 是 Planner 角色,不归 bridge
    assert p.returncode == 2
    assert "executor 或 verifier" in p.stderr


def test_dry_run_with_valid_prompt_exits_0(sandbox: Path):
    """--dry-run + 完整参数 + 存在 prompt 文件 → exit 0 + 生成 UUID。"""
    prompt_file = sandbox / ".ccc" / "plans" / "demo-executor-prompt.txt"
    prompt_file.write_text("# Executor Prompt\nDo the work.\n")

    p = _run_bridge(str(sandbox), "demo", "executor", "--dry-run", cwd=sandbox)

    assert p.returncode == 0, f"stdout={p.stdout!r} stderr={p.stderr!r}"
    assert "DRY-RUN" in p.stdout
    assert "session_id" in p.stdout
    assert "glm-5" in p.stdout or "model" in p.stdout

    # UUID 必须落盘
    sid_file = sandbox / ".ccc" / "plans" / "demo-executor-session-id.txt"
    assert sid_file.exists()
    uuid_str = sid_file.read_text().strip()
    # 简单 UUID 格式校验
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        uuid_str,
    ), f"bad UUID: {uuid_str}"

    # spawn 报告也必须写
    reports = list((sandbox / ".ccc" / "dispatches").glob("spawn-demo-executor-*.json"))
    assert len(reports) == 1
    import json
    rep = json.loads(reports[0].read_text())
    assert rep["status"] == "dry-run"
    assert rep["role"] == "executor"
    assert rep["session_id"] == uuid_str
    # JSON 里 dry_run 写成裸 1,Python json.load 会读成 int 1,不是 bool True
    assert rep["dry_run"] in (1, True)


def test_dry_run_missing_prompt_exits_1(sandbox: Path):
    """prompt 文件缺失 → exit 1,且 spawn 报告记录 failure。"""
    p = _run_bridge(str(sandbox), "demo", "executor", "--dry-run", cwd=sandbox)

    assert p.returncode == 1
    assert "prompt 文件不存在" in p.stderr

    # spawn 报告仍生成,记录 failure
    reports = list((sandbox / ".ccc" / "dispatches").glob("spawn-demo-executor-*.json"))
    assert len(reports) == 1
    import json
    rep = json.loads(reports[0].read_text())
    assert rep["status"] == "failed"
    assert rep["failure_reason"] == "prompt_file_missing"


def test_uuid_reused_on_second_call(sandbox: Path):
    """第二次调用应复用已落盘的 UUID(红线 6 session 隔离 + 可追溯)。"""
    prompt_file = sandbox / ".ccc" / "plans" / "demo-verifier-prompt.txt"
    prompt_file.write_text("# Verifier Prompt\nCheck the work.\n")

    p1 = _run_bridge(str(sandbox), "demo", "verifier", "--dry-run", cwd=sandbox)
    assert p1.returncode == 0
    uuid1 = (sandbox / ".ccc" / "plans" / "demo-verifier-session-id.txt").read_text().strip()

    p2 = _run_bridge(str(sandbox), "demo", "verifier", "--dry-run", cwd=sandbox)
    assert p2.returncode == 0
    uuid2 = (sandbox / ".ccc" / "plans" / "demo-verifier-session-id.txt").read_text().strip()

    assert uuid1 == uuid2, "UUID 必须复用,不重生成"


def test_executor_and_verifier_get_distinct_uuids(sandbox: Path):
    """executor 和 verifier 必须分配不同 UUID(红线 6)。"""
    (sandbox / ".ccc" / "plans" / "demo-executor-prompt.txt").write_text("e\n")
    (sandbox / ".ccc" / "plans" / "demo-verifier-prompt.txt").write_text("v\n")

    _run_bridge(str(sandbox), "demo", "executor", "--dry-run", cwd=sandbox)
    _run_bridge(str(sandbox), "demo", "verifier", "--dry-run", cwd=sandbox)

    exec_uuid = (sandbox / ".ccc" / "plans" / "demo-executor-session-id.txt").read_text().strip()
    ver_uuid = (sandbox / ".ccc" / "plans" / "demo-verifier-session-id.txt").read_text().strip()

    assert exec_uuid != ver_uuid


def test_spawn_report_includes_anthropic_base_url(sandbox: Path):
    """spawn 报告应包含 base_url,便于追溯(红线 10)。"""
    prompt_file = sandbox / ".ccc" / "plans" / "demo-executor-prompt.txt"
    prompt_file.write_text("e\n")

    _run_bridge(str(sandbox), "demo", "executor", "--dry-run", cwd=sandbox)

    import json
    report = json.loads(list((sandbox / ".ccc" / "dispatches").glob("spawn-demo-executor-*.json"))[0].read_text())
    assert "anthropic_base_url" in report
    # base_url 可能是 BigModel 也可能是中转站(http://127.0.0.1:4000),
    # 只要看起来是合法 URL 即可
    base_url = report["anthropic_base_url"]
    assert base_url.startswith("http://") or base_url.startswith("https://"), \
        f"unexpected base_url: {base_url}"
    assert report["model"] == "glm-5"