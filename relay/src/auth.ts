// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.0 — 客户端鉴权 + 配额检查
//  状态通过 getAppContext() 获取（依赖注入）
// ═══════════════════════════════════════════════════════════════

import type { IncomingMessage } from "http";
import type { AuthenticatedClient } from "./types.js";
import { getAppContext } from "./context.js";
import { rebuildUsgIdx } from "./state.js";

const REBUILD_INTERVAL_MS = 60_000;

/** 鉴权: 校验 X-Client-Id / X-Client-Key, 返回客户端 + 配额标志 */
export function cauth(req: IncomingMessage): AuthenticatedClient | null {
  const id = req.headers["x-client-id"] as string;
  const key = req.headers["x-client-key"] as string;
  if (!id || !key) return null;
  const c = getAppContext().clients.value.find(x => x.id === id);
  if (!c || c.key !== key || c.active === false) return null;
  if (c.quota?.daily_tokens && used("client", c.id) >= c.quota.daily_tokens) {
    return { id: c.id, name: c.name || c.id, models: c.models, qe: true };
  }
  return { id: c.id, name: c.name || c.id, models: c.models };
}

/** 校验客户端是否有权使用某 model */
export function cmay(c: AuthenticatedClient | null, model: string): boolean {
  if (!c?.models?.length) return true;
  return c.models.some(
    x => x === "*" || x === model || (x.endsWith("*") && model.startsWith(x.slice(0, -1))),
  );
}

/** 按 field(client/upstream) 统计今日已用 token (M9: O(1) 查索引, 每 60s 重建) */
export function used(field: "client" | "upstream", key: string): number {
  const usgIdx = getAppContext().usageIndex;
  if (Date.now() - usgIdx.builtAt > REBUILD_INTERVAL_MS) {
    rebuildUsgIdx();
  }
  return usgIdx[field].get(key) || 0;
}

export function todayStart(): number {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}
