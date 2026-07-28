// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — Anthropic ↔ OpenAI 协议转换
//  v3.5 重写: 由 v3.4 的内嵌函数转为独立模块,供 protocols/messages.ts 调用
// ═══════════════════════════════════════════════════════════════

import type {
  AnthropicRequest,
  AnthropicMessage,
  ContentBlock,
  AnthropicSSEEvent,
  OpenAIChatRequest,
  ChatMessage,
  OpenAIChunk,
  OpenAIUsage,
} from "../types.js";
import { normTools, stripThinkingDirectives } from "../utils.js";

// ── Anthropic → OpenAI Chat (请求方向) ──

export function anthropicToOpenAI(
  req: AnthropicRequest,
  upstreamModel: string,
  opts?: { promptCacheKey?: string | null },
): OpenAIChatRequest {
  const sysStr = extractSystemString(req.system);
  const sysMsg: ChatMessage | null = sysStr
    ? { role: "system", content: sysStr, cache_control: { type: "ephemeral", ttl: "24h" } }
    : null;
  const sys = sysMsg ? [sysMsg] : [];
  const msgs: ChatMessage[] = (req.messages || []).flatMap(anthropicMsgToOpenAI);
  stripStaleCacheControl(msgs);
  stampTailCacheControl(msgs);
  const finalMsgs = [...sys, ...msgs];
  if (finalMsgs.length === 0) finalMsgs.push({ role: "user", content: "hi" });

  const o: OpenAIChatRequest = {
    model: upstreamModel,
    messages: finalMsgs,
    max_tokens: req.max_tokens || 4096,
    temperature: req.temperature,
    top_p: req.top_p,
    stop: req.stop_sequences,
    stream: req.stream || false,
  };

  // 付费 Go：每轮都钉缓存（含首轮单条 user）
  (o as any).enable_prompt_cache = true;
  (o as any).prompt_cache_retention = "24h";
  const ck = (opts?.promptCacheKey || "").trim();
  if (ck) (o as any).prompt_cache_key = ck.slice(0, 64);

  if (o.stream) o.stream_options = { include_usage: true };
  if (req.tools?.length) {
    o.tools = normTools(req.tools);
    const tools = o.tools as Array<Record<string, unknown>>;
    if (tools.length) tools[tools.length - 1]!.cache_control = { type: "ephemeral", ttl: "24h" };
  }
  if (req.tool_choice && req.tool_choice.type !== "auto") {
    o.tool_choice = req.tool_choice.type === "any"
      ? "required" as const
      : req.tool_choice.type === "tool"
        ? { type: "function" as const, function: { name: req.tool_choice.name! } }
        : "none" as const;
  }

  return o;
}

function stripStaleCacheControl(msgs: ChatMessage[]): void {
  for (const m of msgs) {
    if (m && typeof m === "object" && "cache_control" in m) {
      delete (m as any).cache_control;
    }
  }
}

function stampTailCacheControl(msgs: ChatMessage[]): void {
  let left = 2;
  for (let i = msgs.length - 1; i >= 0 && left > 0; i--) {
    const m = msgs[i]!;
    if (m.role !== "user" && m.role !== "assistant") continue;
    m.cache_control = { type: "ephemeral", ttl: "24h" };
    left -= 1;
  }
}

function extractSystemString(system: string | ContentBlock[] | undefined): string {
  if (!system) return "";
  let raw = "";
  if (typeof system === "string") raw = system;
  else if (Array.isArray(system)) raw = system.map(p => (typeof p === "string" ? p : p.text || "")).join("");
  else return "";
  return stripThinkingDirectives(raw);
}

/** 检测 Anthropic 请求中是否包含 cache_control 断点 */
function detectCacheControl(req: AnthropicRequest): boolean {
  const system = req.system;
  if (Array.isArray(system)) {
    for (const block of system) {
      if (typeof block === "object" && block.cache_control) return true;
    }
  }
  for (const msg of (req.messages || [])) {
    const content = msg.content;
    if (Array.isArray(content)) {
      for (const block of content) {
        if (typeof block === "object" && (block as ContentBlock).cache_control) return true;
      }
    }
  }
  for (const t of (req.tools || []) as Array<{ cache_control?: unknown }>) {
    if (t && t.cache_control) return true;
  }
  return false;
}

function anthropicMsgToOpenAI(m: AnthropicMessage): ChatMessage[] {
  if (!m || !m.role) return [];

  if (m.role === "assistant" && m.content) {
    const parts = Array.isArray(m.content) ? m.content : [{ type: "text" as const, text: String(m.content) }];
    const texts = parts.filter(p => p.type === "text").map(p => p.text || "").join("");
    const tools = parts.filter(p => p.type === "tool_use");
    const thinks = parts.filter(p => p.type === "redacted_thinking");
    const rc = thinks.map(p => p.data || "").join("");

    const msg: ChatMessage = { role: "assistant", content: texts || "" };
    if (rc) (msg as any).reasoning_content = rc;
    if (tools.length) {
      msg.tool_calls = tools.map(t => ({
        id: t.id!,
        type: "function" as const,
        function: { name: t.name!, arguments: JSON.stringify(t.input) },
      }));
    }
    return [msg];
  }

  if (m.role === "user") {
    const parts = Array.isArray(m.content) ? m.content : [{ type: "text" as const, text: String(m.content) }];
    const toolResults = parts.filter(p => p.type === "tool_result");
    if (toolResults.length) {
      return toolResults.map(t => ({
        role: "tool" as const,
        tool_call_id: t.tool_use_id || "?",
        content: typeof t.content === "string" ? t.content : JSON.stringify(t.content),
      }));
    }
    // Check for image blocks
    const imgs = parts.filter(p => p.type === "image");
    if (imgs.length > 0) {
      const content: Record<string, unknown>[] = [];
      const txt = parts.filter(p => p.type === "text" || (p as any).type === "content")
        .map(p => (p as any).text || (p as any).content || "")
        .join("");
      if (txt) content.push({ type: "text", text: txt });
      for (const img of imgs) {
        const src = img.source || { type: "base64", media_type: "image/png", data: "" };
        content.push({
          type: "image_url",
          image_url: { url: `data:${src.media_type};base64,${src.data}`, detail: "auto" },
        });
      }
      return [{ role: "user", content }];
    }
    const txt = parts.filter(p => p.type === "text" || (p as any).type === "content")
      .map(p => (p as any).text || (p as any).content || "")
      .join("");
    return txt.length ? [{ role: "user", content: txt }] : [{ role: "user", content: "[empty]" }];
  }

  // Tool role messages
  if (m.role === "tool") {
    return [{
      role: "tool" as const,
      tool_call_id: m.tool_use_id || "?",
      content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
    }];
  }

  return [m as unknown as ChatMessage];
}

// ── OpenAI Chat SSE → Anthropic SSE (响应方向, stateful) ──

export interface AnthropicSSEState {
  nextIndex: number;
  textOpen: boolean;
  textIndex: number;
  thinkingOpen: boolean;
  thinkingIndex: number;
  toolBlocks: Record<number, {
    index: number;
    name: string;
    id: string;
    closed: boolean;
    started: boolean;
    pendingArgs: string;
  }>;
}

export function createAnthropicSSEState(): AnthropicSSEState {
  return {
    nextIndex: 0,
    textOpen: false,
    textIndex: -1,
    thinkingOpen: false,
    thinkingIndex: -1,
    toolBlocks: {},
  };
}

export function openAIChunkToAnthropicSSE(
  chunk: OpenAIChunk,
  state: AnthropicSSEState,
): AnthropicSSEEvent[] {
  const ch = chunk.choices?.[0];
  if (!ch) return [];

  const evs: AnthropicSSEEvent[] = [];
  const fr = ch.finish_reason;
  const dc = ch.delta?.content;
  const dr = (ch.delta as any)?.reasoning_content || (ch.delta as any)?.reasoning;

  // reasoning_content → thinking block (deepseek/MiniMax 思考过程)
  if (dr) {
    if (!state.thinkingOpen) {
      // 切换到 thinking 前先关掉 text block (一般不会同时开, 但保险)
      if (state.textOpen) {
        evs.push({ type: "content_block_stop", index: state.textIndex });
        state.textOpen = false;
      }
      state.thinkingIndex = state.nextIndex++;
      state.thinkingOpen = true;
      evs.push({
        type: "content_block_start",
        index: state.thinkingIndex,
        content_block: { type: "thinking", thinking: "" },
      });
    }
    evs.push({
      type: "content_block_delta",
      index: state.thinkingIndex,
      delta: { type: "thinking_delta", thinking: dr } as any,
    });
  }

  if (dc) {
    // 从 thinking 切到 text: 先关 thinking block
    if (state.thinkingOpen) {
      evs.push({ type: "content_block_stop", index: state.thinkingIndex });
      state.thinkingOpen = false;
    }
    if (!state.textOpen) {
      state.textIndex = state.nextIndex++;
      state.textOpen = true;
      evs.push({
        type: "content_block_start",
        index: state.textIndex,
        content_block: { type: "text", text: "" },
      });
    }
    evs.push({
      type: "content_block_delta",
      index: state.textIndex,
      delta: { type: "text_delta", text: dc },
    });
  }

  if (ch.delta?.tool_calls) {
    // 开 tool block 前先关 thinking (避免 block 顺序交叉)
    if (state.thinkingOpen) {
      evs.push({ type: "content_block_stop", index: state.thinkingIndex });
      state.thinkingOpen = false;
    }
    if (!state.toolBlocks) state.toolBlocks = {};
    for (const tc of ch.delta.tool_calls) {
      const tIdx = tc.index ?? 0;
      if (!state.toolBlocks[tIdx]) {
        state.toolBlocks[tIdx] = {
          index: state.nextIndex++,
          name: "",
          id: tc.id || "",
          closed: false,
          started: false,
          pendingArgs: "",
        };
      }
      const blk = state.toolBlocks[tIdx];
      if (tc.id && !blk.id) blk.id = tc.id;
      if (tc.function?.name && !blk.name) blk.name = tc.function.name;

      if (tc.function?.arguments) {
        if (blk.started) {
          evs.push({
            type: "content_block_delta",
            index: blk.index,
            delta: { type: "input_json_delta", partial_json: tc.function.arguments },
          });
        } else {
          blk.pendingArgs += tc.function.arguments;
        }
      }

      if (!blk.started && blk.name) {
        evs.push({
          type: "content_block_start",
          index: blk.index,
          content_block: { type: "tool_use", id: blk.id, name: blk.name, input: {} },
        });
        blk.started = true;
        if (blk.pendingArgs) {
          evs.push({
            type: "content_block_delta",
            index: blk.index,
            delta: { type: "input_json_delta", partial_json: blk.pendingArgs },
          });
          blk.pendingArgs = "";
        }
      }
    }
  }

  if (fr && fr !== "null") {
    if (state.thinkingOpen) {
      evs.push({ type: "content_block_stop", index: state.thinkingIndex });
      state.thinkingOpen = false;
    }
    if (state.textOpen) {
      evs.push({ type: "content_block_stop", index: state.textIndex });
      state.textOpen = false;
    }
    if (state.toolBlocks) {
      for (const k in state.toolBlocks) {
        const b = state.toolBlocks[k];
        if (!b.closed) {
          evs.push({ type: "content_block_stop", index: b.index });
          b.closed = true;
        }
      }
    }
    const stopReason = fr === "tool_calls" ? "tool_use" as const
      : fr === "length" ? "max_tokens" as const
      : "end_turn" as const;
    evs.push({
      type: "message_delta",
      delta: { stop_reason: stopReason, stop_sequence: null },
      usage: { output_tokens: ch.usage?.completion_tokens || 0 },
    });
  }

  return evs;
}

// ── OpenAI Chat Response → Anthropic Response (非流式) ──

export function openAIResponseToAnthropic(
  choices: OpenAIChunk["choices"],
  usage?: OpenAIUsage,
  model?: string,
): Record<string, unknown> {
  const ch = choices?.[0];
  if (!ch) return {};
  const msg = ch.message || ch.delta || {};

  const content: ContentBlock[] = [];
  if ((msg as any).reasoning_content) {
    content.push({ type: "redacted_thinking", data: (msg as any).reasoning_content });
  }
  if (msg.content) {
    content.push({ type: "text", text: msg.content });
  }

  const ar: Record<string, unknown> = {
    id: "msg_" + Date.now(),
    type: "message",
    role: "assistant",
    content,
    model: model || "unknown",
    stop_reason: ch.finish_reason === "tool_calls" ? "tool_use"
      : ch.finish_reason === "length" ? "max_tokens"
      : "end_turn",
    stop_sequence: null,
    usage: {
      input_tokens: Math.max(0, (usage?.prompt_tokens || 0) - (usage?.prompt_tokens_details?.cached_tokens || 0)),
      cache_read_input_tokens: usage?.prompt_tokens_details?.cached_tokens || 0,
      output_tokens: usage?.completion_tokens || 0,
    },
  };

  return ar;
}

/** OpenAI Chat 请求注入 Go prompt cache 字段（:4002 / OpenCode） */
export function applyOpenAIPromptCache(
  body: Record<string, unknown>,
  opts?: { promptCacheKey?: string | null },
): void {
  (body as any).enable_prompt_cache = true;
  (body as any).prompt_cache_retention = "24h";
  const ck = (opts?.promptCacheKey || "").trim();
  if (ck) (body as any).prompt_cache_key = ck.slice(0, 64);

  const msgs = body.messages as ChatMessage[] | undefined;
  if (Array.isArray(msgs) && msgs.length) {
    // 清掉上一轮残留断点，再按「≤2 system + 末 2 轮」重打（对齐 Go 24h 会话缓存）
    stripStaleCacheControl(msgs);
    let sysLeft = 2;
    for (const m of msgs) {
      if (sysLeft <= 0) break;
      if (m?.role === "system" && typeof m === "object") {
        (m as any).cache_control = { type: "ephemeral", ttl: "24h" };
        sysLeft -= 1;
      }
    }
    stampTailCacheControl(msgs);
  }
  const tools = body.tools as Array<Record<string, unknown>> | undefined;
  if (Array.isArray(tools) && tools.length) {
    for (const t of tools) {
      if (t && "cache_control" in t) delete t.cache_control;
    }
    tools[tools.length - 1]!.cache_control = { type: "ephemeral", ttl: "24h" };
  }
}

/** 从上游 usage 抽出 cache 命中（Go 可能给 details 或 hit/miss 字段） */
export function extractCachedTokens(usage: any): number {
  if (!usage || typeof usage !== "object") return 0;
  const details = usage.prompt_tokens_details || usage.input_tokens_details || {};
  return (
    Number(details.cached_tokens || 0) ||
    Number(usage.prompt_cache_hit_tokens || 0) ||
    Number(usage.cache_read_input_tokens || 0) ||
    0
  );
}
