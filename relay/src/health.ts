// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.0 — 健康探针 + Cooldown 管理
//  状态通过 getAppContext() 获取（依赖注入）
// ═══════════════════════════════════════════════════════════════

import type { UpstreamConfig } from "./types.js";
import { getConfig } from "./config.js";
import { getAppContext } from "./context.js";
import { upstreamFetch } from "./egress.js";

const PROBE_TIMEOUT_MS = 10_000;
const PROBE_INTERVAL_MS = 120_000; // 2min 全量探针间隔

/** 标记 upstream 进入 cooldown (由 fallback.ts 调用) */
export function bad(up: UpstreamConfig, sec: number, reason: string): void {
  const cooldowns = getAppContext().cooldowns;
  cooldowns.set(up.name, { until: Date.now() + sec * 1000, reason });
}

/**
 * 单个上游健康探针
 */
export async function probeOne(u: UpstreamConfig): Promise<void> {
  const health = getAppContext().health;
  if (!u.api_key || !u.base_url) {
    health.set(u.name, { status: "none", latency_ms: 0, timestamp: Date.now() });
    return;
  }
  const hasPrev = health.has(u.name);

  let t0 = Date.now();
  try {
    const resp = await upstreamFetch(u, `${u.base_url}/models`, {
      method: "GET",
      headers: { Authorization: `Bearer ${u.api_key}` },
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    const ms = Date.now() - t0;
    if (resp.ok) {
      health.set(u.name, { status: "healthy", latency_ms: ms, timestamp: Date.now() });
      return;
    } else if (resp.status === 429) {
      health.set(u.name, { status: "ratelimit", latency_ms: ms, timestamp: Date.now(), error: `HTTP ${resp.status}` });
      return;
    }
  } catch { /* 网络错误 */ }

  if (!hasPrev) {
    const m = u.upstream_model || u.models?.[0] || "gpt-4o-mini";
    t0 = Date.now();
    try {
      const resp = await upstreamFetch(u, `${u.base_url}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${u.api_key}` },
        body: JSON.stringify({ model: m, messages: [{ role: "user", content: "hi" }], max_tokens: 1 }),
        signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
      });
      const ms = Date.now() - t0;
      health.set(u.name, {
        status: resp.ok ? "healthy" : resp.status === 429 ? "ratelimit" : "unhealthy",
        latency_ms: ms, timestamp: Date.now(),
        error: resp.ok ? undefined : `HTTP ${resp.status}`,
      });
    } catch {
      // POST 也失败 → 保持待探针
    }
  }
}

/** 全量探针 */
export async function probeAll(): Promise<void> {
  const cfg = getConfig();
  await Promise.allSettled(cfg.all.map(probeOne));
}

/** 启动周期性探针任务 */
export function startHealthProbe(): void {
  probeAll();
  setInterval(probeAll, PROBE_INTERVAL_MS);
}
