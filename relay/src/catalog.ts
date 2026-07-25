// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — 免费模型目录
//  从 data/free-models.json 加载, 生成 upstream 条目
//  数据源: OmniRoute freeModelCatalog.data.ts
// ═══════════════════════════════════════════════════════════════

import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import type { FreeModelEntry, UpstreamConfig, TierId } from "./types.js";

const DIR = dirname(fileURLToPath(import.meta.url));
const CATALOG_FILE = process.env.FREE_MODEL_CATALOG || join(DIR, "..", "data", "free-models.json");

let _catalog: FreeModelEntry[] | null = null;

export function loadFreeModelCatalog(): FreeModelEntry[] {
  if (_catalog) return _catalog;
  if (!existsSync(CATALOG_FILE)) {
    console.warn("[catalog] free-models.json not found at", CATALOG_FILE);
    return [];
  }
  try {
    const raw = JSON.parse(readFileSync(CATALOG_FILE, "utf-8"));
    const list: FreeModelEntry[] = Array.isArray(raw) ? raw : (raw.FREE_MODEL_BUDGETS || []);
    _catalog = list;
    console.log(`[catalog] loaded ${list.length} free models`);
    return list;
  } catch (e) {
    console.error("[catalog] failed to parse:", (e as Error).message);
    return [];
  }
}

export function getFreeModelTally(): { total: number; recurringPerMonth: number; providers: number } {
  const models = loadFreeModelCatalog();
  const recurring = models.filter(m => m.free_type.startsWith("recurring"));
  const providers = new Set(models.map(m => m.provider));
  return {
    total: models.length,
    recurringPerMonth: recurring.reduce((s, m) => s + m.monthly_tokens, 0),
    providers: providers.size,
  };
}

/**
 * 从免费模型目录生成 upstreams.json 条目
 * 规则:
 * - tos: "avoid" → 跳过
 * - free_type: "keyless" → 跳过 (无 API key)
 * - 相同 pool_key → 只取一条 (避免同池抢配额)
 * - tier: "code", tier_priority: 99
 * - quota.daily_tokens = monthly_tokens / 30
 * - free_type: "uncapped" → 不设 quota
 */
export function generateUpstreamEntries(catalog?: FreeModelEntry[]): UpstreamConfig[] {
  const models = catalog || loadFreeModelCatalog();
  if (!models.length) return [];

  const entries: UpstreamConfig[] = [];
  const seenPools = new Set<string>();

  for (const m of models) {
    // 过滤: 需要 API key 的、TOS 不安全的、已过时的
    if (m.tos === "avoid") continue;
    if (m.free_type === "keyless" || m.free_type === "discontinued") continue;

    // 同池只取一条
    if (m.pool_key && seenPools.has(m.pool_key)) continue;
    if (m.pool_key) seenPools.add(m.pool_key);

    // 生成上游名
    const name = `free-${m.provider}-${m.model_id.replace(/[^a-zA-Z0-9_-]/g, "-")}`.slice(0, 60);

    // 构造 upstream 配置
    const entry: UpstreamConfig = {
      name,
      base_url: getBaseURL(m.provider),
      api_key: process.env[`FREE_API_KEY_${m.provider.toUpperCase()}`] || `sk-${m.provider}-placeholder`,
      tier: "code" as TierId,
      tier_priority: 99,
      models: ["code" as TierId],
      upstream_model: m.model_id,
      free: true,
      free_type: m.free_type,
      free_tokens_monthly: m.monthly_tokens || 0,
      free_pool_key: m.pool_key || undefined,
    };

    // 日配额 (非无上限类型) — v4.2 写入 tpd + daily_tokens 兼容
    if (m.free_type !== "recurring-uncapped" && m.monthly_tokens > 0) {
      const daily = Math.ceil(m.monthly_tokens / 30);
      entry.quota = { daily_tokens: daily, tpd: daily, rpm: 30, rpd: 1000 };
    }

    entries.push(entry);
  }

  return entries;
}

/**
 * 常见免费渠道的 base URL 映射
 * 可根据实际部署调整
 */
const DEFAULT_PROVIDER_URLS: Record<string, string> = {
  "api-airforce": "https://api.airforce/v1",
  "bazaarlink": "https://api.bazaarlink.io/v1",
  "bluesminds": "https://api.bluesminds.com/v1",
  "deepseek": "https://api.deepseek.com/v1",
  "google": "https://generativelanguage.googleapis.com/v1beta/openai",
  "metaso": "https://api.metaso.cn/v1",
  "openrouter": "https://openrouter.ai/api/v1",
  "zhipu": "https://open.bigmodel.cn/api/paas/v4",
  "baichuan": "https://api.baichuan-ai.com/v1",
  "baidu": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1",
  "minimax": "https://api.minimax.chat/v1",
  "moonshot": "https://api.moonshot.cn/v1",
  "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
};

function getBaseURL(provider: string): string {
  const key = provider.toLowerCase();
  // 先看环境变量
  const envKey = `FREE_BASE_URL_${key.toUpperCase().replace(/[^a-zA-Z0-9_]/g, "_")}`;
  const env = process.env[envKey];
  if (env) return env;
  // 再看默认映射
  return DEFAULT_PROVIDER_URLS[key] || `https://api.${key}.com/v1`;
}

// ── 快速计算免费套餐总数 (用于 Dashboard 展示) ──

export function computeFreeTierSummary() {
  const models = loadFreeModelCatalog();
  const providers = new Map<string, { count: number; tokens: number }>();

  for (const m of models) {
    if (m.tos === "avoid" || m.free_type === "keyless" || m.free_type === "discontinued") continue;
    if (!providers.has(m.provider)) providers.set(m.provider, { count: 0, tokens: 0 });
    const p = providers.get(m.provider)!;
    p.count++;
    p.tokens += m.monthly_tokens || 0;
  }

  return [...providers.entries()]
    .map(([provider, info]) => ({ provider, models: info.count, monthlyTokens: info.tokens }))
    .sort((a, b) => b.monthlyTokens - a.monthlyTokens);
}
