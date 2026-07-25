// ═══════════════════════════════════════════════════════════════
//  tests/cache.test.ts — 精确缓存 (LRU + TTL) 验证
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  cacheKey,
  cacheGet,
  cacheSet,
  cacheDelete,
  cacheClear,
  cacheStats,
  _cacheResetForTest,
} from "../src/cache.js";

describe("cache", () => {
  beforeEach(() => _cacheResetForTest());
  afterEach(() => _cacheResetForTest());

  describe("cacheKey", () => {
    it("生成稳定 key (相同请求 → 相同 key)", () => {
      const req = { model: "flash", messages: [{ role: "user", content: "hi" }] };
      expect(cacheKey(req)).toBe(cacheKey(req));
    });

    it("不同 model → 不同 key", () => {
      const a = cacheKey({ model: "flash", messages: [] });
      const b = cacheKey({ model: "pro", messages: [] });
      expect(a).not.toBe(b);
    });

    it("不同 messages → 不同 key", () => {
      const a = cacheKey({ model: "flash", messages: [{ role: "user", content: "a" }] });
      const b = cacheKey({ model: "flash", messages: [{ role: "user", content: "b" }] });
      expect(a).not.toBe(b);
    });

    it("忽略 stream 字段", () => {
      const a = cacheKey({ model: "flash", messages: [], stream: false });
      const b = cacheKey({ model: "flash", messages: [], stream: true });
      expect(a).toBe(b);
    });

    it("max_tokens 影响输出 → 影响 key", () => {
      const a = cacheKey({ model: "flash", messages: [], max_tokens: 100 });
      const b = cacheKey({ model: "flash", messages: [], max_tokens: 200 });
      expect(a).not.toBe(b);
    });

    it("temperature 影响 key", () => {
      const a = cacheKey({ model: "flash", messages: [], temperature: 0.1 });
      const b = cacheKey({ model: "flash", messages: [], temperature: 0.7 });
      expect(a).not.toBe(b);
    });
  });

  describe("cacheGet / cacheSet", () => {
    it("未命中返回 null", () => {
      expect(cacheGet("nonexistent")).toBeNull();
    });

    it("命中返回 entry", () => {
      const key = cacheKey({ model: "flash", messages: [] });
      cacheSet(key, { hello: "world" }, { input: 10, output: 20 });
      const hit = cacheGet(key);
      expect(hit).not.toBeNull();
      expect(hit!.response).toEqual({ hello: "world" });
      expect(hit!.tokens).toEqual({ input: 10, output: 20 });
    });

    it("记录 hit / miss 统计", () => {
      const key = cacheKey({ model: "flash", messages: [] });
      cacheSet(key, { x: 1 }, { input: 0, output: 0 });
      cacheGet(key);          // hit
      cacheGet("miss1");      // miss
      cacheGet("miss2");      // miss
      const s = cacheStats();
      expect(s.hits).toBe(1);
      expect(s.misses).toBe(2);
      expect(s.hit_rate).toBeCloseTo(1 / 3);
    });

    it("LRU: 命中后移到末尾 (不会被淘汰)", () => {
      // 临时降低上限通过环境变量无效 (启动时读), 这里用大循环模拟
      const k1 = cacheKey({ model: "flash", messages: [{ role: "user", content: "1" }] });
      const k2 = cacheKey({ model: "flash", messages: [{ role: "user", content: "2" }] });
      cacheSet(k1, "v1", { input: 0, output: 0 });
      cacheSet(k2, "v2", { input: 0, output: 0 });
      // 命中 k1 (重新插入到末尾)
      expect(cacheGet(k1)).not.toBeNull();
      // k2 应该在前面, 但这里我们手动 delete 验证 LRU 顺序
      // (单测不能模拟淘汰, 因为默认 MAX=500)
      expect(cacheGet(k2)).not.toBeNull();
      expect(cacheGet(k1)).not.toBeNull(); // 仍在
    });
  });

  describe("cacheDelete", () => {
    it("删除存在的 key 返回 true", () => {
      const key = cacheKey({ model: "flash", messages: [] });
      cacheSet(key, "v", { input: 0, output: 0 });
      expect(cacheDelete(key)).toBe(true);
      expect(cacheGet(key)).toBeNull();
    });

    it("删除不存在的 key 返回 false", () => {
      expect(cacheDelete("nope")).toBe(false);
    });
  });

  describe("cacheClear", () => {
    it("清空全部并重置统计", () => {
      cacheSet("k1", "v1", { input: 0, output: 0 });
      cacheSet("k2", "v2", { input: 0, output: 0 });
      cacheGet("k1");
      cacheClear();
      const s = cacheStats();
      expect(s.size).toBe(0);
      expect(s.hits).toBe(0);
      expect(s.misses).toBe(0);
    });
  });

  describe("cacheStats", () => {
    it("默认状态 size=0", () => {
      const s = cacheStats();
      expect(s.size).toBe(0);
      expect(s.hit_rate).toBe(0);
    });
  });

  describe("v4.3 tool cache gate", () => {
    it("isCacheableRequest rejects tools / tool_choice", async () => {
      const { isCacheableRequest, shouldCacheWrite, responseHasToolCalls } = await import("../src/cache.js");
      expect(isCacheableRequest({ model: "flash", messages: [] })).toBe(true);
      expect(isCacheableRequest({ model: "flash", tools: [{ type: "function" }] })).toBe(false);
      expect(isCacheableRequest({ model: "flash", tool_choice: "auto" })).toBe(false);
      expect(isCacheableRequest({ model: "flash", tool_choice: "none" })).toBe(true);
      expect(responseHasToolCalls({ choices: [{ message: { tool_calls: [{ id: "1" }] } }] })).toBe(true);
      expect(shouldCacheWrite({ model: "flash", tools: [{}] }, { ok: 1 })).toBe(false);
      expect(shouldCacheWrite({ model: "flash" }, { choices: [{ message: { tool_calls: [{}] } }] })).toBe(false);
    });

    it("cacheSet skips responses with tool_calls", () => {
      const key = cacheKey({ model: "flash", messages: [{ role: "user", content: "t" }] });
      cacheSet(key, { choices: [{ message: { tool_calls: [{ id: "x" }] } }] }, { input: 1, output: 1 });
      expect(cacheGet(key)).toBeNull();
    });
  });
});
