// ═══════════════════════════════════════════════════════════════
//  tests/router.test.ts — Tier 路由 + Session Affinity 验证
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, unlinkSync, existsSync } from "fs";
import { loadConfig, getConfig, resetConfig } from "../src/config.js";
import { route, affinitySet, affinityDelete, affinityKey, affinityGet, affinityDeleteByUpstream, affinityLookup, resolveRequestTier, _resetFairCursorForTest, _clearAffinityForTest } from "../src/router.js";
import { setAppContext, getAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import type { UpstreamConfig, TierId } from "../src/types.js";

const TEST_FILE = "/tmp/test-router-upstreams.json";

const TEST_UPSTREAMS: UpstreamConfig[] = [
  {
    name: "minimax-m3",
    base_url: "https://api.minimax.chat/v1",
    api_key: "sk-minimax",
    tier: "flash",
    tier_priority: 1,
    models: ["flash"],
    upstream_model: "minimax-m3",
  },
  {
    name: "opencode-go-new",
    base_url: "https://api.opencode.chat/v1",
    api_key: "sk-opencode",
    tier: "flash",
    tier_priority: 2,
    models: ["flash"],
    upstream_model: "gpt-4o-mini",
  },
  {
    name: "claude-opus",
    base_url: "https://api.anthropic.com/v1",
    api_key: "sk-anthropic",
    tier: "pro",
    tier_priority: 1,
    models: ["pro"],
    upstream_model: "claude-opus-4",
  },
  {
    name: "glm-free",
    base_url: "https://open.bigmodel.cn/api/paas/v4",
    api_key: "sk-glm",
    tier: "code",
    tier_priority: 5,
    models: ["code"],
    upstream_model: "glm-4-flash",
    free: true,
  },
  {
    name: "zhipu-glm-flash",
    base_url: "https://open.bigmodel.cn/api/paas/v4",
    api_key: "sk-old",
    tier: "code",
    tier_priority: 99,
    models: ["code"],
    upstream_model: "glm-4v-flash",
  },
];

function writeConfig() {
  writeFileSync(TEST_FILE, JSON.stringify(TEST_UPSTREAMS, null, 2));
}

describe("router", () => {
  beforeEach(() => {
    writeConfig();
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
    loadConfig(TEST_FILE);
  });

  afterEach(() => {
    if (existsSync(TEST_FILE)) unlinkSync(TEST_FILE);
    resetConfig();
  });

  describe("route()", () => {
    it("returns the highest priority upstream for a tier", () => {
      const r = route("flash");
      expect(r.upstream).not.toBeNull();
      expect(r.upstream!.name).toBe("minimax-m3");
      expect(r.candidates.length).toBe(2);
      expect(r.is_fallback).toBe(false);
    });

    it("returns all ok candidates in the tier", () => {
      const r = route("code");
      expect(r.candidates.length).toBe(2);
      expect(r.candidates[0].name).toBe("glm-free");
      expect(r.candidates[1].name).toBe("zhipu-glm-flash");
    });

    it("skips cooled-down upstreams", () => {
      getAppContext().cooldowns.clear();
      getAppContext().cooldowns.set("minimax-m3", { until: Date.now() + 60000, reason: "rate-limit" });

      const r = route("flash");
      expect(r.upstream).not.toBeNull();
      expect(r.upstream!.name).toBe("opencode-go-new");
    });

    it("fails over when all tier upstreams are down", () => {
      getAppContext().cooldowns.clear();
      getAppContext().cooldowns.set("minimax-m3", { until: Date.now() + 60000, reason: "rate-limit" });
      getAppContext().cooldowns.set("opencode-go-new", { until: Date.now() + 60000, reason: "rate-limit" });

      const r = route("flash");
      // 默认拒绝 flash→Pro/code 静默掉档
      expect(r.upstream).toBeNull();
      expect(r.candidates.length).toBe(0);
      expect(r.is_fallback).toBe(true);
    });
  });

  describe("Session Affinity", () => {
    it("prefers affinity-bound upstream", () => {
      // First request: no affinity
      const r1 = route("flash");
      expect(r1.upstream!.name).toBe("minimax-m3");

      // Simulate affinity set for this session
      affinitySet("testkey", "opencode-go-new");

      // Second request: should prefer affinity
      const r2 = route("flash", "testkey");
      expect(r2.upstream!.name).toBe("opencode-go-new");
    });

    it("respects cooldown even with affinity", () => {
      affinitySet("testkey", "zhipu-glm-flash");

      getAppContext().cooldowns.clear();
      getAppContext().cooldowns.set("zhipu-glm-flash", { until: Date.now() + 60000, reason: "rate-limit" });

      const r = route("code", "testkey");
      // affinity upstream is cooled down → pick next ok one
      expect(r.upstream!.name).toBe("glm-free");
    });

    it("clears affinity on cooldown of bound upstream", () => {
      affinitySet("clearkey", "minimax-m3");
      affinityDelete("clearkey", "minimax-m3");

      const r = route("flash", "clearkey");
      // affinity was cleared, normal order
      expect(r.upstream!.name).toBe("minimax-m3");
    });
  });

  describe("affinityKey", () => {
    it("generates consistent keys from user messages", () => {
      const msgs = [{ role: "user", content: "hello world" }];
      const k1 = affinityKey(msgs);
      const k2 = affinityKey(msgs);
      expect(k1).toBe(k2);
    });

    it("returns null for empty messages", () => {
      expect(affinityKey([])).toBeNull();
      expect(affinityKey(null)).toBeNull();
    });

    it("extracts content from array messages", () => {
      const msgs = [{ role: "user", content: [{ type: "text", text: "hi" }] }];
      const k = affinityKey(msgs);
      expect(k).toBeTruthy();
    });

    it("prefers x-session-id header over messages", () => {
      const msgs = [{ role: "user", content: "hello" }];
      const k1 = affinityKey(msgs, { headers: { "x-session-id": "sess-abc" } });
      const k2 = affinityKey([{ role: "user", content: "other" }], { headers: { "x-session-id": "sess-abc" } });
      expect(k1).toBe(k2);
      expect(k1!.startsWith("hdr:")).toBe(true);
    });

    it("stable on system+first user; ignores later user turns", () => {
      const sys = "You are helpful.";
      const k1 = affinityKey(
        [{ role: "user", content: "first" }, { role: "assistant", content: "ok" }, { role: "user", content: "second" }],
        { system: sys },
      );
      const k2 = affinityKey(
        [{ role: "user", content: "first" }, { role: "assistant", content: "ok" }, { role: "user", content: "third turn" }],
        { system: sys },
      );
      expect(k1).toBe(k2);
      const k3 = affinityKey([{ role: "user", content: "other first" }], { system: sys });
      expect(k3).not.toBe(k1);
    });

    it("pinPaid keeps paid first when free recovers", () => {
      _clearAffinityForTest();
      const paid = {
        name: "opencode-go-paid-flash",
        base_url: "https://opencode.ai/zen/go/v1",
        api_key: "sk",
        tier: "flash" as const,
        tier_priority: 80,
        models: ["flash" as const],
        upstream_model: "deepseek-v4-flash",
        free: false,
        billing: "opencode-go",
      };
      const free = {
        name: "opencode-go-a",
        base_url: "https://opencode.ai/zen/v1",
        api_key: "sk",
        tier: "flash" as const,
        tier_priority: 1,
        models: ["flash" as const],
        upstream_model: "deepseek-v4-flash-free",
        free: true,
        billing: "zen-free",
      };
      writeFileSync(TEST_FILE, JSON.stringify([free, paid], null, 2));
      resetConfig();
      loadConfig(TEST_FILE);
      affinitySet("pin-sess", paid.name, { pinPaid: true });
      const r = route("flash", "pin-sess");
      expect(r.upstream!.name).toBe(paid.name);
      expect(r.candidates[0]!.name).toBe(paid.name);
    });
  });

  describe("resolveRequestTier + fair RR", () => {
    it("respects explicit pro/flash/code model, else port default", () => {
      expect(resolveRequestTier("pro", "flash")).toBe("pro");
      expect(resolveRequestTier("loop/code", "flash")).toBe("code");
      expect(resolveRequestTier("claude-opus", "flash")).toBe("flash");
      expect(resolveRequestTier(undefined, "code")).toBe("code");
    });

    it("round-robins equal priority peers with close scores", () => {
      const peers: UpstreamConfig[] = [
        {
          name: "peer-a", base_url: "https://a/v1", api_key: "sk",
          tier: "flash", tier_priority: 1, models: ["flash"], upstream_model: "m",
        },
        {
          name: "peer-b", base_url: "https://b/v1", api_key: "sk",
          tier: "flash", tier_priority: 1, models: ["flash"], upstream_model: "m",
        },
      ];
      writeFileSync(TEST_FILE, JSON.stringify(peers, null, 2));
      resetConfig();
      loadConfig(TEST_FILE);
      _resetFairCursorForTest();
      const names = [route("flash").upstream!.name, route("flash").upstream!.name, route("flash").upstream!.name, route("flash").upstream!.name];
      expect(new Set(names).size).toBe(2);
      expect(names.filter(n => n === "peer-a").length).toBe(2);
      expect(names.filter(n => n === "peer-b").length).toBe(2);
    });

    it("affinityDeleteByUpstream clears bindings", () => {
      affinitySet("k1", "minimax-m3");
      affinityDeleteByUpstream("minimax-m3");
      expect(affinityGet("k1", "minimax-m3")).toBeNull();
    });
  });
});
