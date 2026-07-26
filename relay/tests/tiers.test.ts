// ═══════════════════════════════════════════════════════════════
//  tests/tiers.test.ts — Tier 管理 + isUpstreamOk 验证
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach } from "vitest";
import { isUpstreamOk, getTierSummary, getTierBlockReason, TIER_PRIORITY } from "../src/tiers.js";
import { setAppContext, getAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import type { UpstreamConfig, TierId } from "../src/types.js";

const makeUpstream = (overrides: Partial<UpstreamConfig> = {}): UpstreamConfig => ({
  name: "test-up",
  base_url: "https://api.test.com/v1",
  api_key: "sk-test",
  tier: "flash" as TierId,
  tier_priority: 1,
  models: ["flash" as TierId],
  upstream_model: "test-model",
  ...overrides,
});

describe("tiers", () => {
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

  describe("isUpstreamOk", () => {
    it("returns true for a healthy upstream", () => {
      expect(isUpstreamOk(makeUpstream())).toBe(true);
    });

    it("returns false when api_key is missing", () => {
      expect(isUpstreamOk(makeUpstream({ api_key: "" }))).toBe(false);
    });

    it("returns false when in cooldown", () => {
      getAppContext().cooldowns.clear();
      getAppContext().cooldowns.set("test-up", { until: Date.now() + 60000, reason: "rate-limit" });
      expect(isUpstreamOk(makeUpstream())).toBe(false);
    });

    it("returns true when cooldown has expired", () => {
      getAppContext().cooldowns.clear();
      getAppContext().cooldowns.set("test-up", { until: Date.now() - 1000, reason: "rate-limit" });
      expect(isUpstreamOk(makeUpstream())).toBe(true);
    });

    it("getTierBlockReason aligns with isUpstreamOk", () => {
      expect(getTierBlockReason(makeUpstream({ api_key: "" }))).toBe("no_api_key");
      getAppContext().cooldowns.set("test-up", { until: Date.now() + 60000, reason: "rl" });
      expect(getTierBlockReason(makeUpstream())).toMatch(/^cooldown:/);
      expect(isUpstreamOk(makeUpstream())).toBe(false);
      getAppContext().cooldowns.clear();
      expect(isUpstreamOk(makeUpstream())).toBe(true);
    });
  });

  describe("getTierSummary", () => {
    it("summarizes tiers with upstream counts", () => {
      const pro: UpstreamConfig = makeUpstream({ name: "p1", tier: "pro", models: ["pro"], tier_priority: 1 });
      const flash: UpstreamConfig = makeUpstream({ name: "f1", tier: "flash", models: ["flash"], tier_priority: 1 });
      const code: UpstreamConfig = makeUpstream({ name: "c1", tier: "code", models: ["code"], tier_priority: 1 });

      const tierMap = new Map<TierId, UpstreamConfig[]>([
        ["pro", [pro]],
        ["flash", [flash]],
        ["code", [code]],
      ]);

      const summary = getTierSummary({ tiers: tierMap, all: [pro, flash, code] });
      expect(summary.length).toBe(3);
      expect(summary[0].id).toBe("pro");
      expect(summary[1].id).toBe("flash");
      expect(summary[2].id).toBe("code");
      expect(summary[0].upstreams).toBe(1);
      expect(summary[0].healthy).toBe(1);
    });
  });
});
