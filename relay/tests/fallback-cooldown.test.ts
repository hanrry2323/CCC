// ═══════════════════════════════════════════════════════════════
//  tests/fallback-cooldown.test.ts
//  回归: 限流/错误上游必须触发冷却, 且 route() 下一个请求跳过它
//  (此前 setCooldowns 未接线 + fallback 不冷却 HTTP 错误 → 任务终段)
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { streamWithFallback, markBad } from "../src/fallback.js";
import { isUpstreamOk } from "../src/tiers.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import type { UpstreamConfig, RoutingResult } from "../src/types.js";

const makeUp = (name: string): UpstreamConfig => ({
  name,
  base_url: `https://api.test/${name}/v1`,
  api_key: "sk-test",
  tier: "flash",
  tier_priority: 1,
  models: ["flash"],
  upstream_model: "test-model",
});

const okBody = `data: ${JSON.stringify({ choices: [{ delta: { content: "hi" } }] })}\n\n`;

describe("fallback cooldown on upstream errors", () => {
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
  });

  it("cools a rate-limited (429) upstream so the next route() skips it", async () => {
    const u1 = makeUp("u1");
    const u2 = makeUp("u2");
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1, u2],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };

    globalThis.fetch = vi.fn(async (url: string) => {
      if (url.includes("u1")) {
        return new Response(JSON.stringify({ error: { message: "rate limit exceeded" } }), { status: 429 });
      }
      return new Response(okBody, { status: 200 });
    }) as any;

    const res = await streamWithFallback(routing, async (up) =>
      fetch(up.base_url + "/chat/completions"),
    );

    // 透明降级到 u2 成功
    expect(res.reader).not.toBeNull();
    expect(res.upstream!.name).toBe("u2");
    // u1 已被冷却
    expect(cool.get("u1")).toBeTruthy();
    expect(isUpstreamOk(u1)).toBe(false);
    expect(isUpstreamOk(u2)).toBe(true);
  });

  it("respects Retry-After for FreeUsageLimitError and does not tank score", async () => {
    const u1 = makeUp("u1");
    const u2 = makeUp("u2");
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1, u2],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };

    globalThis.fetch = vi.fn(async (url: string) => {
      if (url.includes("u1")) {
        return new Response(
          JSON.stringify({ error: { type: "FreeUsageLimitError", message: "Rate limit exceeded. Please try again later." } }),
          { status: 429, headers: { "retry-after": "3600" } },
        );
      }
      return new Response(okBody, { status: 200 });
    }) as any;

    const res = await streamWithFallback(routing, async (up) =>
      fetch(up.base_url + "/chat/completions"),
    );

    expect(res.upstream!.name).toBe("u2");
    const c = cool.get("u1")!;
    const leftSec = Math.round((c.until - Date.now()) / 1000);
    // 使用 Retry-After 而不是默认 60s
    expect(leftSec).toBeGreaterThanOrEqual(3590);
    // 配额失败不记为低分
    expect(sc.get("u1")?.ewma ?? 0.8).toBe(0.8);
  });

  it("cools a 400 upstream error (transient gateway failure)", async () => {
    const u1 = makeUp("u1");
    const u2 = makeUp("u2");
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1, u2],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };

    globalThis.fetch = vi.fn(async (url: string) => {
      if (url.includes("u1")) {
        return new Response(JSON.stringify({ error: { message: "Upstream request failed" } }), { status: 400 });
      }
      return new Response(okBody, { status: 200 });
    }) as any;

    const res = await streamWithFallback(routing, async (up) =>
      fetch(up.base_url + "/chat/completions"),
    );

    expect(res.upstream!.name).toBe("u2");
    expect(cool.get("u1")).toBeTruthy();
    expect(isUpstreamOk(u1)).toBe(false);
  });

  it("exhausts all candidates → returns 503 with Retry-After info", async () => {
    const u1 = makeUp("u1");
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };

    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ error: { message: "monthly usage limit reached" } }), { status: 429 }),
    ) as any;

    const res = await streamWithFallback(routing, async (up) =>
      fetch(up.base_url + "/chat/completions"),
    );

    expect(res.reader).toBeNull();
    expect(res.errorCode).toBe(503);
    expect(res.retryAfterSec).toBeGreaterThan(0);
    expect(res.trail?.length).toBeGreaterThan(0);
  });

  it("stall before client write fails over to next upstream", async () => {
    const u1 = makeUp("stall-u1");
    const u2 = makeUp("stall-u2");
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1, u2],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };

    const peekLines = Array.from({ length: 5 }, () => okBody.trim()).join("\n") + "\n";

    globalThis.fetch = vi.fn(async (url: string) => {
      if (String(url).includes("stall-u1")) {
        const stream = new ReadableStream({
          start(controller) {
            const enc = new TextEncoder();
            controller.enqueue(enc.encode(peekLines));
            // peek 读满后后续 read 挂起 → consume 触发 StallError
          },
        });
        return new Response(stream, { status: 200 });
      }
      return new Response(okBody, { status: 200 });
    }) as any;

    const prev = process.env.STALL_IDLE_MS;
    process.env.STALL_IDLE_MS = "100";
    try {
      let bytes = 0;
      const res = await streamWithFallback(
        routing,
        async (up) => fetch(up.base_url + "/chat/completions"),
        {
          getBytesWritten: () => bytes,
          consume: async ({ reader, stallMs }) => {
            const { streamReadWithTimeout } = await import("../src/utils.js");
            await streamReadWithTimeout(reader, stallMs);
            bytes += 1;
          },
        },
      );
      expect(res.upstream?.name).toBe("stall-u2");
      expect(res.trail.some(t => t.reason === "stall")).toBe(true);
      expect(cool.get("stall-u1")).toBeTruthy();
    } finally {
      if (prev === undefined) delete process.env.STALL_IDLE_MS;
      else process.env.STALL_IDLE_MS = prev;
    }
  }, 15_000);

  it("respects FAILOVER_MAX_ATTEMPTS budget", async () => {
    const ups = [makeUp("b1"), makeUp("b2"), makeUp("b3")];
    const routing: RoutingResult = {
      upstream: ups[0]!,
      candidates: ups,
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ error: { message: "rate limit exceeded" } }), { status: 429 }),
    ) as any;

    const prev = process.env.FAILOVER_MAX_ATTEMPTS;
    process.env.FAILOVER_MAX_ATTEMPTS = "2";
    try {
      const res = await streamWithFallback(routing, async (up) =>
        fetch(up.base_url + "/chat/completions"),
      );
      expect(res.errorCode).toBe(503);
      expect(res.trail.some(t => t.reason === "budget:attempts" || t.name === "*")).toBe(true);
      // only 2 upstreams attempted (plus maybe budget marker)
      const attempted = res.trail.filter(t => t.name !== "*");
      expect(attempted.length).toBeLessThanOrEqual(2);
    } finally {
      if (prev === undefined) delete process.env.FAILOVER_MAX_ATTEMPTS;
      else process.env.FAILOVER_MAX_ATTEMPTS = prev;
    }
  });
});

// ── Phase 2 回归测试：markBad 冷却退避 ──

describe("markBad cooldown backoff", () => {
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
    cool.clear();
    sc.clear();
  });

  it("quota cooldown starts at cls.sec × EWMA (0.8→2×)", () => {
    const up = makeUp("quota-up");
    // 冷启动 score=0.8 → multiplier 2 → 300×2=600s
    markBad(up, 429, "usage limit reached");
    const c = cool.get("quota-up");
    expect(c).toBeTruthy();
    const dur = Math.round((c!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(590);
    expect(dur).toBeLessThanOrEqual(610);
  });

  it("non-quota error backoff escalates on repeated failures", () => {
    const up = makeUp("bad-up");

    // 第一次: 120s * 2 (冷启动 score=0.8 → multiplier 2) = 240s
    markBad(up, 400, "Error from provider: Upstream request failed");
    let c = cool.get("bad-up");
    expect(c).toBeTruthy();
    let dur = Math.round((c!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(235);
    expect(dur).toBeLessThanOrEqual(245);

    // 立即解除冷却，模拟冷却到期
    cool.delete("bad-up");

    // 第二次: 120 * 2 = 240s, cap at 1800
    markBad(up, 400, "Error from provider: Upstream request failed");
    c = cool.get("bad-up");
    dur = Math.round((c!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(235);
    expect(dur).toBeLessThanOrEqual(245);

    // 第三次: 120 * 4 = 480s
    cool.delete("bad-up");
    markBad(up, 400, "Error from provider: Upstream request failed");
    c = cool.get("bad-up");
    dur = Math.round((c!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(470);
    expect(dur).toBeLessThanOrEqual(600); // 可能有 cap
  });

  it("quota backoff escalates correctly", () => {
    const up = makeUp("quota-up");

    // 第一次: 300s * 2 (冷启动 score=0.8 → multiplier 2) = 600s
    markBad(up, 429, "insufficient quota");
    let dur = Math.round((cool.get("quota-up")!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(595);
    expect(dur).toBeLessThanOrEqual(605);

    // 第二次: 300 * 2 = 600s
    cool.delete("quota-up");
    markBad(up, 429, "insufficient quota");
    dur = Math.round((cool.get("quota-up")!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(595);
    expect(dur).toBeLessThanOrEqual(605);
  });

  it("same-host rate-limit skips sibling keys without cooling them", async () => {
    const shared = "https://opencode.ai/zen/v1";
    const u1: UpstreamConfig = { ...makeUp("go-a"), base_url: shared };
    const u2: UpstreamConfig = { ...makeUp("go-b"), base_url: shared };
    const u3: UpstreamConfig = { ...makeUp("other"), base_url: "https://other.example/v1" };
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1, u2, u3],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    globalThis.fetch = vi.fn(async (url: string) => {
      if (String(url).includes("opencode.ai")) {
        return new Response(JSON.stringify({ error: { message: "Rate limit exceeded" } }), { status: 429 });
      }
      return new Response(okBody, { status: 200 });
    }) as any;

    const res = await streamWithFallback(routing, async (up) =>
      fetch(up.base_url + "/chat/completions"),
    );
    expect(res.upstream!.name).toBe("other");
    expect(cool.get("go-a")).toBeTruthy();
    // 同 host 第二钥被 skip，不应进冷却
    expect(cool.get("go-b")).toBeFalsy();
    expect(res.trail.some(t => t.name === "go-b" && t.reason.includes("same-host"))).toBe(true);
  });

  it("rate-limit cooldown stays short even when EWMA is tanked", () => {
    const up = makeUp("rate-up");
    // 模拟多钥假死后的低分（旧逻辑会 60×10=600s）
    sc.set("rate-up", {
      ewma: 0.2,
      recentTs: Date.now(),
      failStreak: 12,
      lastSuccessTs: 0,
      totalSuccess: 0,
      totalFail: 12,
    });
    markBad(up, 0, "Rate limit exceeded. Please try again later");
    const c = cool.get("rate-up");
    expect(c).toBeTruthy();
    const dur = Math.round((c!.until - Date.now()) / 1000);
    expect(dur).toBeGreaterThanOrEqual(15);
    expect(dur).toBeLessThanOrEqual(120);
    // 限流不记 EWMA 失败
    expect(sc.get("rate-up")!.ewma).toBeCloseTo(0.2, 5);
  });
});

describe("v4.3 empty stream markBad", () => {
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
  });

  it("marks empty stream upstream bad after retries", async () => {
    const u1 = makeUp("empty-u");
    const u2 = makeUp("ok-u");
    const routing: RoutingResult = {
      upstream: u1,
      candidates: [u1, u2],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };

    // 仅 [DONE]、无 content → peek 判 empty
    const emptyBody = `data: [DONE]\n\n`;
    globalThis.fetch = vi.fn(async (url: string) => {
      if (String(url).includes("empty-u")) {
        return new Response(emptyBody, { status: 200 });
      }
      return new Response(okBody, { status: 200 });
    }) as any;

    const res = await streamWithFallback(routing, async (up) =>
      fetch(up.base_url + "/chat/completions"),
    );

    expect(res.upstream!.name).toBe("ok-u");
    expect(cool.get("empty-u")).toBeTruthy();
    expect(isUpstreamOk(u1)).toBe(false);
  });
});
