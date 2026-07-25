// ═══════════════════════════════════════════════════════════════
//  tests/auth.test.ts — 鉴权 + 配额检查（v3.6 新增覆盖）
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach } from "vitest";
import type { IncomingMessage } from "http";
import { cauth, cmay, todayStart } from "../src/auth.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { cls, usgIdx$, sc, cool, hlt } from "../src/state.js";

function makeReq(headers: Record<string, string>): IncomingMessage {
  return { headers } as unknown as IncomingMessage;
}

beforeEach(() => {
  cls.value = [];
  usgIdx$.client.clear();
  usgIdx$.upstream.clear();
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

describe("cauth", () => {
  it("缺 X-Client-Id/X-Client-Key → 返回 null", () => {
    expect(cauth(makeReq({}))).toBeNull();
    expect(cauth(makeReq({ "x-client-id": "u1" }))).toBeNull();
    expect(cauth(makeReq({ "x-client-key": "k1" }))).toBeNull();
  });

  it("未注册 id → null", () => {
    cls.value = [{ id: "u1", key: "k1" }];
    expect(cauth(makeReq({ "x-client-id": "u2", "x-client-key": "k1" }))).toBeNull();
  });

  it("key 不匹配 → null", () => {
    cls.value = [{ id: "u1", key: "k1" }];
    expect(cauth(makeReq({ "x-client-id": "u1", "x-client-key": "wrong" }))).toBeNull();
  });

  it("active=false → null", () => {
    cls.value = [{ id: "u1", key: "k1", active: false }];
    expect(cauth(makeReq({ "x-client-id": "u1", "x-client-key": "k1" }))).toBeNull();
  });

  it("合法 → 返回 AuthenticatedClient", () => {
    cls.value = [{ id: "u1", key: "k1", name: "Test" }];
    const r = cauth(makeReq({ "x-client-id": "u1", "x-client-key": "k1" }));
    expect(r).toEqual({ id: "u1", name: "Test", models: undefined });
  });

  it("超配额 → qe=true 标志", () => {
    cls.value = [{ id: "u1", key: "k1", quota: { daily_tokens: 100 } }];
    usgIdx$.client.set("u1", 200);
    usgIdx$.builtAt = Date.now(); // 避免懒重建
    const r = cauth(makeReq({ "x-client-id": "u1", "x-client-key": "k1" }));
    expect(r?.qe).toBe(true);
  });

  it("未超配额 → qe 字段缺失", () => {
    cls.value = [{ id: "u1", key: "k1", quota: { daily_tokens: 1000 } }];
    usgIdx$.client.set("u1", 50);
    usgIdx$.builtAt = Date.now();
    const r = cauth(makeReq({ "x-client-id": "u1", "x-client-key": "k1" }));
    expect(r?.qe).toBeUndefined();
  });
});

describe("cmay", () => {
  it("无 client 或 models 为空 → 允许所有", () => {
    expect(cmay(null, "flash")).toBe(true);
    expect(cmay({ id: "u" }, "flash")).toBe(true);
    expect(cmay({ id: "u", models: [] }, "flash")).toBe(true);
  });

  it("models 含 * → 允许所有", () => {
    expect(cmay({ id: "u", models: ["*"] }, "anything")).toBe(true);
  });

  it("models 含具体名称 → 匹配", () => {
    expect(cmay({ id: "u", models: ["flash"] }, "flash")).toBe(true);
    expect(cmay({ id: "u", models: ["flash"] }, "code")).toBe(false);
  });

  it("models 含通配符前缀 → 匹配", () => {
    expect(cmay({ id: "u", models: ["flash*"] }, "flash-mini")).toBe(true);
    expect(cmay({ id: "u", models: ["flash*"] }, "code")).toBe(false);
  });
});

describe("todayStart", () => {
  it("返回当天 00:00:00 时间戳", () => {
    const ts = todayStart();
    const d = new Date(ts);
    expect(d.getHours()).toBe(0);
    expect(d.getMinutes()).toBe(0);
    expect(d.getSeconds()).toBe(0);
  });
});