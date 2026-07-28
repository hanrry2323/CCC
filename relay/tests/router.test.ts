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
    name: "opencode-go-paid-flash",
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-go-paid",
    tier: "flash",
    tier_priority: 1,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
  },
  {
    name: "opencode-go-paid-flash-b",
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-go-paid-b",
    tier: "flash",
    tier_priority: 2,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
    enabled: false,
  },
  {
    name: "claude-opus",
    base_url: "https://api.anthropic.com/v1",
    api_key: "sk-anthropic",
    tier: "pro",
    tier_priority: 1,
    models: ["pro"],
    upstream_model: "claude-opus-4",
    enabled: false,
  },
  {
    name: "code-idle",
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-code",
    tier: "code",
    tier_priority: 1,
    models: ["code"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
    enabled: false,
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
    it("returns the sole enabled paid flash upstream", () => {
      const r = route("flash");
      expect(r.upstream).not.toBeNull();
      expect(r.upstream!.name).toBe("opencode-go-paid-flash");
      expect(r.candidates.length).toBe(1);
      expect(r.is_fallback).toBe(false);
    });

    it("falls back flash when code tier empty/disabled", () => {
      const r = route("code");
      expect(r.upstream!.name).toBe("opencode-go-paid-flash");
      expect(r.is_fallback).toBe(true);
    });

    it("clears soft-cool when sole flash key cooled", () => {
      getAppContext().cooldowns.clear();
      getAppContext().cooldowns.set("opencode-go-paid-flash", { until: Date.now() + 60000, reason: "rate-limit" });

      const r = route("flash");
      // 单钥：清冷却直出，禁止 short-cool bypass 空转
      expect(r.upstream).not.toBeNull();
      expect(r.upstream!.name).toBe("opencode-go-paid-flash");
      expect(r.is_fallback).toBe(false);
      expect(getAppContext().cooldowns.has("opencode-go-paid-flash")).toBe(false);
    });
  });

  describe("Session Affinity", () => {
    it("prefers affinity-bound upstream", () => {
      const r1 = route("flash");
      expect(r1.upstream!.name).toBe("opencode-go-paid-flash");

      affinitySet("testkey", "opencode-go-paid-flash");
      const r2 = route("flash", "testkey");
      expect(r2.upstream!.name).toBe("opencode-go-paid-flash");
    });

    it("affinity sticky to sole paid key", () => {
      _clearAffinityForTest();
      affinitySet("pin-sess", "opencode-go-paid-flash");
      const r = route("flash", "pin-sess");
      expect(r.upstream!.name).toBe("opencode-go-paid-flash");
      expect(r.candidates[0]!.name).toBe("opencode-go-paid-flash");
    });

    it("clears affinity on delete", () => {
      affinitySet("clearkey", "opencode-go-paid-flash");
      affinityDelete("clearkey", "opencode-go-paid-flash");

      const r = route("flash", "clearkey");
      expect(r.upstream!.name).toBe("opencode-go-paid-flash");
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
      affinitySet("k1", "opencode-go-paid-flash");
      affinityDeleteByUpstream("opencode-go-paid-flash");
      expect(affinityGet("k1", "opencode-go-paid-flash")).toBeNull();
    });
  });
});
