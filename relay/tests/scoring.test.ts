// ═══════════════════════════════════════════════════════════════
//  tests/scoring.test.ts — 健康评分 + 指数退避
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach } from "vitest";
import {
  recordOutcome,
  getScore,
  getScoreRecord,
  getAllScores,
  backoffMultiplier,
  computeBackoffCooldown,
} from "../src/scoring.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { sc, cool, hlt, cls, usgIdx$ } from "../src/state.js";

beforeEach(() => {
  sc.clear();
  cool.clear();
  hlt.clear();
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

// ── recordOutcome / getScore ──

describe("recordOutcome / getScore", () => {
  it("冷启动返回初始分 0.8", () => {
    expect(getScore("unknown")).toBe(0.8);
  });

  it("连续成功 → EWMA 趋近 1.0", () => {
    for (let i = 0; i < 30; i++) recordOutcome("up-a", true);
    expect(getScore("up-a")).toBeCloseTo(1.0, 1);
  });

  it("连续失败 → EWMA 趋近 0.0", () => {
    for (let i = 0; i < 30; i++) recordOutcome("up-b", false);
    expect(getScore("up-b")).toBeCloseTo(0.0, 1);
  });

  it("成功立即清零 failStreak", () => {
    for (let i = 0; i < 5; i++) recordOutcome("up-c", false);
    expect(getScoreRecord("up-c")!.failStreak).toBe(5);
    recordOutcome("up-c", true);
    expect(getScoreRecord("up-c")!.failStreak).toBe(0);
  });

  it("混合场景 EWMA 渐进收敛", () => {
    // 10 失败, 10 成功 — 后期分应高于 0.5
    for (let i = 0; i < 10; i++) recordOutcome("up-d", false);
    for (let i = 0; i < 10; i++) recordOutcome("up-d", true);
    const final = getScore("up-d");
    expect(final).toBeGreaterThan(0.5);
    expect(final).toBeLessThan(0.8);
  });

  it("累计计数正确", () => {
    recordOutcome("up-e", true);
    recordOutcome("up-e", true);
    recordOutcome("up-e", false);
    recordOutcome("up-e", false);
    recordOutcome("up-e", false);
    const r = getScoreRecord("up-e")!;
    expect(r.totalSuccess).toBe(2);
    expect(r.totalFail).toBe(3);
    expect(r.failStreak).toBe(3);
  });

  it("成功时更新 lastSuccessTs", () => {
    const before = Date.now();
    recordOutcome("up-f", true);
    const r = getScoreRecord("up-f")!;
    expect(r.lastSuccessTs).toBeGreaterThanOrEqual(before);
  });
});

// ── backoffMultiplier ──

describe("backoffMultiplier", () => {
  it("streak=0 → 1×", () => {
    expect(backoffMultiplier(0)).toBe(1);
  });
  it("streak=1 → 2×", () => {
    expect(backoffMultiplier(1)).toBe(2);
  });
  it("streak=2 → 4×", () => {
    expect(backoffMultiplier(2)).toBe(4);
  });
  it("streak=3 → 8×", () => {
    expect(backoffMultiplier(3)).toBe(8);
  });
  it("streak=4 → 16× (cap)", () => {
    expect(backoffMultiplier(4)).toBe(16);
  });
  it("streak=5+ → cap 16×", () => {
    expect(backoffMultiplier(5)).toBe(16);
    expect(backoffMultiplier(20)).toBe(16);
  });
});

// ── computeBackoffCooldown (v3.7 EWMA 评分驱动) ──

describe("computeBackoffCooldown", () => {
  it("冷启动 (score=0.8) → 2×（给免费渠道更多恢复机会）", () => {
    expect(computeBackoffCooldown("new-up", 60, 3600)).toBe(120);
  });

  it("连续成功 (score≈1.0) → 1×（不惩罚）", () => {
    for (let i = 0; i < 30; i++) recordOutcome("good", true);
    expect(getScore("good")).toBeGreaterThan(0.9);
    expect(computeBackoffCooldown("good", 60, 3600)).toBe(60);
  });

  it("连续失败 (score≈0.0) → 16×（严重惩罚）", () => {
    for (let i = 0; i < 30; i++) recordOutcome("bad", false);
    expect(getScore("bad")).toBeLessThan(0.1);
    expect(computeBackoffCooldown("bad", 60, 3600)).toBe(960);
  });

  it("一次成功不会归零——EWMA 保守恢复", () => {
    for (let i = 0; i < 20; i++) recordOutcome("u1", false);
    const before = computeBackoffCooldown("u1", 60, 3600);
    recordOutcome("u1", true);
    const after = computeBackoffCooldown("u1", 60, 3600);
    // 一次成功只提升 EWMA 10%，不会从 16× 跳回 1×
    expect(after).toBeGreaterThanOrEqual(before / 2); // 不会疯狂跳水
    expect(after).toBeGreaterThan(60); // 不是 1×
  });

  it("遵守 maxSec 上限", () => {
    for (let i = 0; i < 30; i++) recordOutcome("u2", false);
    // 基数 120, score≈0 → mult=16 → 120×16=1920, cap=600
    expect(computeBackoffCooldown("u2", 120, 600)).toBe(600);
  });
});

// ── getAllScores ──

describe("getAllScores", () => {
  it("返回所有 upstream 的评分记录", () => {
    recordOutcome("a", true);
    recordOutcome("b", false);
    const all = getAllScores();
    expect(Object.keys(all).sort()).toEqual(["a", "b"]);
    expect(all["a"].totalSuccess).toBe(1);
    expect(all["b"].totalFail).toBe(1);
  });

  it("空 map 时返回空对象", () => {
    expect(getAllScores()).toEqual({});
  });
});

describe("score persistence", () => {
  it("persistScores / loadScores round-trip", async () => {
    const { persistScores, loadScores } = await import("../src/scoring.js");
    const file = "/tmp/test-scores-v43.json";
    recordOutcome("persist-a", true);
    recordOutcome("persist-a", true);
    recordOutcome("persist-b", false);
    persistScores(file);
    sc.clear();
    expect(getScore("persist-a")).toBe(0.8);
    loadScores(file);
    expect(getScoreRecord("persist-a")!.totalSuccess).toBe(2);
    expect(getScoreRecord("persist-b")!.totalFail).toBe(1);
  });
});
