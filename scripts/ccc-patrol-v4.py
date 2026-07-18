#!/usr/bin/env python3
"""ccc-patrol-v4.py — CCC Auto-Patrol 全 workspace 巡检

**定位**：独立运维探针（非 Engine 流水线核心）。
Hub 运维页可聚合 `~/.ccc/patrol-state.json`；勿与 product/dev/reviewer 角色混为一谈。
见 docs/architecture-core.md。

在全 workspace 检查 Engine 存活、看板异常、卡死任务。
v4 新增：
- Step 0: Engine 存活检测（最优先，Engine 死了不做后续）
- 5 workspace 统一巡检：CCC / qxo / xianyu / qb / qx
- 异常三步法：读 note → 查 verdict → 分类处理
- 活跃任务 5min 卡死检测
- 状态持久化（~/.ccc/patrol-state.json），保留最近 6 轮

红线：
- 不动 qx 源码（projects/qx 只读不改）
- 不杀运行中的 opencode
- 不改 .env
- H7: heartbeat/loop 卡死且 PID 仍存活时允许 kill+restart Engine
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from _executor import _sanitized_env

try:
    from _ccc_control import is_disabled as _ctrl_disabled
    from _ccc_control import may_start_engine as _ctrl_may_start
except ImportError:  # pragma: no cover
    def _ctrl_disabled() -> bool:
        return (Path.home() / ".ccc" / "DISABLED").is_file()

    def _ctrl_may_start() -> bool:
        return not _ctrl_disabled()

# ── 常量 ──
HOME = Path.home()
CCC_HOME = HOME / "program" / "CCC"
ENGINE_SCRIPT = CCC_HOME / "scripts" / "ccc-engine.py"
ENGINE_PLIST = HOME / "Library" / "LaunchAgents" / "com.ccc.engine.plist"
PATROL_STATE_FILE = HOME / ".ccc" / "patrol-state.json"
RESTART_LOG = HOME / ".ccc" / "logs" / "engine-restarts.jsonl"
MAX_ROUNDS = 6

# 注意：qx 对应 ~/program/projects/qx（不是 ~/program/qx）
WORKSPACES: dict[str, Path] = {
    "CCC": HOME / "program" / "CCC",
    "qxo": HOME / "program" / "qx-observer",
    "xianyu": HOME / "program" / "xianyu",
    "qb": HOME / "program" / "projects" / "qb",
    "qx": HOME / "program" / "projects" / "qx",
}
READ_ONLY_WS = {"qx"}  # qx 只读不改

HB_STALE_SECONDS = 300  # 心跳 > 300s → stale
STUCK_THRESHOLD = 300  # in_progress 卡死阈值（秒）
FORCE_MV_THRESHOLD = 1800  # 强制移回 planned 阈值（秒）
PID_DIR = HOME / ".ccc" / "opencode-pids"

BOARD_COLS = [
    "backlog",
    "planned",
    "in_progress",
    "testing",
    "verified",
    "released",
    "abnormal",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_ts() -> int:
    return int(time.time())


# ── 辅助工具 ──


def json_load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def jsonl_load(path: Path) -> dict | None:
    """读单行 JSONL 文件"""
    try:
        line = path.read_text().strip()
        if line:
            return json.loads(line.split("\n")[0])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def list_board_tasks(ws: Path, col: str) -> list[dict]:
    """列出某列所有 task JSONL"""
    tasks = []
    d = ws / ".ccc" / "board" / col
    if not d.is_dir():
        return tasks
    for f in sorted(d.iterdir()):
        if f.suffix == ".jsonl" or f.suffix == ".json":
            t = jsonl_load(f)
            if t:
                tasks.append(t)
    return tasks


def _sync_board_index(ws: Path) -> None:
    """同步 workspace 的 .ccc/board/index.json（让 patrol 报告和消费者读到最新数据）

    在 patrol 完成 board 操作后、commit 前调用一次，确保 git 提交包含 index 更新。
    同步失败时静默跳过，不阻塞 patrol 主流程。
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from _board_store import FileBoardStore

        FileBoardStore(ws).update_index()
    except (OSError, RuntimeError, ValueError, ImportError):
        pass


def read_board_index(ws: Path) -> dict[str, int]:
    """直接遍历目录统计，避开 stale index.json"""
    counts = {}
    for c in BOARD_COLS:
        d = ws / ".ccc" / "board" / c
        if d.is_dir():
            counts[c] = len([f for f in d.iterdir() if f.suffix in (".jsonl", ".json")])
        else:
            counts[c] = 0
    return counts


def verify_board_index(ws: Path) -> list[str]:
    """验证 workspace 的 index.json 与 board 目录一致性，自动修复。

    Args:
        ws: workspace 根路径

    Returns:
        操作描述列表：不一致时返回修复摘要，一致时返回 []
    """
    repairs = []
    board_path = ws / ".ccc" / "board"
    if not board_path.is_dir():
        return repairs

    try:
        index_path = board_path / "index.json"
        if not index_path.exists():
            return repairs

        idx_data = json_load(index_path)
        if not isinstance(idx_data, dict):
            idx_data = {}

        for c in BOARD_COLS:
            actual = read_board_index(ws).get(c, 0)
            idx = idx_data.get(c, 0)
            if actual != idx:
                diffs = []
                if actual != 0:
                    diffs.append(f"{c}(实际={actual})")
                if idx != 0:
                    diffs.append(f"{c}(idx={idx})")
                warning = f"{ws.name}:index 不一致 {','.join(diffs)}"
                repairs.append(warning)
                print(f"[patrol] {warning}", file=sys.stderr)

        if repairs:
            print(
                f"[patrol] {ws.name}: 正在同步 index.json 修复不一致", file=sys.stderr
            )
            _sync_board_index(ws)
            repairs.append(f"{ws.name}:index 已修复 ({len(repairs)}列不一致)")
            print(f"[patrol] {ws.name}:index 同步修复完成", file=sys.stderr)
    except Exception as exc:
        print(
            f"[patrol] 验证 workspace {ws.name} 的 index 健全性失败: {exc}",
            file=sys.stderr,
        )
        repair = f"[验证失败]{ws.name}: {exc}"
        repairs.append(repair)

    return repairs
    return counts


def file_age_seconds(path: Path) -> int | None:
    """文件最后修改距现在的秒数"""
    try:
        return now_ts() - int(path.stat().st_mtime)
    except OSError:
        return None


# ── Step 0: Engine 存活检测 ──


def engine_is_running() -> bool:
    """检查 ccc-engine.py 进程是否存活"""
    try:
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_sanitized_env(),
        )
        for line in r.stdout.splitlines():
            if "ccc-engine.py" in line and "grep" not in line:
                return True
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


def check_heartbeat(ws: Path) -> tuple[str, dict]:
    """返回 (status, hb_dict) — status: 'fresh' | 'stale' | 'missing'"""
    hb_file = ws / ".ccc" / "engine-heartbeat.json"
    if not hb_file.exists():
        return "missing", {}
    hb = json_load(hb_file)
    if not hb:
        return "missing", {}
    ts_str = hb.get("timestamp", "")
    if not ts_str:
        return "missing", hb
    try:
        if ts_str.endswith("Z"):
            hb_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        elif "+" in ts_str:
            hb_ts = datetime.fromisoformat(ts_str)
        else:
            hb_ts = datetime.fromisoformat(ts_str + "+00:00")
        age = (datetime.now(timezone.utc) - hb_ts).total_seconds()
        if age > HB_STALE_SECONDS:
            return "stale", hb
        return "fresh", hb
    except (ValueError, TypeError):
        return "missing", hb


def _ccc_disabled() -> bool:
    """v0.39: 控制面 disabled → 禁止一切自动拉起。"""
    return _ctrl_disabled()


def ensure_engine_healthy(*, allow_restart: bool = True) -> str:
    """Step 0: 确保 Engine 存活。

    v0.39 业务规则：
    - disabled → DISABLED（不拉起）
    - allow_restart=False → 只观察
    - 允许重启时：仅经 launchd 单点拉起（禁止 Popen 旁路）
    """
    if _ccc_disabled() or not _ctrl_may_start():
        print(
            "[patrol] CCC control=disabled — skip engine restart",
            file=sys.stderr,
        )
        return "DISABLED"

    alive = engine_is_running()
    if alive:
        hb_status, hb = check_heartbeat(CCC_HOME)
        loop_stale = _loop_heartbeat_stale()
        if hb_status == "stale" or loop_stale:
            print(
                f"[patrol] heartbeat stale "
                f"(ws={hb.get('timestamp', '?')}, loop_stale={loop_stale}) "
                f"and PID alive — kill+restart (H7)",
                file=sys.stderr,
            )
            if not allow_restart:
                return "STALE"
            _try_kill_engine()
            time.sleep(2)
            if _try_start_engine():
                return "RESTARTED"
            return "DEAD"
        return "OK"

    if not allow_restart:
        print("[patrol] Engine down — restart disabled (--no-restart)", file=sys.stderr)
        return "DOWN"

    if _try_start_engine():
        return "RESTARTED"
    return "DEAD"


def _loop_heartbeat_stale() -> bool:
    """~/.ccc/engine-loop-heartbeat.json 超过 HB_STALE_SECONDS 视为卡死。"""
    p = Path.home() / ".ccc" / "engine-loop-heartbeat.json"
    if not p.is_file():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ts_str = data.get("timestamp") or ""
        if not ts_str:
            return False
        if ts_str.endswith("Z"):
            hb_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            hb_ts = datetime.fromisoformat(ts_str)
        age = (datetime.now(timezone.utc) - hb_ts).total_seconds()
        return age > HB_STALE_SECONDS
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _try_kill_engine() -> None:
    """尝试优雅 + 强制杀 Engine（经 launchd kickstart -k 优先）。"""
    uid = os.getuid()
    gui = f"gui/{uid}"
    try:
        subprocess.run(
            ["launchctl", "kill", "SIGTERM", f"{gui}/com.ccc.engine"],
            capture_output=True,
            timeout=10,
            env=_sanitized_env(),
        )
    except OSError:
        pass
    time.sleep(1)
    try:
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_sanitized_env(),
        )
        for line in r.stdout.splitlines():
            if "ccc-engine.py" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    try:
                        subprocess.run(["kill", "-9", pid], timeout=5, env=_sanitized_env())
                    except OSError:
                        pass
    except (subprocess.TimeoutExpired, OSError):
        pass
    try:
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"{gui}/com.ccc.engine"],
            capture_output=True,
            timeout=15,
            env=_sanitized_env(),
        )
    except OSError:
        pass


def _try_start_engine() -> bool:
    """仅经 launchd 单点拉起 Engine（v0.39 禁止 Popen 旁路）。

    旧版方式 3（python3 后台 Popen）是双 engine / 杀不掉的根因之一，已删除。
    """
    if not _ctrl_may_start():
        return False

    uid = os.getuid()
    gui = f"gui/{uid}"

    if not ENGINE_PLIST.exists():
        print(
            f"[patrol] engine plist missing: {ENGINE_PLIST} — refuse Popen fallback",
            file=sys.stderr,
        )
        return False

    # 方式 1: launchctl bootstrap
    try:
        r = subprocess.run(
            ["launchctl", "bootstrap", gui, str(ENGINE_PLIST)],
            capture_output=True,
            timeout=15,
            env=_sanitized_env(),
        )
        if r.returncode == 0:
            time.sleep(3)
            if engine_is_running():
                return True
    except OSError:
        pass

    # 方式 2: launchctl load（旧接口兜底）
    try:
        subprocess.run(
            ["launchctl", "load", "-w", str(ENGINE_PLIST)],
            capture_output=True,
            timeout=15,
            env=_sanitized_env(),
        )
        time.sleep(3)
        if engine_is_running():
            return True
    except OSError:
        pass

    # 禁止方式 3: Popen(python ccc-engine.py) — 与 KeepAlive 形成双进程
    print(
        "[patrol] launchd start failed — NOT falling back to Popen (v0.39 policy)",
        file=sys.stderr,
    )
    return False


# ── Step 1: 扫描 5 workspace ──


def scan_all_ws(ws_list: dict[str, Path]) -> dict[str, dict]:
    """返回 {ws_name: {col: count}}"""
    result = {}
    for name, path in ws_list.items():
        if path.is_dir():
            result[name] = read_board_index(path)
        else:
            result[name] = {c: -1 for c in BOARD_COLS}
    return result


# ── Step 2: 异常排查（三步法）──


def triage_abnormal(ws_name: str, ws: Path) -> list[str]:
    """三步法排查异常任务。返回执行的操作列表。"""
    if ws_name in READ_ONLY_WS:
        return ["skip (read-only)"]

    ops: list[str] = []
    abnormal_dir = ws / ".ccc" / "board" / "abnormal"
    if not abnormal_dir.is_dir():
        return ops

    verdict_dir = ws / ".ccc" / "verdicts"
    report_dir = ws / ".ccc" / "reports"
    plan_dir = ws / ".ccc" / "plans"

    for f in sorted(abnormal_dir.iterdir()):
        if f.suffix not in (".jsonl", ".json"):
            continue
        task = jsonl_load(f)
        if not task:
            continue
        tid = task.get("id", f.stem)
        note = task.get("note", "")
        updated = task.get("updated_at", "")

        # Step 2.1: 读 note/updated_at
        # Step 2.2: 查 verdict/report/plan 判断真失败
        verdict_file = verdict_dir / f"{tid}.verdict.md"
        report_file = report_dir / f"{tid}.report.md"
        plan_file = plan_dir / f"{tid}.plan.md"

        has_verdict = verdict_file.is_file() and verdict_file.read_text().strip()
        has_report = report_file.is_file() and report_file.read_text().strip()
        has_plan = plan_file.is_file() and plan_file.read_text().strip()
        has_fix = has_verdict or has_report  # 有产出说明问题已修

        # Step 2.3: 分类
        # 已修复（有 verdict/report）→ released
        # 可重试（无产出但有 plan 且不是反复失败）→ planned
        # 不确定 → backlog
        # 反复失败（note 里含 multiple retries）→ abnormal 保留

        retry_count = note.count("重试") + note.count("retry")
        is_persistent = (
            retry_count >= 3 or "连续失败" in note or "all_failed_or_skipped" in note
        )

        if has_fix and not is_persistent:
            # 已修复 → testing（需 reviewer/tester 验收，不跳过看板门禁）
            _move_task(ws, tid, "abnormal", "testing")
            ops.append(f"{tid}: has verdict/report → testing (await review)")
        elif has_plan and not is_persistent:
            # 有 plan，非反复失败 → planned（重新调度）
            _move_task(ws, tid, "abnormal", "planned")
            ops.append(f"{tid}: has plan → planned (retry)")
        elif is_persistent:
            # 反复失败 → 保留 abnormal
            ops.append(f"{tid}: persistent failure (keep abnormal)")
        else:
            # 不确定 → backlog
            _move_task(ws, tid, "abnormal", "backlog")
            ops.append(f"{tid}: no verdict/plan → backlog")

    return ops


def cleanup_zombie_opencode_pids() -> list[str]:
    """全量扫描 ~/.ccc/opencode-pids/，检测并清理 zombie opencode 进程。

    对每个 .pid 文件：
    1. 读 PID
    2. _is_zombie_pid(pid) 检查是否为 Z 状态
    3. 是 → 先 kill -TERM, sleep 1, 仍存活则 kill -KILL
    4. 清理 pid 文件（无论 kill 是否成功，文件都可能残留）

    Returns:
        操作描述列表，每项如 "zombie:{phase_id}(pid=12345) → killed+cleaned"
    """
    ops: list[str] = []
    if not PID_DIR.is_dir():
        return ops
    try:
        pid_files = list(PID_DIR.glob("*.pid"))
    except OSError:
        return ops
    for pid_file in pid_files:
        try:
            pid_str = pid_file.read_text().strip()
            pid = int(pid_str)
            phase_id = pid_file.stem
        except (OSError, ValueError):
            continue
        if not _is_zombie_pid(pid):
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        except (OSError, ProcessLookupError):
            pass
        except ValueError:
            pass
        try:
            pid_file.unlink()
        except OSError:
            pass
        ops.append(f"zombie:{phase_id}(pid={pid}) → killed+cleaned")
    return ops


def _move_task(ws: Path, tid: str, src: str, dst: str) -> bool:
    """通过 FileBoardStore 在 board 列间移动 task，确保 index.json 同步（R2）"""
    try:
        # 先更新 note（读 src 文件改后写回）
        src_file = ws / ".ccc" / "board" / src / f"{tid}.jsonl"
        alt_src = ws / ".ccc" / "board" / src / f"{tid}.json"
        src_path = src_file if src_file.exists() else alt_src
        if src_path.exists():
            task = json_load(src_path)
            if task:
                task["note"] = f"patrol-v4: {src} → {dst} (auto)"
                task["updated_at"] = now_iso()
                src_path.write_text(json.dumps(task, ensure_ascii=False) + "\n")

        sys.path.insert(0, str(CCC_HOME / "scripts"))
        from _board_store import FileBoardStore

        store = FileBoardStore(ws)
        ok = store.move_task(tid, src, dst)
        store.update_index()
        return ok
    except Exception as exc:
        print(f"[patrol] _move_task({tid}, {src}→{dst}) 失败: {exc}", file=sys.stderr)
        return False


def _is_zombie_pid(pid: int) -> bool:
    try:
        r = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
            env=_sanitized_env(),
        )
        if r.returncode != 0:
            return False
        state = r.stdout.strip()
        return state.startswith("Z")
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return False


def _detect_crash_loop(tid: str) -> bool:
    if not PID_DIR.is_dir():
        return False
    stale_count = 0
    for pid_file in PID_DIR.iterdir():
        if tid in pid_file.name:
            try:
                pid_str = pid_file.read_text().strip()
                pid = int(pid_str)
                try:
                    os.kill(pid, 0)
                    if _is_zombie_pid(pid):
                        stale_count += 1
                except (OSError, ProcessLookupError):
                    stale_count += 1
            except (ValueError, OSError):
                stale_count += 1
    return stale_count >= 2


def _load_stuck_counters() -> dict[str, int]:
    if not PATROL_STATE_FILE.exists():
        return {}
    try:
        state = json.loads(PATROL_STATE_FILE.read_text())
        return state.get("stuck_tasks", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _save_stuck_counters(counters: dict[str, int]) -> None:
    try:
        state: dict = {"rounds": []}
        if PATROL_STATE_FILE.exists():
            try:
                state = json.loads(PATROL_STATE_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                state = {"rounds": []}
        state["stuck_tasks"] = counters
        PATROL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PATROL_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ── Step 3: 活跃任务卡死检测 ──


def check_stuck_tasks(
    ws_name: str, ws: Path, stuck_counters: dict[str, int] | None = None
) -> tuple[list[str], dict[str, int]]:
    """检查 in_progress 任务卡死。返回 (操作列表, 更新后的 stuck_counters)。"""
    if stuck_counters is None:
        stuck_counters = {}
    if ws_name in READ_ONLY_WS:
        return ["skip (read-only)"], stuck_counters

    ops: list[str] = []
    ip_dir = ws / ".ccc" / "board" / "in_progress"
    if not ip_dir.is_dir():
        return ops, stuck_counters

    # v0.31: 检测 all-phases-done 但卡在 planned/in_progress 的任务
    for _col in ("planned", "in_progress"):
        _check_done_phases_in_wrong_column(ws, ops, _col)

    # ── 以下为卡死检测逻辑 ──
    for f in sorted(ip_dir.iterdir()):
        if f.suffix not in (".jsonl", ".json"):
            continue
        tid = f.stem
        age = file_age_seconds(f)
        if age is None:
            continue

        # 检查是否有活进程持有此 task_id
        process_alive = False
        is_zombie = False
        if PID_DIR.is_dir():
            for pid_file in PID_DIR.iterdir():
                if tid in pid_file.name:
                    try:
                        pid_str = pid_file.read_text().strip()
                        pid = int(pid_str)
                        os.kill(pid, 0)
                        process_alive = True
                        if _is_zombie_pid(pid):
                            is_zombie = True
                        break
                    except (ValueError, OSError, ProcessLookupError):
                        pass

        if not process_alive:
            try:
                r = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env=_sanitized_env(),
                )
                for line in r.stdout.splitlines():
                    if tid in line and "grep" not in line:
                        process_alive = True
                        break
            except (subprocess.TimeoutExpired, OSError):
                pass

        stuck_count = stuck_counters.get(tid, 0)
        target: str | None = None

        if age > FORCE_MV_THRESHOLD:
            if is_zombie or stuck_count >= 3:
                target = "backlog"
            else:
                target = "planned"
            ops.append(f"{tid}: stuck {age}s > {FORCE_MV_THRESHOLD}s → {target}")
        elif age > STUCK_THRESHOLD and not process_alive:
            if stuck_count >= 3:
                target = "backlog"
            else:
                target = "planned"
            ops.append(f"{tid}: stuck {age}s, no process → {target}")
        elif age > STUCK_THRESHOLD and process_alive:
            ops.append(f"{tid}: running {age}s (alive, no action)")

        if target:
            _move_task(ws, tid, "in_progress", target)
            stuck_count += 1
            stuck_counters[tid] = stuck_count

    return ops, stuck_counters


def _check_done_phases_in_wrong_column(ws: Path, ops: list[str], col: str) -> None:
    """检测 all-phases-done 但卡在 planned/in_progress 的任务 → 移到 testing"""
    import json as _json

    col_dir = ws / ".ccc" / "board" / col
    if not col_dir.is_dir():
        return
    phases_dir = ws / ".ccc" / "phases"
    if not phases_dir.is_dir():
        return
    for f in sorted(col_dir.iterdir()):
        if f.suffix not in (".jsonl", ".json"):
            continue
        tid2 = f.stem
        pf = phases_dir / f"{tid2}.phases.json"
        if not pf.exists():
            continue
        try:
            lines = pf.read_text().strip().split("\n")
            all_done = True
            has_done = False
            for pl in lines:
                pl = pl.strip()
                if not pl or not pl.startswith("{"):
                    continue
                try:
                    po = _json.loads(pl)
                except _json.JSONDecodeError:
                    continue
                if "schema_version" in po or "engine_iter" in po:
                    continue
                if po.get("phase") and po.get("status") != "done":
                    all_done = False
                    break
                if po.get("status") == "done":
                    has_done = True
            if all_done and has_done:
                _move_task(ws, tid2, col, "testing")
                ops.append(f"{tid2}: all phases done but in {col} → testing")
        except Exception:
            continue


def save_patrol_state(
    ws_stats: dict[str, dict],
    engine_status: str,
    fix_ops: list[str],
    stuck_count: int,
    warn: str,
) -> None:
    """持久化一轮 patrol 状态，保留最多 MAX_ROUNDS 轮"""
    state: dict = {"rounds": []}
    if PATROL_STATE_FILE.exists():
        try:
            state = json.loads(PATROL_STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            state = {"rounds": []}

    pack = {
        "ts": now_iso(),
        "engine": engine_status,
        "ws": {},
    }
    for name, counts in ws_stats.items():
        pack["ws"][name] = {
            "planned": counts.get("planned", 0),
            "in_progress": counts.get("in_progress", 0),
            "testing": counts.get("testing", 0),
            "released": counts.get("released", 0),
            "abnormal": counts.get("abnormal", 0),
        }

    if fix_ops:
        pack["fix"] = fix_ops
    if stuck_count > 0:
        pack["stuck"] = stuck_count
    if warn:
        pack["warn"] = warn

    state.setdefault("rounds", []).append(pack)
    # 只保留最后 MAX_ROUNDS 轮
    if len(state["rounds"]) > MAX_ROUNDS:
        state["rounds"] = state["rounds"][-MAX_ROUNDS:]

    PATROL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PATROL_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False) + "\n")


def detect_stagnation(ws_stats: dict[str, dict]) -> str:
    """检查是否连续 6 轮无变化"""
    if not PATROL_STATE_FILE.exists():
        return ""
    try:
        state = json.loads(PATROL_STATE_FILE.read_text())
        rounds = state.get("rounds", [])
        if len(rounds) < 6:
            return ""
        last_6 = rounds[-6:]

        def to_key(ws_data: dict[str, int]) -> str:
            return json.dumps(ws_data, sort_keys=True)

        first_key = {name: to_key(last_6[0]["ws"].get(name, {})) for name in ws_stats}
        stagnant = True
        for r in last_6[1:]:
            for name in ws_stats:
                if to_key(r["ws"].get(name, {})) != first_key.get(name, ""):
                    stagnant = False
                    break
            if not stagnant:
                break

        if stagnant:
            return "连续6轮无变化"
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return ""


# ── Step 5: 修复后 commit ──


def commit_patrol_fix(ws_path: Path, ops: list[str], engine_action: str) -> None:
    """在 workspace 执行 git commit（仅 qx 跳过）"""
    # 按名称查找
    ws_name = None
    for name, path in WORKSPACES.items():
        if path.resolve() == ws_path.resolve():
            ws_name = name
            break
    if ws_name in READ_ONLY_WS:
        return

    if not ops and engine_action == "OK":
        return
    if not ops and engine_action == "":
        return

    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ws_path,
            capture_output=True,
            timeout=5,
            env=_sanitized_env(),
        )
        if r.returncode != 0:
            return
    except OSError:
        return

    # 同步 index.json（让 commit 包含最新 board 计数）
    _sync_board_index(ws_path)

    # git add
    subprocess.run(["git", "add", "-A"], cwd=ws_path, capture_output=True, timeout=10, env=_sanitized_env())

    # 检查是否有改动
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ws_path,
        capture_output=True,
        text=True,
        timeout=10,
        env=_sanitized_env(),
    )
    if not r.stdout.strip():
        return

    commit_msg = f"chore: patrol-v4 fix {datetime.now().strftime('%Y-%m-%d-%H%M')}"
    if engine_action and engine_action != "OK":
        commit_msg += f" (engine: {engine_action})"
    subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=ws_path,
        capture_output=True,
        timeout=15,
        env=_sanitized_env(),
    )


def _log_engine_restart(status: str, reason: str) -> None:
    """记录 Engine 重启/死亡事件到 JSONL 日志。幂等不抛异常。

    Args:
        status: "RESTARTED"（重启成功）或 "DEAD"（无法重启）
        reason: 描述原因，如 "patrol-v4 detected Engine dead, auto-restarted"
    """
    try:
        RESTART_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": now_iso(),
            "status": status,
            "reason": reason,
        }
        with RESTART_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _notify_engine_restart(status: str) -> None:
    """Engine 重启/死亡时发桌面通知 + webhook。非阻塞，不抛异常。"""
    notify_script = CCC_HOME / "scripts" / "ccc-notify.sh"
    if not notify_script.is_file():
        return
    try:
        if status == "RESTARTED":
            subprocess.Popen(
                [
                    "bash",
                    str(notify_script),
                    "L2",
                    "Engine 自动重启",
                    "Patrol-v4 检测到 Engine 已停止，已自动重启完成",
                ],
                stdout=subprocess.DEVNULL,
                env=_sanitized_env(),
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif status == "DEAD":
            subprocess.Popen(
                [
                    "bash",
                    str(notify_script),
                    "L3",
                    "Engine 重启失败",
                    "Patrol-v4 尝试自动重启 Engine 失败，需人工介入",
                ],
                stdout=subprocess.DEVNULL,
                env=_sanitized_env(),
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError:
        pass

    # v0.32: webhook 通知（无论 RESTARTED 还是 DEAD）
    try:
        from _config import Config
        from _webhook import send_webhook

        cfg = Config()
        if cfg.webhook_url:
            level = "L3" if status == "DEAD" else "L2"
            title = "Engine 自动重启" if status == "RESTARTED" else "Engine 重启失败"
            msg = (
                "Patrol-v4 检测到 Engine 已停止，已自动重启完成"
                if status == "RESTARTED"
                else "Patrol-v4 尝试自动重启 Engine 失败，需人工介入"
            )
            send_webhook(cfg.webhook_url, level, title, msg)
    except Exception:
        pass


def _get_engine_pid() -> int | None:
    """从 ps 输出获取 ccc-engine.py 进程 PID。重启后调用以记录新 PID。"""
    try:
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_sanitized_env(),
        )
        for line in r.stdout.splitlines():
            if "ccc-engine.py" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        pass
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _get_engine_uptime() -> str:
    """从 engine-heartbeat.json 的 timestamp 计算 Engine 运行时长。

    在重启 Engine 前调用，读取旧心跳的时间戳计算 uptime。
    返回人类可读字符串如 "45m12s"，无法获取时返回 "unknown"。
    """
    hb_file = CCC_HOME / ".ccc" / "engine-heartbeat.json"
    if not hb_file.exists():
        return "unknown"
    hb = json_load(hb_file)
    if not hb:
        return "unknown"
    ts_str = hb.get("timestamp", "")
    if not ts_str:
        return "unknown"
    try:
        if ts_str.endswith("Z"):
            hb_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        elif "+" in ts_str:
            hb_ts = datetime.fromisoformat(ts_str)
        else:
            hb_ts = datetime.fromisoformat(ts_str + "+00:00")
        age = datetime.now(timezone.utc) - hb_ts
        total_secs = int(age.total_seconds())
        if total_secs < 60:
            return f"{total_secs}s"
        elif total_secs < 3600:
            return f"{total_secs // 60}m{total_secs % 60}s"
        else:
            h, remainder = divmod(total_secs, 3600)
            return f"{h}h{remainder // 60}m"
    except (ValueError, TypeError):
        return "unknown"


def commit_engine_restart(
    reason: str,
    ws_stats: dict[str, dict] | None = None,
    pid: int | None = None,
    uptime: str = "unknown",
) -> None:
    """Engine 重启后 commit，包含 PID/uptime/看板快照正文"""
    ws_path = CCC_HOME
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ws_path,
            capture_output=True,
            timeout=5,
            env=_sanitized_env(),
        )
        if r.returncode != 0:
            return
    except OSError:
        return

    # 构造 commit body
    body_lines = []
    if pid is not None:
        body_lines.append(f"PID: {pid}")
    body_lines.append(f"Uptime: {uptime} (before restart)")
    if ws_stats:
        parts = []
        for name in sorted(ws_stats.keys()):
            c = ws_stats.get(name, {})
            if isinstance(c, dict):
                parts.append(
                    f"{name}(pl:{c.get('planned', 0)} ip:{c.get('in_progress', 0)} "
                    f"rel:{c.get('released', 0)} ab:{c.get('abnormal', 0)})"
                )
            else:
                parts.append(f"{name}:{c}")
        body_lines.append("Board: " + " ".join(parts))

    commit_msg = f"chore: patrol-v4 engine restart ({reason})"
    if body_lines:
        commit_msg += "\n\n" + "\n".join(body_lines)

    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", commit_msg],
        cwd=ws_path,
        capture_output=True,
        timeout=15,
        env=_sanitized_env(),
    )


# ── Step 6: 一行报告 ──


def format_report(
    ws_stats: dict[str, dict],
    engine_status: str,
    all_fix_ops: list[str],
    all_stuck_ops: list[str],
    warnings: list[str],
) -> str:
    """输出一行报告"""
    parts = []
    for name in sorted(ws_stats.keys()):
        c = ws_stats.get(name, {})
        parts.append(
            f"{name}(pl:{c.get('planned', 0)} ip:{c.get('in_progress', 0)} "
            f"rel:{c.get('released', 0)} ab:{c.get('abnormal', 0)})"
        )
    ws_str = " ".join(parts)

    fix_str = "; ".join(all_fix_ops) if all_fix_ops else "-"
    stuck_total = len(all_stuck_ops)

    warn_str = "; ".join(warnings) if warnings else "0"

    return (
        f"patrol-v4: {ws_str} | engine={engine_status} "
        f"| fix: {fix_str} | stale: {stuck_total} | warn: {warn_str}"
    )


# ── 主流程 ──


def main() -> int:
    start = time.time()
    all_fix_ops: list[str] = []
    all_stuck_ops: list[str] = []
    warnings: list[str] = []
    engine_operated = False
    engine_status = "OK"

    allow_restart = "--no-restart" not in sys.argv
    if _ccc_disabled():
        allow_restart = False

    # ── Step 0: Engine 存活检测 ──
    engine_status = ensure_engine_healthy(allow_restart=allow_restart)
    if engine_status == "DISABLED":
        print("[patrol] CCC DISABLED — observation only")
        return 0
    if engine_status == "DOWN":
        print("[patrol] Engine down (no auto-restart)")
        return 0
    if engine_status in ("DEAD",):
        # Engine 修不好，报告死信后退出（不做后续步骤）
        _log_engine_restart("DEAD", "patrol-v4 failed to restart Engine")
        _notify_engine_restart("DEAD")
        ws_stats = scan_all_ws(WORKSPACES)
        report = format_report(
            ws_stats, engine_status, [], [], ["Engine DEAD — cannot continue"]
        )
        print(report)
        save_patrol_state(ws_stats, engine_status, [], 0, "Engine DEAD")
        return 1

    if engine_status == "RESTARTED":
        engine_operated = True
        engine_pid = _get_engine_pid()  # 重启后 PID
        engine_uptime = _get_engine_uptime()  # 重启前 uptime
        board_snapshot = scan_all_ws(WORKSPACES)  # 重启前看板快照
        _log_engine_restart(
            "RESTARTED", "patrol-v4 detected Engine dead, auto-restarted"
        )
        _notify_engine_restart("RESTARTED")
        commit_engine_restart(
            "restarted by patrol-v4",
            ws_stats=board_snapshot,
            pid=engine_pid,
            uptime=engine_uptime,
        )

    # ── Step 1: 扫描 5 workspace ──
    ws_stats = scan_all_ws(WORKSPACES)

    # ── Step 2: 异常排查（三步法）──
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        ops = triage_abnormal(name, path)
        if ops:
            all_fix_ops.extend([f"{name}:{o}" for o in ops])
            if not name.startswith("skip"):
                engine_operated = True

    # ── Step 3: 活跃任务卡死检测 ──
    stuck_counters: dict[str, int] = _load_stuck_counters()
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        ops, stuck_counters = check_stuck_tasks(name, path, stuck_counters)
        for o in ops:
            if "→ planned" in o or "→ backlog" in o:
                all_stuck_ops.append(f"{name}:{o}")
                all_fix_ops.append(f"{name}:stale-{o}")
                if name not in READ_ONLY_WS:
                    engine_operated = True
            elif "stuck" in o and "no action" not in o:
                all_stuck_ops.append(f"{name}:{o}")
    _save_stuck_counters(stuck_counters)

    # ── Step 3.5: zombie opencode 进程清理 ──
    zombie_ops = cleanup_zombie_opencode_pids()
    if zombie_ops:
        all_fix_ops.extend(zombie_ops)
        engine_operated = True

    # ── Step 4: 状态持久化 ──
    warn = detect_stagnation(ws_stats)
    if warn:
        warnings.append(warn)
        # v0.32: stagnation webhook
        try:
            from _config import Config
            from _webhook import send_webhook

            cfg = Config()
            if cfg.webhook_url:
                send_webhook(
                    cfg.webhook_url,
                    "L2",
                    "Patrol 持续停滞",
                    f"连续 6 轮状态无变化: {warn}",
                )
        except Exception:
            pass
    save_patrol_state(ws_stats, engine_status, all_fix_ops, len(all_stuck_ops), warn)

    # ── Step 4.5: index.json 一致性校验 ──
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        repairs = verify_board_index(path)
        if repairs:
            all_fix_ops.extend(repairs)
            for r in repairs:
                if "不一致" in r:
                    warnings.append(f"{name}:{r}")

    # ── Step 5: 修复后 commit ──
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        ws_ops = [o for o in all_fix_ops if o.startswith(f"{name}:")]
        ws_engine_action = engine_status if name == "CCC" else ""
        commit_patrol_fix(path, ws_ops, ws_engine_action)

    # ── Step 6: 报告 ──
    report = format_report(
        ws_stats, engine_status, all_fix_ops, all_stuck_ops, warnings
    )
    elapsed = time.time() - start
    print(f"{report} | took={elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
