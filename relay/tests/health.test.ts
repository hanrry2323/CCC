// ═══════════════════════════════════════════════════════════════
//  tests/health.test.ts — 健康探针 + cooldown 管理（v3.6 新增覆盖）
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { bad, probeOne } from "../src/health.js";
import { isUpstreamOk } from "../src/tiers.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import type { UpstreamConfig } from "../src/types.js";

const makeUp = (name: string, base = "https://api.test/v1"): UpstreamConfig => ({
  name,
  base_url: base,
  api_key: "sk-test",
  tier: "flash",
  tier_priority: 1,
  models: ["flash"],
  upstream_model: "test-model",
});

beforeEach(() => {
  cool.clear();
  hlt.clear();
  sc.clear();
  setAppContext(createAppContext({
    clients: cls,
    usage: { value: [] },
    recentLogs: { value: [] },
    health: hlt,
    cooldowns: cool,
    scores: sc,
    startTime: Date.now(),
    cacheStats: { hits: 0, misses: 0, prefixHits: 0, prefixMisses: 0 },
    usageIndex: usgIdx$,
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
  cool.clear();
  hlt.clear();
});

describe("bad()", () => {
  it("写入 cooldown 直到指定时间", () => {
    const u = makeUp("up-bad");
    bad(u, 60, "test reason");
    const c = cool.get("up-bad");
    expect(c).toBeDefined();
    expect(c!.reason).toBe("test reason");
    expect(c!.until).toBeGreaterThan(Date.now());
    expect(c!.until).toBeLessThanOrEqual(Date.now() + 60_000 + 100);
  });

  it("isUpstreamOk 拒绝 cooldown 中的上游", () => {
    const u = makeUp("up-cool");
    bad(u, 30, "");
    expect(isUpstreamOk(u)).toBe(false);
  });

  it("cooldown 到期后 isUpstreamOk 恢复 true", () => {
    const u = makeUp("up-expire");
    bad(u, 0, ""); // 立即过期
    expect(isUpstreamOk(u)).toBe(true);
  });
});

describe("probeOne", () => {
  it("200 OK → healthy（不再清除 cooldown：探针与冷却解耦）", async () => {
    const u = makeUp("up-healthy");
    bad(u, 600, "stale");
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ choices: [{ message: { content: "ok" } }] }), { status: 200 })
    ) as unknown as typeof fetch;
    await probeOne(u);
    const h = hlt.get("up-healthy");
    expect(h?.status).toBe("healthy");
    expect(typeof h?.latency_ms).toBe("number");
    // 探针不再操作冷却，冷却由 markBad 设置、自然过期管理
    expect(cool.has("up-healthy")).toBe(true);
  });

  it("429 → ratelimit", async () => {
    const u = makeUp("up-rl");
    globalThis.fetch = vi.fn(async () =>
      new Response("rate limited", { status: 429 })
    ) as unknown as typeof fetch;
    await probeOne(u);
    expect(hlt.get("up-rl")?.status).toBe("ratelimit");
  });

  it("5xx → POST fallback 建立初始 unhealthy（无已知状态时兜底）", async () => {
    const u = makeUp("up-5xx");
    globalThis.fetch = vi.fn(async () =>
      new Response("internal", { status: 503 })
    ) as unknown as typeof fetch;
    await probeOne(u);
    // GET /models 失败 + POST fallback → unhealthy（需要建立初始状态）
    expect(hlt.get("up-5xx")?.status).toBe("unhealthy");
  });

  it("网络异常 → 不更新状态，保留上次已知", async () => {
    const u = makeUp("up-neterr");
    globalThis.fetch = vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof fetch;
    await probeOne(u);
    // 探针网络错误时不更新，防 transient 误报
    expect(hlt.get("up-neterr")).toBeUndefined();
  });

  it("200 保留短 cooldown (≤ 2min)", async () => {
    const u = makeUp("up-short-cd");
    bad(u, 30, "transient"); // 短冷却
    globalThis.fetch = vi.fn(async () =>
      new Response("{}", { status: 200 })
    ) as unknown as typeof fetch;
    await probeOne(u);
    expect(cool.has("up-short-cd")).toBe(true); // 短冷却保留
  });

  it("无 api_key → 状态为 none", async () => {
    const u = makeUp("up-nokey");
    u.api_key = "";
    await probeOne(u);
    expect(hlt.get("up-nokey")?.status).toBe("none");
  });
});