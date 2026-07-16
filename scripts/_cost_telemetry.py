"""_cost_telemetry.py — Per-execution 成本遥测（Phase 2 FinOps 核心）

每次 claude CLI / opencode 调用记录一条 JSONL：
  {role, provider, model, tokens_prompt, tokens_completion, cost, latency_ms, ok, timestamp, task_id}

写入 ~/.ccc/cost-telemetry.jsonl（append-only）。

Cost 基准价来自 _COST_MAP（$/1M tokens），按 role→provider 查找。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_TELEMETRY_FILE = Path.home() / ".ccc" / "cost-telemetry.jsonl"

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
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
    }

    try:
        _TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_TELEMETRY_FILE, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 静默失败，不阻塞主流程

    return record


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
                    # timestamp field is GMT ISO string
                    ts = rec.get("timestamp", "")
                    if ts:
                        try:
                            from datetime import datetime
                            rec_ts = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").timestamp()
                            if rec_ts >= one_hour_ago:
                                count += 1
                        except (ValueError, OSError):
                            count += 1  # 无法解析的 timestamp 保守处理
        return count > _MAX_CALLS_PER_HOUR
    except Exception:
        return False
