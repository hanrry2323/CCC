// ═══════════════════════════════════════════════════════════════
//  tests/translator-anthropic.test.ts — 协议转换验证
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect } from "vitest";
import { anthropicToOpenAI, openAIChunkToAnthropicSSE, createAnthropicSSEState } from "../src/translator/anthropic.js";
import type { AnthropicRequest, OpenAIChunk } from "../src/types.js";

describe("anthropicToOpenAI", () => {
  it("converts basic message", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [{ role: "user", content: "Hello" }],
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "minimax-m3");
    expect(result.model).toBe("minimax-m3");
    expect(result.messages.length).toBe(1);
    expect(result.messages[0].content).toBe("Hello");
  });

  it("converts system prompt", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [{ role: "user", content: "Hi" }],
      system: "You are helpful",
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "test");
    expect(result.messages.length).toBe(2);
    expect(result.messages[0].role).toBe("system");
    expect(result.messages[0].content).toBe("You are helpful");
  });

  it("guards against empty messages", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [],
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "test");
    expect(result.messages.length).toBe(1);
    expect(result.messages[0].content).toBe("hi");
  });

  it("converts tool_choice", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [{ role: "user", content: "Hi" }],
      tools: [{ name: "get_weather" }],
      tool_choice: { type: "any" },
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "test");
    expect(result.tool_choice).toBe("required");
  });

  it("converts text+image message to OpenAI content array", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [{
        role: "user",
        content: [
          { type: "text", text: "描述这张图" },
          { type: "image", source: { type: "base64", media_type: "image/png", data: "abc123" } },
        ],
      }],
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "test");
    expect(result.messages.length).toBe(1);
    const content = result.messages[0].content;
    expect(Array.isArray(content)).toBe(true);
    const arr = content as Record<string, unknown>[];
    expect(arr[0].type).toBe("text");
    expect((arr[0] as any).text).toBe("描述这张图");
    expect(arr[1].type).toBe("image_url");
    const iu = (arr[1] as any).image_url;
    expect(iu.url).toMatch(/^data:image\/png;base64,abc123$/);
  });

  it("converts image-only message", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [{
        role: "user",
        content: [
          { type: "image", source: { type: "base64", media_type: "image/jpeg", data: "xyz" } },
        ],
      }],
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "test");
    expect(result.messages.length).toBe(1);
    const content = result.messages[0].content;
    expect(Array.isArray(content)).toBe(true);
    const arr = content as Record<string, unknown>[];
    expect(arr[0].type).toBe("image_url");
    const iu = (arr[0] as any).image_url;
    expect(iu.url).toMatch(/^data:image\/jpeg;base64,xyz$/);
    expect(iu.detail).toBe("auto");
  });

  it("enables OpenCode Go prompt cache fields for system/tools sessions", () => {
    const req: AnthropicRequest = {
      model: "flash",
      messages: [
        { role: "user", content: "a" },
        { role: "assistant", content: "b" },
        { role: "user", content: "c" },
      ],
      system: "You are helpful",
      tools: [{ name: "t", description: "d", input_schema: { type: "object" } }],
      max_tokens: 100,
    };
    const result = anthropicToOpenAI(req, "deepseek-v4-flash", { promptCacheKey: "sess-abc" }) as any;
    expect(result.enable_prompt_cache).toBe(true);
    expect(result.prompt_cache_retention).toBe("24h");
    expect(result.prompt_cache_key).toBe("sess-abc");
    expect(result.messages[0].role).toBe("system");
    expect((result.messages[0] as any).cache_control?.type).toBe("ephemeral");
  });
});

describe("openAIChunkToAnthropicSSE", () => {
  it("converts text chunk", () => {
    const state = createAnthropicSSEState();
    const chunk: OpenAIChunk = {
      choices: [{ index: 0, delta: { content: "Hello" }, finish_reason: null }],
    };
    const events = openAIChunkToAnthropicSSE(chunk, state);
    expect(events.length).toBeGreaterThanOrEqual(2);
    // First event should be content_block_start
    expect(events[0].type).toBe("content_block_start");
  });

  it("handles finish_reason", () => {
    const state = createAnthropicSSEState();
    state.textOpen = true;
    state.textIndex = 0;
    const chunk: OpenAIChunk = {
      choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
    };
    const events = openAIChunkToAnthropicSSE(chunk, state);
    expect(events.some(e => e.type === "content_block_stop")).toBe(true);
    expect(events.some(e => e.type === "message_delta")).toBe(true);
  });

  it("assigns sequential content block indices", () => {
    const state = createAnthropicSSEState();
    // First text chunk
    openAIChunkToAnthropicSSE(
      { choices: [{ index: 0, delta: { content: "Hello" }, finish_reason: null }] },
      state,
    );
    expect(state.textIndex).toBe(0);
    expect(state.nextIndex).toBe(1);
  });
});
