"""Loop Observer只读巡查框架 — 每日/合入巡检任务。"""

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from server.board.registry import load_projects
from server.board.loader import load_dispatch_cards, get_index_path
from server.board.plans import list_plans

logger = logging.getLogger("ccc.engine.observer")

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_current_state(cfg: dict[str, Any]) -> dict[str, Any]:
    """获取当前系统的状态：时间戳、最新的 git merge 提交、cards.index.jsonl 信息。"""
    now = time.time()
    git_commit = ""
    try:
        res = subprocess.run(
            ["git", "log", "origin/main", "--merges", "-n", "1", "--format=%H"],
            capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            git_commit = res.stdout.strip()
    except Exception:
        pass

    if not git_commit:
        try:
            res = subprocess.run(
                ["git", "log", "--merges", "-n", "1", "--format=%H"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                git_commit = res.stdout.strip()
        except Exception:
            pass

    cards_mtime = 0.0
    cards_size = 0
    try:
        idx_path = get_index_path(cfg.get("SCHEDULER_DISPATCH_DIR"))
        if idx_path.exists():
            stat = idx_path.stat()
            cards_mtime = stat.st_mtime
            cards_size = stat.st_size
    except Exception:
        pass

    return {
        "timestamp": now,
        "git_commit": git_commit,
        "cards_index_mtime": cards_mtime,
        "cards_index_size": cards_size,
    }


def should_run(cfg: dict[str, Any], current_state: dict[str, Any]) -> tuple[bool, str]:
    """判断是否应当运行巡查（时间/Git提交/索引文件变更）。"""
    if cfg.get("OBSERVER_FORCE", "").strip().lower() in ("true", "1", "yes") or os.environ.get("OBSERVER_FORCE") == "1":
        return True, "force via config/env"

    data_dir = cfg.get("DATA_DIR", "")
    if not data_dir:
        data_dir = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR") or "data"

    last_run_path = Path(data_dir).resolve() / "observer" / "last-run.json"
    if not last_run_path.exists():
        return True, "first run"

    try:
        with open(last_run_path, "r", encoding="utf-8") as f:
            last_state = json.load(f)
    except Exception as e:
        return True, f"last-run error: {e}"

    # 1. 每日 1 次（超过 24 小时）
    last_ts = last_state.get("timestamp", 0.0)
    if current_state["timestamp"] - last_ts >= 86400:
        return True, f"24 hours passed since last run at {last_ts}"

    # 2. 合入后触发（Git merge 提交变更）
    last_commit = last_state.get("git_commit", "")
    curr_commit = current_state["git_commit"]
    if curr_commit and last_commit and curr_commit != last_commit:
        return True, f"new merge commit {curr_commit} (prev {last_commit})"

    # 3. cards.index.jsonl 发生变化
    last_mtime = last_state.get("cards_index_mtime", 0.0)
    last_size = last_state.get("cards_index_size", 0)
    curr_mtime = current_state["cards_index_mtime"]
    curr_size = current_state["cards_index_size"]
    if curr_mtime != last_mtime or curr_size != last_size:
        return True, f"cards.index.jsonl changed: mtime {curr_mtime} (prev {last_mtime}), size {curr_size} (prev {last_size})"

    return False, "thresholds not met"


def run_observer(cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """定时只读巡检入口。

    采集 registry/卡/方案快照，并在满足阈值时写入/更新快照。
    """
    current_state = _get_current_state(cfg)
    need_run, reason = should_run(cfg, current_state)

    if not need_run:
        logger.info("Loop Observer 跳过运行：%s", reason)
        return True, {"skipped": True, "reason": reason}

    logger.info("Loop Observer 开始运行：%s", reason)

    # 1. 读取只读快照数据
    try:
        projects = load_projects()
        projects_list = [{"id": p.id, "prefix": p.prefix, "status": p.status} for p in projects]
    except Exception as e:
        logger.error("加载项目注册表失败: %s", e)
        projects_list = []

    try:
        dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")
        if not dispatch_dir:
            dispatch_dir = PROJECT_ROOT / "docs" / "dispatch"
        else:
            dispatch_dir = Path(dispatch_dir)
        cards = load_dispatch_cards(dispatch_dir)
        cards_list = [c.to_dict() for c in cards]
    except Exception as e:
        logger.error("加载任务卡失败: %s", e)
        cards_list = []

    try:
        plans = list_plans(PROJECT_ROOT)
    except Exception as e:
        logger.error("加载方案/计划失败: %s", e)
        plans = []

    # 2. 统计摘要
    cards_states: dict[str, int] = {}
    for c in cards_list:
        state = str(c.get("state", "未知"))
        cards_states[state] = cards_states.get(state, 0) + 1

    plans_states: dict[str, int] = {}
    for p in plans:
        state = str(p.get("status", "未知"))
        plans_states[state] = plans_states.get(state, 0) + 1

    summary = {
        "timestamp": current_state["timestamp"],
        "collected_at": datetime.datetime.fromtimestamp(current_state["timestamp"]).isoformat(),
        "projects_count": len(projects_list),
        "cards_count": len(cards_list),
        "plans_count": len(plans),
        "cards_states": cards_states,
        "plans_states": plans_states,
        "projects": projects_list,
    }

    # 3. 写入输出文件
    data_dir = cfg.get("DATA_DIR", "")
    if not data_dir:
        data_dir = os.environ.get("CCC_DATA_DIR") or os.environ.get("DATA_DIR") or "data"

    observer_dir = Path(data_dir).resolve() / "observer"
    try:
        observer_dir.mkdir(parents=True, exist_ok=True)

        # 写入 snapshot.json
        snapshot_path = observer_dir / "snapshot.json"
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 写入带时间戳的快照 snapshot-YYYYMMDD-HHMMSS.json
        dt_str = datetime.datetime.fromtimestamp(current_state["timestamp"]).strftime("%Y%m%d-%H%M%S")
        ts_snapshot_path = observer_dir / f"snapshot-{dt_str}.json"
        with open(ts_snapshot_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        # 更新 last-run.json
        last_run_path = observer_dir / "last-run.json"
        with open(last_run_path, "w", encoding="utf-8") as f:
            json.dump(current_state, f, ensure_ascii=False, indent=2)

        logger.info("Loop Observer 快照已保存到 %s", observer_dir)
    except Exception as e:
        logger.error("写入 Observer 快照失败: %s", e)
        return False, {"error": str(e)}

    return True, summary
