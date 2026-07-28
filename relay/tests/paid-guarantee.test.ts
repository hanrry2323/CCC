// ═══════════════════════════════════════════════════════════════
//  paid-only failover（取代 PaidGuarantee / free-first）
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  selectNextCandidate,
  streamWithFallback,
  nonStreamWithFallback,
  markBad,
  _clearFetchGrayForTest,
} from "../src/fallback.js";
import { isPaidUpstream, boostPaidCandidates } from "../src/tiers.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import type { UpstreamConfig, RoutingResult } from "../src/types.js";

const okBody = `data: ${JSON.stringify({ choices: [{ delta: { content: "hi" } }] })}\n\n`;

function paid(name: string, extra: Partial<UpstreamConfig> = {}): UpstreamConfig {
  return {
    name,
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: `sk-${name}`,
    tier: "flash",
    tier_priority: 1,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
    ...extra,
  };
}

function ctxReset() {
  cool.clear();
  hlt.clear();
  sc.clear();
  setAppContext(
    createAppContext({
      clients: cls,
      usage: { value: [] },
      recentLogs: { value: [] },
      health: hlt,
      cooldowns: cool,
      scores: sc,
      startTime: Date.now(),
      cacheStats: { hits: 0, misses: 0, prefixHits: 0, prefixMisses: 0 },
      usageIndex: usgIdx$,
    }),
  );
  _clearFetchGrayForTest();
}

describe("isPaidUpstream / boostPaidCandidates (noop)", () => {
  it("detects Go paid", () => {
    expect(isPaidUpstream(paid("a"))).toBe(true);
  });
  it("boostPaidCandidates is noop under paid-only", () => {
    const a = paid("a");
    const b = paid("b", { enabled: false });
    expect(boostPaidCandidates([a, b], "flash")).toEqual([a, b]);
  });
});

describe("selectNextCandidate paid-only", () => {
  beforeEach(ctxReset);

  it("returns first untried key in order", () => {
    const a = paid("paid-a");
    const b = paid("paid-b");
    const tried = new Set<string>();
    const opts = {
      budgetStart: Date.now(),
      attempts: 0,
      failedPlatforms: new Set<string>(),
      rateLimitedHosts: new Set<string>(),
    };
    expect(selectNextCandidate([a, b], tried, opts)!.name).toBe("paid-a");
    tried.add("paid-a");
    expect(selectNextCandidate([a, b], tried, opts)!.name).toBe("paid-b");
  });

  it("skips rate-limited key", () => {
    const a = paid("paid-a");
    const b = paid("paid-b");
    const opts = {
      budgetStart: Date.now(),
      attempts: 0,
      failedPlatforms: new Set<string>(),
      rateLimitedHosts: new Set(["paid-a"]),
    };
    expect(selectNextCandidate([a, b], new Set(), opts)!.name).toBe("paid-b");
  });
});

describe("streamWithFallback paid-only", () => {
  beforeEach(ctxReset);
  afterEach(() => {
    vi.restoreAllMocks();
    cool.clear();
  });

  it("succeeds on sole paid key", async () => {
    const up = paid("sole");
    const routing: RoutingResult = {
      upstream: up,
      candidates: [up],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const r = await streamWithFallback(routing, async () => new Response(okBody, { status: 200 }));
    expect(r.upstream?.name).toBe("sole");
    expect(r.trail.some(t => t.reason === "ok" || t.reason === "active")).toBe(true);
  });

  it("sole upstream skips peek — delayed first byte still succeeds under peek budget", async () => {
    const up = paid("sole-slow");
    const routing: RoutingResult = {
      upstream: up,
      candidates: [up],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    // 若仍走 5-line/12s peek，此处延迟首包会被误杀；快路径应直接透传
    const slow = new ReadableStream<Uint8Array>({
      async start(controller) {
        await new Promise(r => setTimeout(r, 50));
        controller.enqueue(new TextEncoder().encode(okBody));
        controller.close();
      },
    });
    const r = await streamWithFallback(routing, async () => new Response(slow, { status: 200 }));
    expect(r.upstream?.name).toBe("sole-slow");
    expect(r.firstLines).toEqual([]);
    expect(cool.has(up.name)).toBe(false);
  });

  it("fails over to second paid when first throws", async () => {
    const a = paid("paid-a");
    const b = paid("paid-b");
    const routing: RoutingResult = {
      upstream: a,
      candidates: [a, b],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const called: string[] = [];
    const r = await streamWithFallback(routing, async (up) => {
      called.push(up.name);
      if (up.name === "paid-a") throw new Error("fetch failed");
      return new Response(okBody, { status: 200 });
    });
    expect(r.upstream?.name).toBe("paid-b");
    expect(called[0]).toBe("paid-a");
    expect(called).toContain("paid-b");
    expect(called[called.length - 1]).toBe("paid-b");
  });

  it("non-stream succeeds on sole paid key", async () => {
    const up = paid("ns-sole");
    const routing: RoutingResult = {
      upstream: up,
      candidates: [up],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const body = { id: "1", content: [{ type: "text", text: "ok" }] };
    const r = await nonStreamWithFallback(routing, async () => ({
      response: new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
      body,
    }));
    expect(r.upstream?.name).toBe("ns-sole");
  });

  it("paid fetch short-cools only that key", () => {
    const u1 = paid("go-a", { provider_group: "opencode-go-paid" });
    const u2 = paid("go-b", { provider_group: "opencode-go-paid-b" });
    markBad(u1, 0, "fetch failed");
    expect(cool.has("go-a")).toBe(true);
    expect(cool.has("go-b")).toBe(false);
  });
});
