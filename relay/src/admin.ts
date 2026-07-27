// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — Admin API
//  upstreams / clients / usage / stats / health / logs / guide / cache
// ═══════════════════════════════════════════════════════════════

import { getConfig, reloadConfig, getUpstreamsFile, isAutoReloadEnabled, assertValidUpstreamList, validateConfig, normalizeUpstream } from "./config.js";
import { getTierSummary, getTierBlockReason } from "./tiers.js";
import { probeAll } from "./health.js";
import { used, todayStart } from "./auth.js";
import { getAppContext } from "./context.js";
import { json, readBody, urlParams } from "./http.js";
import { cacheStats, cacheClear, cacheDelete } from "./cache.js";
import { getScore, getAllScores } from "./scoring.js";
import { ledgerSnapshot, ledgerAll } from "./ledger.js";
import { upstreamFetch } from "./egress.js";
import type { UpstreamConfig } from "./types.js";
import { readFileSync, existsSync, writeFileSync } from "fs";
import type { IncomingMessage, ServerResponse } from "http";

function loadUpstreams(): UpstreamConfig[] {
  const f = getUpstreamsFile();
  if (!existsSync(f)) return [];
  try {
    const raw = JSON.parse(readFileSync(f, "utf-8"));
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function saveUpstreams(list: UpstreamConfig[]): void {
  writeFileSync(getUpstreamsFile(), JSON.stringify(list, null, 2) + "\n");
}

export async function handleAdmin(req: IncomingMessage, res: ServerResponse, pathname: string): Promise<void> {
  const cfg = getConfig();
  const { health: hlt, cooldowns: cool, clients: cls, usage: usg, recentLogs: rlg, startTime: T0, recentTrails } = getAppContext();
  const method = req.method || "GET";

  // ── /admin/status ──
  if (method === "GET" && pathname === "/admin/status") {
    return json(res, 200, {
      name: "AI Loop Router",
      version: "4.3.0",
      description: "AI 编程工具的智能梯队路由网关",
      uptime: Math.floor((Date.now() - T0) / 1000),
      upstreams: cfg.all.length,
      tiers: cfg.tiers.size,
      models: cfg.names.join(","),
      today_req: usg.value.filter(x => x.timestamp >= todayStart()).length,
      today_tokens: usg.value.filter(x => x.timestamp >= todayStart()).reduce((s, x) => s + (x.total_tokens || 0), 0),
      cache: cacheStats(),
      config_auto_reload: isAutoReloadEnabled(),
    });
  }

  // ── /admin/trail ──
  if (method === "GET" && pathname === "/admin/trail") {
    const limit = Math.min(200, parseInt(urlParams(req).get("limit") || "50", 10) || 50);
    return json(res, 200, { trails: recentTrails.value.slice(-limit).reverse() });
  }

  // ── /admin/ledger ──
  if (method === "GET" && pathname === "/admin/ledger") {
    return json(res, 200, { ledger: ledgerAll(cfg.all) });
  }

  // ── /admin/upstreams ──
  if (method === "GET" && pathname === "/admin/upstreams") {
    const ts = todayStart();
    const data = cfg.all.map(u => {
      const scRec = getAllScores()[u.name];
      return {
        name: u.name, base_url: u.base_url, models: u.models, tier: u.tier,
        tier_priority: u.tier_priority, upstream_model: u.upstream_model,
        fallback_model: u.fallback_model, quota: u.quota || null,
        free: u.free || false, free_type: u.free_type || null,
        provider_group: u.provider_group || null,
        proxy: u.proxy || null,
        health: hlt.get(u.name) || null, cooldown: cool.get(u.name)?.until || null,
        used_today: used("upstream", u.name),
        req_today: usg.value.filter(x => x.timestamp >= ts && x.upstream === u.name).length,
        score: getScore(u.name),
        fail_streak: scRec?.failStreak ?? 0,
        total_success: scRec?.totalSuccess ?? 0,
        total_fail: scRec?.totalFail ?? 0,
        ledger: u.quota ? ledgerSnapshot(u) : null,
        block_reason: getTierBlockReason(u),
      };
    });
    return json(res, 200, data);
  }

  if (method === "POST" && pathname === "/admin/upstreams") {
    let b: any;
    try { b = await readBody(req); } catch { return json(res, 400, { error: "Invalid JSON" }); }
    const norm = normalizeUpstream(b);
    if (!norm) {
      const { warnings } = validateConfig([b]);
      return json(res, 400, { error: warnings.join("; ") || "Invalid upstream" });
    }
    const list = loadUpstreams();
    if (list.find(x => x.name === norm.name)) return json(res, 409, { error: "Upstream already exists" });
    if (b.fallback_model) norm.fallback_model = b.fallback_model;
    if (b.quota) norm.quota = b.quota;
    if (b.primary) norm.primary = b.primary;
    if (b.free) norm.free = b.free;
    if (b.provider_group) norm.provider_group = b.provider_group;
    if (b.enabled === false) norm.enabled = false;
    list.push(norm);
    const err = assertValidUpstreamList(list);
    if (err) return json(res, 400, { error: err });
    saveUpstreams(list);
    reloadConfig();
    return json(res, 201, norm);
  }

  if (method === "PUT" && pathname === "/admin/upstreams") {
    let b: any;
    try { b = await readBody(req); } catch { return json(res, 400, { error: "Invalid JSON" }); }
    if (!Array.isArray(b)) return json(res, 400, { error: "Expected array" });
    const err = assertValidUpstreamList(b);
    if (err) return json(res, 400, { error: err });
    const { valid } = validateConfig(b);
    saveUpstreams(valid);
    reloadConfig();
    probeAll().catch(() => {});
    return json(res, 200, { ok: true, count: valid.length });
  }

  if (method === "PATCH" && pathname.startsWith("/admin/upstreams/")) {
    const name = pathname.slice("/admin/upstreams/".length);
    let b: any;
    try { b = await readBody(req); } catch { return json(res, 400, { error: "Invalid JSON" }); }
    const list = loadUpstreams();
    const idx = list.findIndex(x => x.name === name);
    if (idx < 0) return json(res, 404, { error: "Not found" });
    const merged = { ...list[idx], ...b, name };
    const norm = normalizeUpstream(merged as unknown as Record<string, unknown>);
    if (!norm) {
      const { warnings } = validateConfig([merged]);
      return json(res, 400, { error: warnings.join("; ") || "Invalid upstream" });
    }
    if (merged.fallback_model !== undefined) norm.fallback_model = merged.fallback_model;
    if (merged.quota !== undefined) norm.quota = merged.quota;
    if (merged.primary !== undefined) norm.primary = merged.primary;
    if (merged.free !== undefined) norm.free = merged.free;
    if (merged.provider_group !== undefined) norm.provider_group = merged.provider_group;
    if (merged.enabled !== undefined) norm.enabled = merged.enabled;
    list[idx] = norm;
    const err = assertValidUpstreamList(list);
    if (err) return json(res, 400, { error: err });
    saveUpstreams(list);
    reloadConfig();
    return json(res, 200, norm);
  }

  if (method === "DELETE" && pathname.startsWith("/admin/upstreams/")) {
    const name = pathname.slice("/admin/upstreams/".length);
    if (!name) return json(res, 400, { error: "Missing name" });
    const list = loadUpstreams().filter(u => u.name !== name);
    if (list.length === cfg.all.length) return json(res, 404, { error: "Not found" });
    saveUpstreams(list);
    reloadConfig();
    return json(res, 200, { ok: true, removed: name });
  }

  if (method === "POST" && pathname === "/admin/upstreams/test") {
    let b: any;
    try { b = await readBody(req); } catch { return json(res, 400, { error: "Invalid JSON" }); }
    const name = b?.name;
    if (!name) return json(res, 400, { error: "Missing name" });
    const u = cfg.all.find(x => x.name === name);
    if (!u) return json(res, 404, { error: "Not found" });
    const t0 = Date.now();
    try {
      const resp = await upstreamFetch(u, `${u.base_url}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${u.api_key}` },
        body: JSON.stringify({ model: u.upstream_model || u.models?.[0] || "gpt-4o-mini", messages: [{ role: "user", content: "hi" }], max_tokens: 1 }),
        signal: AbortSignal.timeout(10000),
      });
      return json(res, 200, { name, ok: resp.ok, ms: Date.now() - t0, status: resp.status });
    } catch (e) {
      return json(res, 200, { name, ok: false, ms: Date.now() - t0, error: (e as Error).message });
    }
  }

  // ── /admin/clients ──
  if (method === "GET" && pathname === "/admin/clients") {
    const data = cls.value.map(c => ({
      id: c.id, name: c.name || c.id, models: c.models || [],
      quota: c.quota || null, active: c.active !== false,
      used_today: used("client", c.id),
    }));
    return json(res, 200, data);
  }

  if (method === "PUT" && pathname === "/admin/clients") {
    let b: any;
    try { b = await readBody(req); } catch { return json(res, 400, { error: "Invalid JSON" }); }
    if (!Array.isArray(b)) return json(res, 400, { error: "Expected array" });
    const clientsFile = process.env.LOOP_CLIENTS_FILE || "clients.json";
    const old = existsSync(clientsFile) ? JSON.parse(readFileSync(clientsFile, "utf-8")) : [];
    for (const it of b) {
      if (!it.key && it.id) { const o = old.find((x: any) => x.id === it.id); if (o?.key) it.key = o.key; }
    }
    writeFileSync(clientsFile, JSON.stringify(b, null, 2));
    cls.value = b;
    return json(res, 200, { ok: true, count: b.length });
  }

  if (method === "DELETE" && pathname.startsWith("/admin/clients/")) {
    const id = pathname.slice("/admin/clients/".length);
    if (!id) return json(res, 400, { error: "Missing id" });
    const list = cls.value.filter(c => c.id !== id);
    if (list.length === cls.value.length) return json(res, 404, { error: "Not found" });
    const clientsFile = process.env.LOOP_CLIENTS_FILE || "clients.json";
    writeFileSync(clientsFile, JSON.stringify(list, null, 2));
    cls.value = list;
    return json(res, 200, { ok: true, removed: id });
  }

  // ── /admin/usage ──
  if (method === "GET" && pathname === "/admin/usage") {
    const q = urlParams(req);
    const p = q.get("period") || "today";
    const uf = q.get("upstream");
    const cf = q.get("client");
    const now = Date.now();
    const DAY_MS = 864e5;
    let ps = now;
    if (p === "7d") ps = now - 7 * DAY_MS;
    else if (p === "30d") ps = now - 30 * DAY_MS;
    else if (p === "1d") ps = now - DAY_MS;
    else if (p === "1h") ps = now - 3600_000;
    else if (p === "today") ps = todayStart();
    else ps = todayStart(); // 未知 period 回落今日
    let f = usg.value.filter(r => r.timestamp >= ps);
    if (uf) f = f.filter(r => r.upstream === uf);
    if (cf) f = f.filter(r => r.client === cf);
    const total = f.length;
    const tokens = f.reduce((s, r) => s + (r.total_tokens || 0), 0);
    const cachedTokens = f.reduce((s, r) => s + (r.cached_tokens || 0), 0);
    const byU: Record<string, { n: number; tk: number; cached: number }> = {};
    const byC: Record<string, { n: number; tk: number }> = {};
    for (const r of f) {
      if (!byU[r.upstream]) byU[r.upstream] = { n: 0, tk: 0, cached: 0 };
      byU[r.upstream].n++;
      byU[r.upstream].tk += r.total_tokens || 0;
      byU[r.upstream].cached += r.cached_tokens || 0;
    }
    for (const r of f) {
      const c = r.client || "anonymous";
      if (!byC[c]) byC[c] = { n: 0, tk: 0 };
      byC[c].n++;
      byC[c].tk += r.total_tokens || 0;
    }
    const upTier: Record<string, string> = {};
    for (const [t, ups] of cfg.tiers) for (const u of ups) upTier[u.name] = t;
    const byTier: Record<string, { n: number; tk: number }> = {};
    for (const r of f) {
      const t = upTier[r.upstream] || "unknown";
      if (!byTier[t]) byTier[t] = { n: 0, tk: 0 };
      byTier[t].n++;
      byTier[t].tk += r.total_tokens || 0;
    }
    const trend: Record<string, number> = {};
    for (const r of f) {
      const d = new Date(r.timestamp).toISOString().slice(0, 10);
      trend[d] = (trend[d] || 0) + (r.total_tokens || 0);
    }
    const tr = Object.entries(trend).sort((a, b) => a[0].localeCompare(b[0])).map(([date, tokens]) => ({ date, tokens }));

    // ── 小时级按 tier 聚合 (granularity=hourly) ──
    const hourly: Record<string, Array<{ hour: string; n: number }>> = {};
    const tierOrder = ["pro", "flash", "code"];
    for (const t of tierOrder) hourly[t] = [];
    if (q.get("granularity") === "hourly") {
      const hb: Record<string, Record<string, number>> = {};
      for (const r of f) {
        const hk = new Date(r.timestamp).toISOString().slice(0, 13);
        const t = upTier[r.upstream] || "unknown";
        if (!tierOrder.includes(t)) continue;
        if (!hb[t]) hb[t] = {};
        hb[t][hk] = (hb[t][hk] || 0) + 1;
      }
      for (const t of tierOrder) {
        if (!hb[t]) continue;
        hourly[t] = Object.entries(hb[t])
          .sort((a, b) => a[0].localeCompare(b[0]))
          .map(([hour, n]) => ({ hour, n }));
      }
    }

    return json(res, 200, {
      period: p,
      total,
      tokens,
      cached_tokens: cachedTokens,
      cache_hit_ratio: tokens > 0 ? cachedTokens / tokens : 0,
      by_upstream: byU,
      by_client: byC,
      by_tier: byTier,
      trend: tr,
      hourly,
    });
  }

  // ── /admin/cooldowns ── 运维：冷却列表（剩余秒 + 原因）
  if (method === "GET" && pathname === "/admin/cooldowns") {
    const now = Date.now();
    const items = [...cool.entries()]
      .map(([name, rec]) => ({
        name,
        until: rec.until,
        reason: rec.reason,
        left_sec: Math.max(0, Math.ceil((rec.until - now) / 1000)),
      }))
      .sort((a, b) => b.left_sec - a.left_sec);
    return json(res, 200, { cooldowns: items, count: items.length });
  }

  // ── /admin/cooldowns/clear ── 运维：清冷却 + 软重置低分（多钥限流假死急救）
  // 默认保留长冷却（日配额 / 长 Retry-After），避免清完又撞同一耗尽钥；?force=1 全清
  if (method === "POST" && pathname === "/admin/cooldowns/clear") {
    const ctx = getAppContext();
    const q = urlParams(req);
    const force =
      q.get("force") === "1" ||
      q.get("force") === "true";
    /** 剩余超过此秒数视为日配额类，默认不清 */
    const PRESERVE_LEFT_SEC = 300;
    const before = cool.size;
    let cleared = 0;
    let preserved = 0;
    const now = Date.now();
    if (force) {
      cool.clear();
      cleared = before;
    } else {
      for (const [name, rec] of [...cool.entries()]) {
        const left = Math.ceil((rec.until - now) / 1000);
        if (left > PRESERVE_LEFT_SEC) {
          preserved += 1;
          continue;
        }
        cool.delete(name);
        cleared += 1;
      }
    }
    ctx.providerCooldowns.clear();
    ctx.providerFailCounts.clear();
    let resetScores = 0;
    for (const [, rec] of ctx.scores) {
      if (rec.failStreak > 0 || rec.ewma < 0.5) {
        rec.failStreak = 0;
        rec.ewma = Math.max(rec.ewma, 0.7);
        resetScores += 1;
      }
    }
    console.warn(
      `[admin] cooldowns cleared=${cleared} preserved=${preserved} force=${force} (before=${before}), soft-reset scores=${resetScores}`,
    );
    return json(res, 200, {
      ok: true,
      cleared,
      preserved,
      force,
      before,
      scores_soft_reset: resetScores,
      hint: force
        ? null
        : "long cooldowns (left>300s) preserved; POST ?force=1 to clear all",
    });
  }

  // ── /admin/scores ── score 排行 + cooldown/ledger 原因
  if (method === "GET" && pathname === "/admin/scores") {
    const ranked = cfg.all.map(u => {
      const scRec = getAllScores()[u.name];
      const cd = cool.get(u.name);
      return {
        name: u.name,
        models: u.models,
        tier_priority: u.tier_priority,
        score: getScore(u.name),
        fail_streak: scRec?.failStreak ?? 0,
        total_success: scRec?.totalSuccess ?? 0,
        total_fail: scRec?.totalFail ?? 0,
        block_reason: getTierBlockReason(u),
        cooldown: cd ? { until: cd.until, reason: cd.reason, left_sec: Math.max(0, Math.ceil((cd.until - Date.now()) / 1000)) } : null,
        ledger: u.quota ? ledgerSnapshot(u) : null,
      };
    }).sort((a, b) => b.score - a.score);
    return json(res, 200, { scores: ranked });
  }

  // ── /admin/stats ──
  if (method === "GET" && pathname === "/admin/stats") {
    const ts = todayStart();
    const today = usg.value.filter(x => x.timestamp >= ts);
    const tiers: Record<string, any> = {};
    let totalUp = 0, totalHealthy = 0, totalReq = 0, totalTk = 0;
    for (const [t, ups] of cfg.tiers) {
      const healthy = ups.filter(u => {
        const h = hlt.get(u.name);
        return h && (h.status === "healthy" || h.status === "ratelimit");
      }).length;
      const reqs = today.filter(x => ups.some(u => u.name === x.upstream));
      const tks = reqs.reduce((s, x) => s + (x.total_tokens || 0), 0);
      const lats = ups.map(u => hlt.get(u.name)?.latency_ms).filter((x): x is number => typeof x === "number");
      const avgLat = lats.length ? Math.round(lats.reduce((a, b) => a + b, 0) / lats.length) : 0;
      tiers[t] = { upstreams: ups.length, healthy, requests_today: reqs.length, tokens_today: tks, avg_latency_ms: avgLat };
      totalUp += ups.length;
      totalHealthy += healthy;
      totalReq += reqs.length;
      totalTk += tks;
    }
    return json(res, 200, { tiers, total: { upstreams: totalUp, healthy: totalHealthy, requests_today: totalReq, tokens_today: totalTk }, tier_summary: getTierSummary(cfg) });
  }

  // ── /admin/health ──
  if (method === "GET" && pathname === "/admin/health") {
    return json(res, 200, getHealthStatus());
  }

  // ── /admin/logs ──
  if (method === "GET" && pathname === "/admin/logs") {
    const q = urlParams(req);
    const lim = parseInt(q.get("limit") || "100");
    const uf = q.get("upstream");
    const cf = q.get("client");
    let e = [...rlg.value].reverse();
    if (uf) e = e.filter(x => x.u === uf);
    if (cf) e = e.filter(x => x.c === cf);
    return json(res, 200, e.slice(0, lim));
  }

  // ── /admin/cache ──
  if (method === "GET" && pathname === "/admin/cache") {
    return json(res, 200, cacheStats());
  }
  if (method === "DELETE" && pathname === "/admin/cache") {
    cacheClear();
    return json(res, 200, { ok: true, cleared: true });
  }
  if (method === "DELETE" && pathname.startsWith("/admin/cache/")) {
    const key = pathname.slice("/admin/cache/".length);
    const ok = cacheDelete(key);
    return json(res, ok ? 200 : 404, { ok, key });
  }

  // ── /admin/guide ──
  if (method === "GET" && pathname === "/admin/guide") {
    return json(res, 200, {
      title: "下游接入指南 v3.5 — Tier 梯队路由",
      base_url: `http://127.0.0.1:${process.env.LOOP_PORT || "4100"}`,
      models: cfg.names,
      endpoints: { claude: "/v1/messages", openai: "/v1/chat/completions" },
      auth: { headers: { "X-Client-Id": "your-id", "X-Client-Key": "your-key" } },
    });
  }

  // ── /admin (index) ──
  if (method === "GET" && pathname === "/admin") {
    return json(res, 200, {
      endpoints: [
        "status", "upstreams", "clients", "usage", "stats",
        "health", "logs", "guide", "cache", "scores", "trail",
        "POST cooldowns/clear",
      ],
    });
  }

  return json(res, 404, { error: "Admin endpoint not found: " + method + " " + pathname });
}

// ── Helpers ──

function getHealthStatus(): Record<string, any> {
  const ctx = getAppContext();
  const hlt = ctx.health;
  const T0 = ctx.startTime;
  const cfg = getConfig();
  const upTot = cfg.all.length;
  // 'none' = 没 api_key 或刚注册未探针过, 不计入 healthy, 但也不是 unhealthy
  const upHealthy = cfg.all.filter(u => {
    const h = hlt.get(u.name);
    return h && (h.status === "healthy" || h.status === "ratelimit");
  }).length;
  const upPending = cfg.all.filter(u => {
    const h = hlt.get(u.name);
    return !h || h.status === "none";
  }).length;
  let allTiersOk = true;
  for (const [, tierUp] of cfg.tiers) {
    const hasHealthy = tierUp.some(u => {
      const h = hlt.get(u.name);
      return h && (h.status === "healthy" || h.status === "ratelimit");
    });
    if (!hasHealthy) { allTiersOk = false; break; }
  }
  // 实际可服务数 = 健康数 + 待探针数 (待探针 5min 内会变, 不能算 down)
  const upServable = upHealthy + upPending;
  const status = upHealthy === 0 && upPending === 0 ? "down"
    : (!allTiersOk || upHealthy < upTot - upPending) ? "degraded"
    : "healthy";
  return {
    status,
    uptime_seconds: Math.floor((Date.now() - T0) / 1000),
    tiers_total: cfg.tiers.size,
    upstreams_total: upTot,
    upstreams_healthy: upHealthy,
    upstreams_pending: upPending, // 新增: 等待首次探针 (5min 后会被统计)
  };
}

