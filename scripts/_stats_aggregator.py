"""_stats_aggregator.py — CCC 统计聚合器 (v0.30)

将 engine 写入的 events.jsonl（原始事件流）聚合为 summary.json（可消费洞察），
供 Engine 决策和 Executor fallback 使用。

职责边界：
- 只读 events.jsonl，不写回
- 只写 summary.json，不碰其他文件
- 幂等：多次运行结果一致（不修改 events.jsonl）
- 轻量：单次运行 < 100ms（events 文件通常 < 1MB）

调用方式：
  1. Engine 空闲时调用 aggregate_stats(workspace)
  2. Executor fallback 决策前调用 load_summary(workspace)
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from _config import get_logger

_log = get_logger("stats")

# ── 输出 schema ──────────────────────────────────────────────
# summary.json 结构见 _write_summary() 的注释


def _stats_dir(ws: Path) -> Path:
    d = ws / ".ccc" / "stats"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _events_file(ws: Path) -> Path:
    return _stats_dir(ws) / "events.jsonl"


def _summary_file(ws: Path) -> Path:
    return _stats_dir(ws) / "summary.json"


def aggregate_stats(workspace: Path) -> dict:
    """读 events.jsonl → 聚合 → 写 summary.json → 返回聚合结果。

    聚合维度：
    - 按 event 类型计数
    - 按 task 统计失败率、平均延时
    - 按 workspace 统计吞吐量

    Returns:
        聚合结果 dict（同时也是写入 summary.json 的内容）
    """
    ws = workspace.resolve()
    ev_file = _events_file(ws)
    if not ev_file.exists():
        _log.debug("no events.jsonl at %s, skipping aggregation", ev_file)
        empty = {
            "aggregated_at": _now_iso(),
            "workspace": ws.name,
            "total_events": 0,
            "events_by_type": {},
            "task_stats": {},
            "perf_insights": [],
            "recommendations": [],
        }
        _write_summary(ws, empty)
        return empty

    # ── 扫描 events ──────────────────────────────────────────
    events_by_type: dict[str, int] = defaultdict(int)
    task_outcomes: dict[str, list[dict]] = defaultdict(list)
    total = 0
    latest_ts: Optional[str] = None

    try:
        with ev_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total += 1
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ev_type = ev.get("event", "unknown")
                events_by_type[ev_type] += 1

                # 记录时间窗口
                ts = ev.get("t")
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts

                # 按 task 聚合
                tid = ev.get("task", "")
                if tid:
                    task_outcomes[tid].append(ev)

    except OSError as e:
        _log.warning("read events.jsonl failed: %s", e)
        return {}

    # ── 分析 task 级别统计 ──────────────────────────────────
    # perf_insights: 按 event 类型的时间序列趋势
    # task_stats: 每个 task 的完成状态、总耗时
    task_stats = {}
    task_failures = 0
    task_success = 0
    total_latency = 0.0
    latency_count = 0

    for tid, events in task_outcomes.items():
        statuses = [e.get("event") for e in events]
        has_fail = any("fail" in s or "quarantine" in s for s in statuses)
        has_success = any(
            s in ("move", "product_done", "pytest") and e.get("exit_code") == 0
            for s, e in zip(statuses, events)
        )

        # 提取延时信息（如果有）
        latencies = []
        for ev in events:
            if ev.get("event") == "pytest" and "duration_s" in ev:
                latencies.append(ev["duration_s"])
            # 可扩展：其他事件的延时

        if has_fail:
            task_failures += 1
        if has_success:
            task_success += 1

        task_stats[tid] = {
            "total_events": len(events),
            "has_failure": has_fail,
            "has_success": has_success,
            "latency_samples": len(latencies),
            "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "last_event": events[-1].get("event") if events else None,
            "last_ts": events[-1].get("t") if events else None,
        }

    # ── 生成性能洞察 ─────────────────────────────────────────
    perf_insights = []

    # 洞察1: 失败率
    total_tasks = len(task_stats)
    if total_tasks > 0:
        fail_rate = round(task_failures / total_tasks * 100, 1)
        perf_insights.append({
            "metric": "task_failure_rate",
            "value": fail_rate,
            "unit": "percent",
            "label": f"Task failure rate: {fail_rate}% ({task_failures}/{total_tasks})",
        })

    # 洞察2: 事件分布异常
    for ev_type, count in sorted(events_by_type.items(), key=lambda x: -x[1]):
        if ev_type in ("product_fail", "quarantine") and count > 3:
            perf_insights.append({
                "metric": f"{ev_type}_spike",
                "value": count,
                "unit": "count",
                "label": f"High {ev_type} count: {count} (threshold: 3)",
                "severity": "warning",
            })

    # 洞察3: 吞吐量
    if latest_ts:
        perf_insights.append({
            "metric": "total_events",
            "value": total,
            "unit": "count",
            "label": f"Total events recorded: {total}",
            "latest_event": latest_ts,
        })

    # ── 生成可执行建议 ──────────────────────────────────────
    recommendations = []

    # 如果 product_fail 很多 → 建议检查 plan 生成或切换模型
    if events_by_type.get("product_fail", 0) > 3:
        recommendations.append({
            "action": "check_product_role",
            "reason": f"product_role failed {events_by_type['product_fail']} times",
            "suggestion": "Consider plan generation model or switch to fallback",
        })

    # 如果 quarantine 很多 → 建议启用 fallback 链
    if events_by_type.get("quarantine", 0) > 5:
        recommendations.append({
            "action": "enable_fallback_chain",
            "reason": f"{events_by_type['quarantine']} tasks quarantined",
            "suggestion": "Enable executor fallback chain to reduce quarantine rate",
        })

    # 如果 move 成功率高 → 系统健康
    move_count = events_by_type.get("move", 0)
    if move_count > 10 and task_failures == 0:
        recommendations.append({
            "action": "system_healthy",
            "reason": f"{move_count} successful moves, 0 failures",
            "suggestion": "System operating normally",
        })

    # ── 组装输出 ─────────────────────────────────────────────
    summary = {
        "aggregated_at": _now_iso(),
        "workspace": ws.name,
        "total_events": total,
        "latest_event_ts": latest_ts,
        "events_by_type": dict(events_by_type),
        "task_stats": {
            "total": total_tasks,
            "success": task_success,
            "failed": task_failures,
            "details": task_stats,
        },
        "perf_insights": perf_insights,
        "recommendations": recommendations,
    }

    _write_summary(ws, summary)
    _log.info("aggregated %d events for %s → summary.json", total, ws.name)
    return summary


def load_summary(workspace: Path) -> dict:
    """加载已聚合的 summary.json（不出错则返回空 dict）。

    Executor fallback 决策前调用此函数获取历史洞察。
    """
    ws = workspace.resolve()
    sf = _summary_file(ws)
    if not sf.exists():
        return {}
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        _log.debug("load_summary failed: %s", e)
        return {}


def _write_summary(ws: Path, data: dict) -> None:
    """原子写 summary.json（temp + rename）。"""
    sf = _summary_file(ws)
    tmp = sf.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.rename(sf)
    except OSError as e:
        _log.warning("write summary.json failed: %s", e)
        if tmp.exists():
            tmp.unlink()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── CLI 入口（手动触发用）──
if __name__ == "__main__":
    import sys
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    result = aggregate_stats(ws)
    print(json.dumps(result, ensure_ascii=False, indent=2))
