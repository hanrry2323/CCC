"""_cost_telemetry.py — Per-execution 成本遥测（Phase 2 FinOps 核心）

每次 claude CLI / opencode 调用记录一条 JSONL：
  {role, provider, model_raw, tokens_prompt, tokens_completion, tokens_total, cost, latency_ms, ok, task_id, phase_id, timestamp}

写入 ~/.ccc/cost-telemetry.jsonl（append-only，10 MB 自动轮转，保留 3 个 .gz 备份）。

Cost 基准价来自 _COST_MAP（$/1M tokens），按 role→provider 查找。

v0.51.0 P3-1: 字段命名统一
  - 单条记录用 `model_raw` / `cost` / `latency_ms`（与 JSONL 落盘一致）
  - 聚合返回（summarize_task_calls）用 `cost_usd` / `latency_ms_total`（带 _total 后缀表求和）
  - timestamp 改用 _utils.now_iso_utc()（带 Z 后缀，UTC SSOT）
"""
from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path

# v0.51.0 P3-1: 委托 _utils.now_iso_utc() 统一 timestamp 格式（带 Z 后缀）
from _utils import now_iso_utc as _utils_now_iso_utc

_TELEMETRY_FILE = Path.home() / ".ccc" / "cost-telemetry.jsonl"

# v0.51.0 (P1-3): 轮转阈值与备份数
_MAX_TELEMETRY_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_TELEMETRY_BACKUPS = 3

# 角色 → provider → (input $/1M, output $/1M)
# 来源：上游定价，近似值
_COST_MAP: dict[str, dict[str, tuple[float, float]]] = {
    "planner": {
        "claude-sonnet": (3.0, 15.0),
        "gemini-flash": (0.1, 0.4),
        "deepseek-v4": (0.15, 0.6),
        "minimax-m3": (0.5, 2.0),
        "xfyun-code": (0.3, 0.8),
        "zhipu-glm4": (0.0, 0.0),
    },
    "executor": {
        "claude-sonnet": (3.0, 15.0),
        "claude-haiku": (0.25, 1.25),
        "deepseek-v4": (0.15, 0.6),
        "minimax-m3": (0.5, 2.0),
        "xfyun-code": (0.3, 0.8),
        "zhipu-glm4": (0.0, 0.0),
    },
    "reviewer": {
        "claude-sonnet": (3.0, 15.0),
        "gemini-flash": (0.1, 0.4),
        "deepseek-v4": (0.15, 0.6),
        "minimax-m3": (0.5, 2.0),
        "xfyun-code": (0.3, 0.8),
        "zhipu-glm4": (0.0, 0.0),
    },
    "tester": {
        "claude-haiku": (0.25, 1.25),
        "gemini-flash": (0.1, 0.4),
        "minimax-m3": (0.5, 2.0),
        "zhipu-glm4": (0.0, 0.0),
    },
}

# 异常流量跳闸：单 task 单角色 1h 内调用 > MAX_CALLS_PER_HOUR → 隔离
_MAX_CALLS_PER_HOUR = 20


def _normalize_provider(raw_model: str) -> str:
    """根据模型名推断 provider 分组"""
    m = raw_model.lower()
    if "sonnet" in m or "opus" in m:
        return "claude-sonnet"
    if "haiku" in m:
        return "claude-haiku"
    if "gemini" in m:
        return "gemini-flash"
    if "deepseek" in m:
        return "deepseek-v4"
    if "minimax" in m or "m3" in m:
        return "minimax-m3"
    if "xfyun" in m or "astron" in m:
        return "xfyun-code"
    if "zhipu" in m or "glm" in m or "glm" in m:
        return "zhipu-glm4"
    # fallback: 用 raw_model 的 prefix
    return raw_model.split("-")[0] if "-" in raw_model else raw_model


def _compute_cost(
    role: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """按角色+provider 查表算出本次调用成本（美元）"""
    role_map = _COST_MAP.get(role, {})
    rates = role_map.get(provider)
    if rates is None:
        # fallback: 用 default 价
        return 0.0
    input_rate, output_rate = rates
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000


def record_call(
    role: str,
    provider_or_model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    ok: bool,
    task_id: str = "",
    phase_id: str = "",
) -> dict:
    """记录一次 LLM 调用成本遥测。返回写入的记录 dict。"""
    provider = _normalize_provider(provider_or_model)
    cost = _compute_cost(role, provider, prompt_tokens, completion_tokens)

    record = {
        "role": role,
        "provider": provider,
        "model_raw": provider_or_model,
        "tokens_prompt": prompt_tokens,
        "tokens_completion": completion_tokens,
        "tokens_total": prompt_tokens + completion_tokens,
        "cost": round(cost, 6),
        "latency_ms": latency_ms,
        "ok": ok,
        "task_id": task_id,
        "phase_id": phase_id,
        # v0.51.0 P3-1: 统一用 _utils.now_iso_utc()（带 Z 后缀，UTC SSOT）
        "timestamp": _utils_now_iso_utc(),
    }

    try:
        _TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        with open(_TELEMETRY_FILE, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 静默失败，不阻塞主流程

    return record


def _rotate_if_needed() -> None:
    """v0.51.0 (P1-3): 文件超过 _MAX_TELEMETRY_BYTES 时轮转。

    cost-telemetry.jsonl → cost-telemetry.jsonl.1.gz（新建）
    cost-telemetry.jsonl.{N-1}.gz → cost-telemetry.jsonl.{N}.gz（后移）
    cost-telemetry.jsonl.{N}.gz → 删除（最旧）

    轮转失败静默忽略，不阻塞主流程。
    """
    try:
        if not _TELEMETRY_FILE.exists():
            return
        if _TELEMETRY_FILE.stat().st_size < _MAX_TELEMETRY_BYTES:
            return
        # 删除最旧备份
        oldest = Path(str(_TELEMETRY_FILE) + f".{_MAX_TELEMETRY_BACKUPS}.gz")
        if oldest.exists():
            oldest.unlink()
        # 逐个后移 .{N-1}.gz → .{N}.gz
        for i in range(_MAX_TELEMETRY_BACKUPS - 1, 0, -1):
            src = Path(str(_TELEMETRY_FILE) + f".{i}.gz")
            dst = Path(str(_TELEMETRY_FILE) + f".{i + 1}.gz")
            if src.exists():
                src.rename(dst)
        # 压缩当前文件为 .1.gz
        import shutil

        with open(_TELEMETRY_FILE, "rb") as f_in:
            with gzip.open(str(_TELEMETRY_FILE) + ".1.gz", "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        _TELEMETRY_FILE.unlink()
    except OSError:
        pass  # 静默失败


def estimate_tokens(text: str) -> int:
    """粗估 token（无上游 usage 时）：约 4 字符 ≈ 1 token。"""
    if not text:
        return 0
    return max(1, len(text) // 4)


def summarize_task_calls(task_id: str) -> dict:
    """按 task_id 汇总 cost-telemetry.jsonl（真实每任务计量）。"""
    empty = {
        "task_id": task_id,
        "calls": 0,
        "ok_calls": 0,
        "fail_calls": 0,
        "tokens_prompt": 0,
        "tokens_completion": 0,
        "tokens_total": 0,
        "cost_usd": 0.0,
        "latency_ms_total": 0,
        "by_role": {},
        "records": [],
    }
    if not task_id or not _TELEMETRY_FILE.exists():
        return empty
    rows: list[dict] = []
    try:
        with open(_TELEMETRY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("task_id") == task_id:
                    rows.append(rec)
    except OSError:
        return empty

    by_role: dict[str, dict] = {}
    for rec in rows:
        role = str(rec.get("role") or "unknown")
        bucket = by_role.setdefault(
            role,
            {
                "calls": 0,
                "tokens_total": 0,
                "cost_usd": 0.0,
                "latency_ms_total": 0,
            },
        )
        bucket["calls"] += 1
        bucket["tokens_total"] += int(rec.get("tokens_total") or 0)
        bucket["cost_usd"] = round(
            bucket["cost_usd"] + float(rec.get("cost") or 0), 6
        )
        bucket["latency_ms_total"] += int(rec.get("latency_ms") or 0)

    return {
        "task_id": task_id,
        "calls": len(rows),
        "ok_calls": sum(1 for r in rows if r.get("ok")),
        "fail_calls": sum(1 for r in rows if not r.get("ok")),
        "tokens_prompt": sum(int(r.get("tokens_prompt") or 0) for r in rows),
        "tokens_completion": sum(
            int(r.get("tokens_completion") or 0) for r in rows
        ),
        "tokens_total": sum(int(r.get("tokens_total") or 0) for r in rows),
        "cost_usd": round(sum(float(r.get("cost") or 0) for r in rows), 6),
        "latency_ms_total": sum(int(r.get("latency_ms") or 0) for r in rows),
        "by_role": by_role,
        "records": rows[-50:],
    }


# ============================================================
# 异常流量检测
# ============================================================

def check_abnormal_traffic(
    task_id: str,
    role: str,
) -> bool:
    """检查 task_id+role 在最近 1h 内调用次数是否 > MAX_CALLS_PER_HOUR。

    返回 True = 疑似死循环，需要跳闸/隔离。
    """
    if not task_id:
        return False
    try:
        if not _TELEMETRY_FILE.exists():
            return False
        now = time.time()
        one_hour_ago = now - 3600
        count = 0
        with open(_TELEMETRY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("task_id") == task_id and rec.get("role") == role:
                    # v0.51.0 P3-1: timestamp 现在是 _utils.now_iso_utc() 格式（带 Z 后缀）
                    ts = rec.get("timestamp", "")
                    if ts:
                        try:
                            from datetime import datetime, timezone
                            # 兼容带 Z 和不带 Z 两种格式（历史数据可能无 Z）
                            ts_clean = ts.rstrip("Z")
                            rec_ts = datetime.strptime(
                                ts_clean, "%Y-%m-%dT%H:%M:%S"
                            ).replace(tzinfo=timezone.utc).timestamp()
                            if rec_ts >= one_hour_ago:
                                count += 1
                        except (ValueError, OSError):
                            count += 1  # 无法解析的 timestamp 保守处理
        return count > _MAX_CALLS_PER_HOUR
    except Exception:
        return False
