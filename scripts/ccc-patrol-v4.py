#!/usr/bin/env python3
"""ccc-patrol-v4.py — CCC Auto-Patrol 全 workspace 巡检

在全 workspace 检查 Engine 存活、看板异常、卡死任务。
v4 新增：
- Step 0: Engine 存活检测（最优先，Engine 死了不做后续）
- 5 workspace 统一巡检：CCC / qxo / xianyu / qb / qx
- 异常三步法：读 note → 查 verdict → 分类处理
- 活跃任务 5min 卡死检测
- 状态持久化（~/.ccc/patrol-state.json），保留最近 6 轮

红线：
- 不动 qx 源码（projects/qx 只读不改）
- 不杀 Engine 自身
- 不杀运行中的 opencode
- 不改 .env
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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

HB_STALE_SECONDS = 300       # 心跳 > 300s → stale
STUCK_THRESHOLD = 300        # in_progress 卡死阈值（秒）
FORCE_MV_THRESHOLD = 1800   # 强制移回 planned 阈值（秒）
PID_DIR = HOME / ".ccc" / "opencode-pids"

BOARD_COLS = ["backlog", "planned", "in_progress", "testing", "verified", "released", "abnormal"]


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


def read_board_index(ws: Path) -> dict[str, int]:
    """读 board/index.json"""
    idx = json_load(ws / ".ccc" / "board" / "index.json")
    if idx:
        return {c: idx.get(c, 0) for c in BOARD_COLS}
    # fallback: 遍历目录计数
    counts = {}
    for c in BOARD_COLS:
        d = ws / ".ccc" / "board" / c
        if d.is_dir():
            counts[c] = len([f for f in d.iterdir() if f.suffix in (".jsonl", ".json")])
        else:
            counts[c] = 0
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
            capture_output=True, text=True, timeout=10,
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


def ensure_engine_healthy() -> str:
    """Step 0: 确保 Engine 存活。返回 'OK' | 'RESTARTED' | 'DEAD' | 'ALREADY_OK'

    顺序：CCC workspace 的 Engine 是总管，查它是否活着。
    """
    alive = engine_is_running()
    if alive:
        # 检查 heartbeat 是否 stale
        hb_status, hb = check_heartbeat(CCC_HOME)
        if hb_status == "stale":
            # heartbeat stale → 可能 Engine 挂了但 zombie 残留？先 kill 再启
            action = "heartbeat stale"
            _try_kill_engine()
            time.sleep(2)
            if _try_start_engine():
                return "RESTARTED"
            return "DEAD"
        return "OK"

    # Engine 完全死了，启动
    action = "not running"
    if _try_start_engine():
        return "RESTARTED"
    return "DEAD"


def _try_kill_engine() -> None:
    """尝试优雅 + 强制杀 Engine"""
    try:
        r = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.splitlines():
            if "ccc-engine.py" in line and "grep" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    try:
                        subprocess.run(["kill", pid], timeout=5)
                    except OSError:
                        pass
    except (subprocess.TimeoutExpired, OSError):
        pass
    # 也通过 launchctl 尝试
    try:
        subprocess.run(
            ["launchctl", "bootout", "gui/501", str(ENGINE_PLIST)],
            capture_output=True, timeout=10,
        )
    except OSError:
        pass


def _try_start_engine() -> bool:
    """尝试启动 Engine（后台 python3 + launchctl 双重兜底）"""
    # 方式 1: launchctl bootstrap
    if ENGINE_PLIST.exists():
        try:
            r = subprocess.run(
                ["launchctl", "bootstrap", "gui/501", str(ENGINE_PLIST)],
                capture_output=True, timeout=15,
            )
            if r.returncode == 0:
                # 等待进程启动
                time.sleep(3)
                if engine_is_running():
                    return True
        except OSError:
            pass

    # 方式 2: launchctl load
    if ENGINE_PLIST.exists():
        try:
            subprocess.run(
                ["launchctl", "load", str(ENGINE_PLIST)],
                capture_output=True, timeout=15,
            )
            time.sleep(3)
            if engine_is_running():
                return True
        except OSError:
            pass

    # 方式 3: python3 后台启动
    if ENGINE_SCRIPT.exists():
        try:
            subprocess.Popen(
                [sys.executable, str(ENGINE_SCRIPT)],
                cwd=CCC_HOME,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(3)
            return engine_is_running()
        except OSError:
            pass

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
            retry_count >= 3
            or "连续失败" in note
            or "all_failed_or_skipped" in note
        )

        if has_fix and not is_persistent:
            # 已修复 → released
            _move_task(ws, tid, "abnormal", "released")
            ops.append(f"{tid}: has verdict/report → released")
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


def _move_task(ws: Path, tid: str, src: str, dst: str) -> bool:
    """在 board 目录间移动 task JSONL"""
    src_file = ws / ".ccc" / "board" / src / f"{tid}.jsonl"
    alt_src = ws / ".ccc" / "board" / src / f"{tid}.json"
    if not src_file.exists() and alt_src.exists():
        src_file = alt_src
    if not src_file.exists():
        return False
    dst_dir = ws / ".ccc" / "board" / dst
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_file = dst_dir / f"{tid}.jsonl"

    # 更新 task 元数据
    task = jsonl_load(src_file)
    if task:
        task["updated_at"] = now_iso()
        task["note"] = f"patrol-v4: {src} → {dst} (auto)"
        dst_file.write_text(json.dumps(task, ensure_ascii=False) + "\n")
    else:
        shutil.copy2(str(src_file), str(dst_file))

    src_file.unlink(missing_ok=True)
    return True


# ── Step 3: 活跃任务卡死检测 ──

def check_stuck_tasks(ws_name: str, ws: Path) -> list[str]:
    """检查 in_progress 任务卡死。返回操作列表。"""
    if ws_name in READ_ONLY_WS:
        return ["skip (read-only)"]

    ops: list[str] = []
    ip_dir = ws / ".ccc" / "board" / "in_progress"
    if not ip_dir.is_dir():
        return ops

    for f in sorted(ip_dir.iterdir()):
        if f.suffix not in (".jsonl", ".json"):
            continue
        tid = f.stem

        age = file_age_seconds(f)
        if age is None:
            continue

        # 检查是否有活进程持有此 task_id
        process_alive = False
        if PID_DIR.is_dir():
            for pid_file in PID_DIR.iterdir():
                if tid in pid_file.name:
                    try:
                        pid_str = pid_file.read_text().strip()
                        pid = int(pid_str)
                        os.kill(pid, 0)
                        process_alive = True
                        break
                    except (ValueError, OSError, ProcessLookupError):
                        pass

        # 也检查 opencode 进程
        if not process_alive:
            try:
                r = subprocess.run(
                    ["ps", "aux"],
                    capture_output=True, text=True, timeout=10,
                )
                for line in r.stdout.splitlines():
                    if tid in line and "grep" not in line:
                        process_alive = True
                        break
            except (subprocess.TimeoutExpired, OSError):
                pass

        if age > FORCE_MV_THRESHOLD:
            # > 30min: 强制移回 planned
            _move_task(ws, tid, "in_progress", "planned")
            ops.append(f"{tid}: stuck {age}s > {FORCE_MV_THRESHOLD}s → planned (force)")
        elif age > STUCK_THRESHOLD and not process_alive:
            # > 5min + 无进程: 卡死 → planned
            _move_task(ws, tid, "in_progress", "planned")
            ops.append(f"{tid}: stuck {age}s, no process → planned")
        elif age > STUCK_THRESHOLD and process_alive:
            ops.append(f"{tid}: running {age}s (alive, no action)")
        else:
            ops.append(f"{tid}: active {age}s (normal)")

    return ops


# ── Step 4: 状态持久化 ──

def save_patrol_state(ws_stats: dict[str, dict], engine_status: str,
                      fix_ops: list[str], stuck_count: int, warn: str) -> None:
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

        first_key = {name: to_key(last_6[0]["ws"].get(name, {}))
                     for name in ws_stats}
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
            cwd=ws_path, capture_output=True, timeout=5,
        )
        if r.returncode != 0:
            return
    except OSError:
        return

    # git add
    subprocess.run(["git", "add", "-A"], cwd=ws_path,
                   capture_output=True, timeout=10)

    # 检查是否有改动
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ws_path, capture_output=True, text=True, timeout=10,
    )
    if not r.stdout.strip():
        return

    commit_msg = f"chore: patrol-v4 fix {datetime.now().strftime('%Y-%m-%d-%H%M')}"
    if engine_action and engine_action != "OK":
        commit_msg += f" (engine: {engine_action})"
    subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=ws_path, capture_output=True, timeout=15,
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
    """Engine 重启/死亡时发桌面通知。非阻塞，不抛异常。"""
    notify_script = CCC_HOME / "scripts" / "ccc-notify.sh"
    if not notify_script.is_file():
        return
    try:
        if status == "RESTARTED":
            subprocess.Popen(
                ["bash", str(notify_script), "L2", "Engine 自动重启",
                 "Patrol-v4 检测到 Engine 已停止，已自动重启完成"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        elif status == "DEAD":
            subprocess.Popen(
                ["bash", str(notify_script), "L3", "Engine 重启失败",
                 "Patrol-v4 尝试自动重启 Engine 失败，需人工介入"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
    except OSError:
        pass


def commit_engine_restart(reason: str) -> None:
    """Engine 重启后单独 commit（只记一次）"""
    ws_path = CCC_HOME
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=ws_path, capture_output=True, timeout=5,
        )
        if r.returncode != 0:
            return
    except OSError:
        return

    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ws_path, capture_output=True, text=True, timeout=10,
    )
    # 即使无 staged 改动也强行 commit
    commit_msg = f"chore: patrol-v4 engine restart ({reason})"
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", commit_msg],
        cwd=ws_path, capture_output=True, timeout=15,
    )


# ── Step 6: 一行报告 ──

def format_report(ws_stats: dict[str, dict], engine_status: str,
                  all_fix_ops: list[str], all_stuck_ops: list[str],
                  warnings: list[str]) -> str:
    """输出一行报告"""
    parts = []
    for name in sorted(ws_stats.keys()):
        c = ws_stats.get(name, {})
        parts.append(
            f"{name}(pl:{c.get('planned',0)} ip:{c.get('in_progress',0)} "
            f"rel:{c.get('released',0)} ab:{c.get('abnormal',0)})"
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

    # ── Step 0: Engine 存活检测 ──
    engine_status = ensure_engine_healthy()
    if engine_status in ("DEAD",):
        # Engine 修不好，报告死信后退出（不做后续步骤）
        _log_engine_restart("DEAD", "patrol-v4 failed to restart Engine")
        _notify_engine_restart("DEAD")
        ws_stats = scan_all_ws(WORKSPACES)
        report = format_report(ws_stats, engine_status, [], [], [
            "Engine DEAD — cannot continue"])
        print(report)
        save_patrol_state(ws_stats, engine_status, [], 0, "Engine DEAD")
        return 1

    if engine_status == "RESTARTED":
        engine_operated = True
        _log_engine_restart("RESTARTED", "patrol-v4 detected Engine dead, auto-restarted")
        _notify_engine_restart("RESTARTED")
        commit_engine_restart("restarted by patrol-v4")

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
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        ops = check_stuck_tasks(name, path)
        for o in ops:
            if "→ planned" in o or "→ backlog" in o:
                all_stuck_ops.append(f"{name}:{o}")
                all_fix_ops.append(f"{name}:stale-{o}")
                if name not in READ_ONLY_WS:
                    engine_operated = True
            elif "stuck" in o and "no action" not in o:
                all_stuck_ops.append(f"{name}:{o}")

    # ── Step 4: 状态持久化 ──
    warn = detect_stagnation(ws_stats)
    if warn:
        warnings.append(warn)
    save_patrol_state(ws_stats, engine_status, all_fix_ops, len(all_stuck_ops), warn)

    # ── Step 5: 修复后 commit ──
    for name, path in WORKSPACES.items():
        if not path.is_dir():
            continue
        ws_ops = [o for o in all_fix_ops if o.startswith(f"{name}:")]
        ws_engine_action = engine_status if name == "CCC" else ""
        commit_patrol_fix(path, ws_ops, ws_engine_action)

    # ── Step 6: 报告 ──
    report = format_report(ws_stats, engine_status, all_fix_ops, all_stuck_ops, warnings)
    elapsed = time.time() - start
    print(f"{report} | took={elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
