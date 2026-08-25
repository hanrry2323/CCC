"""ccc083 防旋修复回归单测。

覆盖四组回归面（对应 2026-08-24 ccc078 机审连环 kickstart 风暴的取证结论）：
1. 击杀语义退出码（137/143/-9/-15）判基础设施故障，不烧业务重试预算；
2. 短命会话计数熔断：窗口/寿命/ok 过滤、阈值触发、告警文件落盘；
3. 业务重试指数退避：秒数单调封顶、退避期判定、收单成功清除；
4. 会话探针：worker-events.jsonl 的 kind=session 行含会话寿命/短命标记/编辑命中；
5. bash 层：watchdog 防旋闸（连续确认→DRY-RUN 触发→冷却拦截）与 kickstart 冷却/DRY-RUN。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from server.engine import main as engine_main
from server.engine import metrics

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT_ROOT / "scripts"


# ───────────────────────── 1. 击杀语义退出码 → 基础设施故障 ─────────────────────────


@pytest.mark.parametrize("code", ["137", "143", "-9", "-15", "-137", "-143"])
def test_kill_exit_codes_classified_infra(tmp_path: Path, code: str) -> None:
    ok, hint = engine_main.is_retryable_failure(
        "w1", [f"退出码非 0: {code}（日志: {tmp_path}/w1.log）"], tmp_path, phase="run"
    )
    assert ok is True
    assert "击杀语义" in hint


@pytest.mark.parametrize("code", ["1", "2", "9", "15", "127", "9001"])
def test_normal_exit_codes_not_infra(tmp_path: Path, code: str) -> None:
    ok, _hint = engine_main.is_retryable_failure(
        "w1", [f"退出码非 0: {code}（日志: {tmp_path}/missing.log）"], tmp_path, phase="run"
    )
    assert ok is False


def test_exit_137_no_longer_burns_business_retry(tmp_path: Path) -> None:
    """ccc079 实证回归：audit exit 137 曾走业务重试 retry=1/3；现在必须判 infra。"""
    problems = ["退出码非 0: 137（日志: /Users/fan/.ccc/logs/exec/x.audit.log）"]
    ok, _ = engine_main.is_retryable_failure("x", problems, tmp_path, phase="audit")
    assert ok is True


# ───────────────────────── 2. 短命会话计数熔断 ─────────────────────────


def _append_worker_event(
    path: Path,
    *,
    ts: str,
    ok: bool = False,
    duration_s: float = 60.0,
    work_id: str = "w1",
) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": ts,
                    "kind": "worker",
                    "work_id": work_id,
                    "phase": "run",
                    "ok": ok,
                    "returncode": 0 if ok else 1,
                    "duration_s": duration_s,
                    "exit_kind": "ok" if ok else "nonzero",
                    "problem": None,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _iso(ts: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def test_count_recent_short_sessions_filters(tmp_path: Path) -> None:
    events = tmp_path / "worker-events.jsonl"
    now = time.time()
    # 窗口内短命失败 ×2
    _append_worker_event(events, ts=_iso(now - 30), duration_s=100)
    _append_worker_event(events, ts=_iso(now - 60), duration_s=299)
    # 窗口内长命失败 → 不计
    _append_worker_event(events, ts=_iso(now - 90), duration_s=301)
    # 窗口内成功 → 不计
    _append_worker_event(events, ts=_iso(now - 120), ok=True, duration_s=50)
    # 寿命字段缺失 → 不计（容错）
    with events.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": _iso(now - 10), "kind": "worker", "ok": False}) + "\n")
    # 窗口外短命失败 → 不计
    _append_worker_event(events, ts=_iso(now - 3600), duration_s=100)
    assert engine_main.count_recent_short_sessions(events, now, window_s=600, short_s=300) == 2


def test_count_recent_short_sessions_missing_file(tmp_path: Path) -> None:
    assert engine_main.count_recent_short_sessions(tmp_path / "nope.jsonl") == 0


def test_breaker_trips_at_threshold_and_writes_alert(tmp_path: Path) -> None:
    events = tmp_path / "worker-events.jsonl"
    now = time.time()
    for i in range(5):
        _append_worker_event(events, ts=_iso(now - 10 * (i + 1)), duration_s=42)
    tripped, detail = engine_main.short_session_breaker_status(
        tmp_path, {"EXECUTOR_SHORT_SESSION_MAX_COUNT": 5}, now_ts=now
    )
    assert tripped is True
    assert "5 个" in detail
    engine_main._write_short_session_alert(tmp_path, detail, now)
    alert = tmp_path / "alerts" / "short-session-breaker.txt"
    assert alert.is_file()
    assert "短命会话熔断" in alert.read_text(encoding="utf-8")


def test_breaker_stays_open_below_threshold(tmp_path: Path) -> None:
    events = tmp_path / "worker-events.jsonl"
    now = time.time()
    for i in range(4):
        _append_worker_event(events, ts=_iso(now - 10 * (i + 1)), duration_s=42)
    tripped, _detail = engine_main.short_session_breaker_status(
        tmp_path, {"EXECUTOR_SHORT_SESSION_MAX_COUNT": 5}, now_ts=now
    )
    assert tripped is False


# ───────────────────────── 3. 业务重试指数退避 ─────────────────────────


def test_retry_backoff_seconds_monotonic_and_capped() -> None:
    cfg = {}
    seq = [engine_main.retry_backoff_seconds(cfg, n) for n in range(1, 6)]
    assert seq[0] == 60
    assert seq == sorted(seq)
    assert seq[-1] <= int(cfg.get("EXECUTOR_RETRY_BACKOFF_MAX_SECONDS") or 900)


def test_retry_backoff_custom_base_and_cap() -> None:
    cfg = {"EXECUTOR_RETRY_BACKOFF_SECONDS": 10, "EXECUTOR_RETRY_BACKOFF_MAX_SECONDS": 30}
    assert engine_main.retry_backoff_seconds(cfg, 1) == 10
    assert engine_main.retry_backoff_seconds(cfg, 2) == 20
    assert engine_main.retry_backoff_seconds(cfg, 3) == 30
    assert engine_main.retry_backoff_seconds(cfg, 9) == 30


def test_set_and_expire_retry_backoff() -> None:
    wid = "ccc083-test-backoff"
    engine_main.clear_retry_backoff(wid)
    try:
        assert engine_main.retry_backoff_active(wid, now_ts=1000.0) is False
        engine_main.set_retry_backoff(wid, 120, now_ts=1000.0)
        assert engine_main.retry_backoff_active(wid, now_ts=1000.0 + 60) is True
        # 到期自动清除并放行
        assert engine_main.retry_backoff_active(wid, now_ts=1000.0 + 121) is False
        assert wid not in engine_main._RETRY_BACKOFF_UNTIL
    finally:
        engine_main.clear_retry_backoff(wid)


def test_clear_retry_backoff_on_success_helper() -> None:
    wid = "ccc083-test-clear"
    engine_main.set_retry_backoff(wid, 999, now_ts=time.time())
    engine_main.clear_retry_backoff(wid)
    assert engine_main.retry_backoff_active(wid) is False


# ───────────────────────── 4. 会话探针（worker-events.jsonl kind=session） ─────────────────────────


def _git_init_with_commit(repo: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f.txt").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_session_probe_fields_edit_hit_false_when_clean(tmp_path: Path) -> None:
    repo = tmp_path / "wt"
    repo.mkdir()
    tip = _git_init_with_commit(repo)
    marker = tmp_path / "w1.running"
    marker.write_text(f"dispatch_tip={tip}\n", encoding="utf-8")
    engine_main._append_session_probe(
        tmp_path,
        work_id="w1",
        phase="run",
        lifetime_s=12.5,
        short_threshold_s=300,
        worktree_path=str(repo),
        marker_id="w1",
    )
    rec = json.loads((tmp_path / "worker-events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["kind"] == "session"
    assert rec["work_id"] == "w1"
    assert rec["session_lifetime_s"] == 12.5
    assert rec["short_session"] is True
    assert rec["edit_hit"] is False
    assert rec["ts"].endswith("Z")


def test_session_probe_edit_hit_true_on_dirty_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "wt"
    repo.mkdir()
    tip = _git_init_with_commit(repo)
    (repo / "g.txt").write_text("dirty\n", encoding="utf-8")  # 未提交改动
    marker = tmp_path / "w2.running"
    marker.write_text(f"dispatch_tip={tip}\n", encoding="utf-8")
    engine_main._append_session_probe(
        tmp_path,
        work_id="w2",
        phase="run",
        lifetime_s=400.0,
        short_threshold_s=300,
        worktree_path=str(repo),
        marker_id="w2",
    )
    rec = json.loads((tmp_path / "worker-events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["edit_hit"] is True
    assert rec["short_session"] is False  # 400s > 300s 阈值


def test_session_probe_degrades_to_null_without_tip(tmp_path: Path) -> None:
    repo = tmp_path / "wt"
    repo.mkdir()
    _git_init_with_commit(repo)  # 干净但无 dispatch_tip 标记 → 无法判定 → null
    engine_main._append_session_probe(
        tmp_path,
        work_id="w3",
        phase="audit",
        lifetime_s=5.0,
        short_threshold_s=300,
        worktree_path=str(repo),
        marker_id="w3",
    )
    rec = json.loads((tmp_path / "worker-events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["edit_hit"] is None


def test_worker_events_consumer_filter_unaffected(tmp_path: Path) -> None:
    """kind=session 行不得干扰 kind=worker 消费口径（web/server.py 按 kind 过滤）。"""
    metrics.record_worker_event(
        tmp_path, work_id="w9", phase="run", ok=False, returncode=1,
        duration_s=1.0, exit_kind="nonzero", problems=["退出码非 0: 1"],
    )
    engine_main._append_session_probe(
        tmp_path, work_id="w9", phase="run", lifetime_s=1.0,
        short_threshold_s=300, worktree_path=None,
    )
    lines = (tmp_path / "worker-events.jsonl").read_text(encoding="utf-8").splitlines()
    kinds = [json.loads(x)["kind"] for x in lines]
    assert kinds == ["worker", "session"]
    worker_rows = [json.loads(x) for x in lines if json.loads(x)["kind"] == "worker"]
    assert worker_rows[0]["problem"] == "退出码非 0: 1"


# ───────────────────────── 5. bash 层：防旋闸 / 冷却 / DRY-RUN ─────────────────────────


WATCHDOG = SCRIPTS / "watchdog-ccc.sh"
KICKSTART = SCRIPTS / "kickstart-ccc.sh"


def _run_watchdog(home: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "HOME": str(home),
        "CCC_JANITOR_OFF": "1",
        "CCC_WATCHDOG_DRY_RUN": "1",
        "CCC_WATCHDOG_ENGINE_PNAME": "ccc083-no-such-proc-xyz",
        "CCC_WATCHDOG_WEB_PNAME": "ccc083-no-such-proc-xyz-web",
    }
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(WATCHDOG)], capture_output=True, text=True, timeout=120, env=env
    )


def _wd_log(home: Path) -> str:
    f = home / ".ccc" / "logs" / "watchdog.log"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def _wd_state(home: Path, svc: str) -> dict[str, str]:
    f = home / ".ccc" / "logs" / "watchdog-state" / f"{svc}.state"
    out: dict[str, str] = {}
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
    return out


@pytest.mark.parametrize("script", [WATCHDOG, KICKSTART])
def test_shell_scripts_syntax_ok(script: Path) -> None:
    res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_watchdog_first_fault_observes_without_kick(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    res = _run_watchdog(home)
    assert res.returncode == 0
    log = _wd_log(home)
    assert "发现故障 [Engine: 进程不存在]" in log
    assert "观察一轮不动手" in log
    assert "自愈成功" not in log and "[DRY-RUN] 将触发" not in log
    assert _wd_state(home, "engine").get("streak") == "1"


def test_watchdog_second_fault_kicks_dryrun_then_cooldown_blocks(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _run_watchdog(home)  # streak=1 观察
    res2 = _run_watchdog(home)  # streak=2 → DRY-RUN 触发
    assert res2.returncode == 0
    log = _wd_log(home)
    assert "[DRY-RUN] 将触发 kickstart --engine-only" in log
    st = _wd_state(home, "engine")
    assert st.get("streak") == "0" and int(st.get("last_kick") or 0) > 0
    # 第三轮：冷却期内只观测不动手
    _run_watchdog(home)
    log3 = _wd_log(home)
    assert "自愈冷却中" in log3
    assert log3.count("[DRY-RUN] 将触发 kickstart --engine-only") == 1


def test_watchdog_zero_cooldown_allows_repeat_kick(tmp_path: Path) -> None:
    """冷却=0 时不受间隔拦截，但「连续两次确认」仍然独立生效（每两轮可触发一次）。"""
    home = tmp_path / "home"
    home.mkdir()
    env = {"CCC_WATCHDOG_KICKSTART_COOLDOWN": "0"}
    for _ in range(5):
        _run_watchdog(home, env)
    # 轮次: 1观察 2触发 3观察 4触发 5观察 → 至少 2 次意图记录
    assert _wd_log(home).count("[DRY-RUN] 将触发 kickstart --engine-only") >= 2


def test_watchdog_flap_alert_file_written_at_streak(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {"CCC_WATCHDOG_MIN_FAULT_STREAK": "99", "CCC_WATCHDOG_FLAP_ALERT_STREAK": "3"}
    for _ in range(3):
        _run_watchdog(home, env)
    alert = home / ".ccc" / "logs" / "alerts" / "watchdog-flap-engine.alert"
    assert alert.is_file()
    assert "需人工介入" in alert.read_text(encoding="utf-8")


def test_watchdog_healthy_resets_streak(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    _run_watchdog(home)  # streak=1
    assert _wd_state(home, "engine").get("streak") == "1"
    # 心跳源：预置新鲜 slot metrics（watchdog 优先读它判心跳）
    exec_dir = home / ".ccc" / "logs" / "exec"
    exec_dir.mkdir(parents=True, exist_ok=True)
    (exec_dir / "engine-metrics.jsonl").write_text("", encoding="utf-8")
    # 起一个可被 pgrep 匹配的假进程，让两个服务都「存活」
    fake = subprocess.Popen(["sleep", "300"])
    try:
        res = _run_watchdog(home, {
            "CCC_WATCHDOG_ENGINE_PNAME": "sleep 300",
            "CCC_WATCHDOG_WEB_PNAME": "sleep 300",
        })
        assert res.returncode == 0
        # 全健康路径：引擎连击清零（web 的 HTTP 探测结果不影响 engine 状态断言）
        assert _wd_state(home, "engine").get("streak") == "0"
    finally:
        fake.kill()


def test_kickstart_dry_run_and_min_interval(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "CCC_KICKSTART_DRY_RUN": "1",
    }
    args = ["bash", str(KICKSTART), "--engine-only"]
    r1 = subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)
    assert r1.returncode == 0
    assert "[DRY-RUN]" in r1.stderr
    klog = (home / ".ccc" / "logs" / "watchdog.log").read_text(encoding="utf-8")
    assert "[DRY-RUN] 热重启意图: com.ccc.engine" in klog
    assert "热重启成功" not in klog  # DRY-RUN 绝不产生真实重启记录
    state = (home / ".ccc" / "logs" / "kickstart-state" / "com.ccc.engine.last")
    assert state.is_file() and state.read_text().strip().isdigit()
    # 冷却：默认间隔内第二次调用跳过（仍 exit 0 幂等安全侧）
    r2 = subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)
    assert r2.returncode == 0
    assert "冷却跳过" not in r2.stderr  # dry-run 分支不走冷却拦截，直接再记意图
    klog2 = (home / ".ccc" / "logs" / "watchdog.log").read_text(encoding="utf-8")
    assert klog2.strip().splitlines()[-1].endswith("com.ccc.engine")


def test_kickstart_min_interval_blocks_real_call(tmp_path: Path) -> None:
    """非 dry-run 下，间隔内的第二次重启被冷却拦截且不触 launchctl（用 FORCE 对照）。"""
    home = tmp_path / "home"
    home.mkdir()
    base_env = {
        **os.environ,
        "HOME": str(home),
        "CCC_KICKSTART_STATE_DIR": str(tmp_path / "kickstate"),
    }
    # 预置「刚刚重启过」状态
    state_dir = tmp_path / "kickstate"
    state_dir.mkdir(parents=True)
    (state_dir / "com.ccc.engine.last").write_text(f"{int(time.time())}\n", encoding="utf-8")
    env_block = {**base_env, "CCC_KICKSTART_MIN_INTERVAL": "300"}
    r = subprocess.run(
        ["bash", str(KICKSTART), "--engine-only"],
        capture_output=True, text=True, env=env_block, timeout=60,
    )
    assert r.returncode == 0
    assert "冷却跳过" in r.stderr
    klog = (home / ".ccc" / "logs" / "watchdog.log").read_text(encoding="utf-8")
    assert "热重启成功" not in klog  # 未执行任何 launchctl 动作
