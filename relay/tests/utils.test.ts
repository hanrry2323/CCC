// ═══════════════════════════════════════════════════════════════
//  tests/utils.test.ts — classifyErr, cleanThink, normTools
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect } from "vitest";
import { classifyErr, normTools, cleanThink } from "../src/utils.js";

describe("classifyErr", () => {
  // ── 配额类（预期 quota: true）──

  it("detects quota errors (Chinese)", () => {
    const r = classifyErr("额度用完");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
    expect(r!.sec).toBe(300);
  });

  it("detects quota errors (English)", () => {
    const r = classifyErr("insufficient quota");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  it("detects quota exceeded without rate prefix", () => {
    const r = classifyErr("quota exceeded");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  it("detects usage limit reached", () => {
    const r = classifyErr("Monthly usage limit reached. Resets in 5 days.");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  it("detects insufficient balance", () => {
    const r = classifyErr("insufficient balance");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  it("detects balance is zero", () => {
    const r = classifyErr("balance is zero");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  it("detects 余额不足", () => {
    const r = classifyErr("余额不足，请充值");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  // ── 限流类（预期 quota: false）──

  it("detects rate limit errors (Chinese)", () => {
    const r = classifyErr("访问量过大");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(false);
    expect(r!.sec).toBe(60);
  });

  it("detects rate limit errors (English)", () => {
    const r = classifyErr("rate limit exceeded");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(false);
  });

  // ── 回归测试：宽泛词不应再误判为配额 ──

  it("does not classify rate-limit-with-quota-word as quota", () => {
    // "请求额度超限" 是限流，不应被判为配额耗尽
    const r = classifyErr("请求额度超限，请稍后重试");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(false); // 限流，非配额
    expect(r!.sec).toBe(60);
  });

  it("does not classify exceeded-timeout as quota", () => {
    const r = classifyErr("Request exceeded timeout");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(false); // timeout → 网络类短冷却，非配额
    expect(r!.sec).toBe(60);
  });

  it("does not classify exceeded-token as quota", () => {
    const r = classifyErr("exceeded the maximum allowed tokens");
    expect(r).toBeNull(); // token 限制，非配额
  });

  it("does not classify exceeded-context as quota", () => {
    const r = classifyErr("exceeded the context window");
    expect(r).toBeNull(); // 上下文窗口，非配额
  });

  it("does not classify load-balance as quota", () => {
    const r = classifyErr("load balance error");
    // "balance" 被移除，不应命中配额
    expect(r?.quota).toBeFalsy();
  });

  it("does not classify insufficient-permissions as quota", () => {
    const r = classifyErr("insufficient permissions");
    // "insufficient" 被移除，不应命中配额
    expect(r?.quota).toBeFalsy();
  });

  // ── 认证/服务故障类 ──

  it("detects auth errors", () => {
    const r = classifyErr("invalid api key");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(false);
    expect(r!.sec).toBe(300);
  });

  it("detects upstream provider errors", () => {
    const r = classifyErr("Error from provider (Console Go): Upstream request failed");
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(false);
    expect(r!.sec).toBe(120);
  });

  // ── 边界情况 ──

  it("returns null for unknown errors", () => {
    expect(classifyErr("random error message")).toBeNull();
  });

  it("handles object input by extracting .message field", () => {
    const r = classifyErr({ message: "额度用完" });
    expect(r).not.toBeNull();
    expect(r!.quota).toBe(true);
  });

  it("returns null for empty input", () => {
    expect(classifyErr(null)).toBeNull();
    expect(classifyErr("")).toBeNull();
  });

  it("rate exceeded is rate-limit not quota", () => {
    // "rate" exclusion on exceeded line ensures this is NOT quota
    const r = classifyErr("rate exceeded");
    expect(r?.quota).toBeFalsy();
  });
});

describe("normTools", () => {
  it("normalizes Anthropic tools to OpenAI format", () => {
    const tools = [
      { name: "get_weather", description: "Get weather", input_schema: { type: "object", properties: {} } },
    ];
    const result = normTools(tools);
    expect(result.length).toBe(1);
    expect(result[0].function.name).toBe("get_weather");
    expect(result[0].function.parameters?.type).toBe("object");
  });

  it("filters tools without name", () => {
    const tools = [{ name: "", description: "no name" }] as any;
    expect(normTools(tools).length).toBe(0);
  });

  it("fixes null schema type", () => {
    const tools = [{ name: "test", parameters: { type: "null" } }] as any;
    const result = normTools(tools);
    expect(result[0].function.parameters?.type).toBe("object");
  });
});

describe("cleanThink", () => {
  it("removes think tags from content", () => {
    const input = "Hello <think>internal thought</think> World";
    expect(cleanThink(input)).toBe("Hello  World");
  });

  it("handles content without think tags", () => {
    expect(cleanThink("Hello World")).toBe("Hello World");
  });

  it("handles empty input", () => {
    expect(cleanThink("")).toBe("");
  });
});
