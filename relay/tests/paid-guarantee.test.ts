// ═══════════════════════════════════════════════════════════════
//  PaidGuarantee + breaker 分级 + selectNextCandidate
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  streamWithFallback,
  nonStreamWithFallback,
  markBad,
  selectNextCandidate,
} from "../src/fallback.js";
import { boostPaidCandidates, isPaidUpstream } from "../src/tiers.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import { resetConfig, loadConfig } from "../src/config.js";
import { writeFileSync, mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import type { UpstreamConfig, RoutingResult } from "../src/types.js";

const okBody = `data: ${JSON.stringify({ choices: [{ delta: { content: "hi" } }] })}\n\n`;

function makeFree(name: string, prio = 1): UpstreamConfig {
  return {
    name,
    base_url: `https://api.test/${name}/v1`,
    api_key: "sk-free",
    tier: "flash",
    tier_priority: prio,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: true,
    billing: "zen-free",
  };
}

function makePaid(name = "opencode-go-paid-flash"): UpstreamConfig {
  return {
    name,
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-paid",
    tier: "flash",
    tier_priority: 80,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
  };
}

function ctxReset() {
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
}

describe("isPaidUpstream / boostPaidCandidates", () => {
  beforeEach(ctxReset);
  afterEach(() => cool.clear());

  it("detects go billing and free===false", () => {
    expect(isPaidUpstream(makePaid())).toBe(true);
    expect(isPaidUpstream(makeFree("f1"))).toBe(false);
    expect(isPaidUpstream({ ...makeFree("x"), free: false })).toBe(true);
  });

  it("boosts paid to second when majority free long-cooled", () => {
    const tmp = mkdtempSync(join(tmpdir(), "relay-boost-"));
    const upsPath = join(tmp, "upstreams.json");
    const f1 = makeFree("f1", 1);
    const f2 = makeFree("f2", 1);
    const f3 = makeFree("f3", 1);
    const paid = makePaid();
    writeFileSync(
      upsPath,
      JSON.stringify([
        { ...f1, tier: "flash" },
        { ...f2, tier: "flash" },
        { ...f3, tier: "flash" },
        { ...paid, tier: "flash" },
      ]),
    );
    const     prev = process.env.LOOP_UPSTREAMS_FILE;
    process.env.LOOP_UPSTREAMS_FILE = upsPath;
    resetConfig();
    loadConfig(upsPath);
    try {
      cool.set("f1", { until: Date.now() + 3600_000, reason: "day" });
      cool.set("f2", { until: Date.now() + 3600_000, reason: "day" });
      // f3 not long cool — 2/3 >= 50%
      const ordered = [f1, f2, f3, paid];
      const boosted = boostPaidCandidates(ordered, "flash");
      expect(boosted.map(u => u.name)).toEqual([paid.name, "f1", "f2", "f3"]);
    } finally {
      resetConfig();
      if (prev === undefined) delete process.env.LOOP_UPSTREAMS_FILE;
      else process.env.LOOP_UPSTREAMS_FILE = prev;
      rmSync(tmp, { recursive: true, force: true });
    }
  });
});

describe("selectNextCandidate PaidGuarantee", () => {
  beforeEach(ctxReset);

  it("forces paid after one free failure on same egress", () => {
    const free1 = { ...makeFree("free1"), base_url: "https://opencode.ai/zen/v1" };
    const free2 = { ...makeFree("free2"), base_url: "https://opencode.ai/zen/v1" };
    const paid = makePaid();
    const next = selectNextCandidate([free1, free2, paid], new Set(["free1"]), {
      budgetStart: Date.now(),
      attempts: 1,
      freeFailCount: 1,
      failedPlatforms: new Set(),
      rateLimitedHosts: new Set(),
    });
    expect(next?.name).toBe(paid.name);
  });

  it("tries other-egress free before paid", () => {
    const free1 = { ...makeFree("free1"), base_url: "https://opencode.ai/zen/v1", proxy: "" };
    const free2 = {
      ...makeFree("free2"),
      base_url: "https://opencode.ai/zen/v1",
      proxy: "http://127.0.0.1:18080",
    };
    const paid = makePaid();
    const next = selectNextCandidate([free1, free2, paid], new Set(["free1"]), {
      budgetStart: Date.now(),
      attempts: 1,
      freeFailCount: 1,
      failedPlatforms: new Set(),
      rateLimitedHosts: new Set(),
    });
    expect(next?.name).toBe("free2");
  });

  it("reserves last attempt for paid", () => {
    const prev = process.env.FAILOVER_MAX_ATTEMPTS;
    process.env.FAILOVER_MAX_ATTEMPTS = "4";
    try {
      const free1 = makeFree("free1");
      const free2 = makeFree("free2");
      const paid = makePaid();
      const next = selectNextCandidate([free1, free2, paid], new Set(), {
        budgetStart: Date.now(),
        attempts: 3, // attemptsLeft=1
        freeFailCount: 0,
        failedPlatforms: new Set(),
        rateLimitedHosts: new Set(),
      });
      expect(next?.name).toBe(paid.name);
    } finally {
      if (prev === undefined) delete process.env.FAILOVER_MAX_ATTEMPTS;
      else process.env.FAILOVER_MAX_ATTEMPTS = prev;
    }
  });
});

describe("streamWithFallback must reach paid", () => {
  beforeEach(ctxReset);
  afterEach(() => {
    vi.restoreAllMocks();
    cool.clear();
  });

  it("tries paid after same-egress free fetch failures", async () => {
    const free1 = { ...makeFree("free-a"), base_url: "https://opencode.ai/zen/v1" };
    const free2 = { ...makeFree("free-b"), base_url: "https://opencode.ai/zen/v1" };
    const paid = makePaid();
    const routing: RoutingResult = {
      upstream: free1,
      candidates: [free1, free2, paid],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const called: string[] = [];
    const res = await streamWithFallback(routing, async (up) => {
      called.push(up.name);
      if (up.name === paid.name) {
        return new Response(okBody, { status: 200 });
      }
      throw new Error("fetch failed");
    });
    expect(res.upstream?.name).toBe(paid.name);
    expect(called).toContain(paid.name);
    // 同 egress：第一次 free 失败后应插队 paid（sibling 被 same-host 或 forcePaid 跳过）
    expect(called.indexOf(paid.name)).toBeLessThanOrEqual(2);
  });

  it("rotates free across different egress before forcing paid", async () => {
    const freeDirect = { ...makeFree("free-direct"), proxy: "" };
    const freeHk = { ...makeFree("free-hk"), proxy: "http://127.0.0.1:18080" };
    const paid = makePaid();
    const routing: RoutingResult = {
      upstream: freeDirect,
      candidates: [freeDirect, freeHk, paid],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const called: string[] = [];
    const res = await streamWithFallback(routing, async (up) => {
      called.push(up.name);
      if (up.name === paid.name) return new Response(okBody, { status: 200 });
      throw new Error("fetch failed");
    });
    expect(res.upstream?.name).toBe(paid.name);
    expect(called).toContain("free-direct");
    expect(called).toContain("free-hk");
    expect(called.indexOf("free-hk")).toBeLessThan(called.indexOf(paid.name));
  });

  it("aborts hung free fetch when wall clock expires", async () => {
    const prev = process.env.FAILOVER_MAX_MS;
    process.env.FAILOVER_MAX_MS = "400";
    const free1 = makeFree("hang-free");
    const paid = makePaid("hang-paid");
    const routing: RoutingResult = {
      upstream: free1,
      candidates: [free1, paid],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const t0 = Date.now();
    const res = await streamWithFallback(routing, async (up, signal) => {
      if (up.name === paid.name) {
        return new Response(okBody, { status: 200 });
      }
      await new Promise<void>((resolve, reject) => {
        const t = setTimeout(() => resolve(), 30_000);
        signal?.addEventListener("abort", () => {
          clearTimeout(t);
          reject(Object.assign(new Error("aborted"), { name: "TimeoutError" }));
        }, { once: true });
      });
      return null;
    });
    if (prev === undefined) delete process.env.FAILOVER_MAX_MS;
    else process.env.FAILOVER_MAX_MS = prev;
    expect(Date.now() - t0).toBeLessThan(5_000);
    // 墙钟打断 free 后应能落到 paid，或至少不拖死 30s
    expect(res.upstream?.name === paid.name || res.errorCode === 503).toBe(true);
  });

  it("non-stream also reaches paid after free fail", async () => {
    const free1 = makeFree("ns-free");
    const paid = makePaid("ns-paid");
    const routing: RoutingResult = {
      upstream: free1,
      candidates: [free1, paid],
      tier: "flash",
      is_fallback: false,
      fallback_model: null,
    };
    const called: string[] = [];
    const res = await nonStreamWithFallback(routing, async (up) => {
      called.push(up.name);
      if (isPaidUpstream(up)) {
        return {
          response: new Response(JSON.stringify({ choices: [{ message: { content: "ok" } }] }), { status: 200 }),
          body: { choices: [{ message: { content: "ok" } }] },
        };
      }
      throw new Error("connect timeout");
    });
    expect(res.upstream?.name).toBe(paid.name);
    expect(called).toEqual(["ns-free", "ns-paid"]);
  });
});

describe("breaker tier: fetch does not fan-out", () => {
  let tmpDir: string;
  let prevUps: string | undefined;

  beforeEach(() => {
    ctxReset();
    tmpDir = mkdtempSync(join(tmpdir(), "relay-brk-"));
    const ups = join(tmpDir, "upstreams.json");
    writeFileSync(
      ups,
      JSON.stringify([
        {
          name: "acct-a",
          base_url: "https://opencode.ai/zen/v1",
          api_key: "k1",
          tier: "flash",
          tier_priority: 1,
          models: ["flash"],
          upstream_model: "deepseek-v4-flash",
          provider_group: "hanrry2323",
          free: true,
        },
        {
          name: "acct-b",
          base_url: "https://opencode.ai/zen/v1",
          api_key: "k2",
          tier: "flash",
          tier_priority: 1,
          models: ["flash"],
          upstream_model: "deepseek-v4-flash",
          provider_group: "hanrry2323",
          free: true,
        },
        {
          name: "paid-go",
          base_url: "https://opencode.ai/zen/go/v1",
          api_key: "kp",
          tier: "flash",
          tier_priority: 80,
          models: ["flash"],
          upstream_model: "deepseek-v4-flash",
          billing: "opencode-go",
          free: false,
        },
      ]),
    );
    prevUps = process.env.LOOP_UPSTREAMS_FILE;
    process.env.LOOP_UPSTREAMS_FILE = ups;
    resetConfig();
    loadConfig(ups);
  });

  afterEach(() => {
    cool.clear();
    resetConfig();
    if (prevUps === undefined) delete process.env.LOOP_UPSTREAMS_FILE;
    else process.env.LOOP_UPSTREAMS_FILE = prevUps;
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("fetch failure cools only that key, not sibling provider_group", () => {
    const a: UpstreamConfig = {
      name: "acct-a",
      base_url: "https://opencode.ai/zen/v1",
      api_key: "k1",
      tier: "flash",
      tier_priority: 1,
      models: ["flash"],
      upstream_model: "m",
      provider_group: "hanrry2323",
      free: true,
    };
    markBad(a, 0, "fetch failed after retries");
    expect(cool.get("acct-a")).toBeTruthy();
    const left = Math.round((cool.get("acct-a")!.until - Date.now()) / 1000);
    expect(left).toBeLessThanOrEqual(25);
    expect(cool.get("acct-b")).toBeFalsy();
    // 连打 3 次 fetch 也不应 trip breaker
    markBad(a, 0, "fetch failed after retries");
    markBad(a, 0, "fetch failed after retries");
    expect(cool.get("acct-b")).toBeFalsy();
  });

  it("paid fetch gets short cool (≤5s) and never trips breaker", () => {
    const paid: UpstreamConfig = {
      name: "paid-go",
      base_url: "https://opencode.ai/zen/go/v1",
      api_key: "kp",
      tier: "flash",
      tier_priority: 80,
      models: ["flash"],
      upstream_model: "m",
      billing: "opencode-go",
      free: false,
      provider_group: "should-not-trip",
    };
    markBad(paid, 0, "attempt timeout");
    const left = Math.round((cool.get("paid-go")!.until - Date.now()) / 1000);
    expect(left).toBeLessThanOrEqual(5);
    expect(left).toBeGreaterThanOrEqual(2);
  });
});
