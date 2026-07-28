// ═══════════════════════════════════════════════════════════════
//  CCC Relay — /v1/responses（OpenAI Responses API 薄垫片）
//  给 Codex / ChatGPT.app 用：转 chat/completions 上游，再转回 responses。
//  含 tools / function_call 双向转换（Codex 工具调用主路径）。
// ═══════════════════════════════════════════════════════════════

import type { IncomingMessage, ServerResponse } from "http";
import { route, affinityKey, affinitySet, resolveRequestTier } from "../router.js";
import {
  streamWithFallback,
  nonStreamWithFallback,
  recordProviderSuccess,
  applyTrailHeaders,
} from "../fallback.js";
import { cleanThink, streamReadWithTimeout } from "../utils.js";
import { cauth, cmay } from "../auth.js";
import { logUsage } from "../usage.js";
import { json, readBody } from "../http.js";
import { TIMEOUTS } from "../config.js";
import { upstreamFetch } from "../egress.js";
import { applyOpenAIPromptCache } from "../translator/anthropic.js";
import { isPaidUpstream } from "../tiers.js";

type Msg = {
  role: string;
  content: string | null;
  tool_calls?: Array<{ id: string; type: "function"; function: { name: string; arguments: string } }>;
  tool_call_id?: string;
};

type ChatTool = {
  type: "function";
  function: { name: string; description: string; parameters: Record<string, unknown> };
};

type ToolAcc = { id: string; name: string; args: string; itemId: string; outputIndex: number; started: boolean };

function textFromContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((c: any) => {
      if (typeof c === "string") return c;
      if (c?.type === "input_text" || c?.type === "output_text" || c?.type === "text") {
        return c.text || c.content || "";
      }
      return typeof c?.text === "string" ? c.text : "";
    })
    .filter(Boolean)
    .join("\n");
}

/** Responses tools（含 namespace 展开）→ Chat Completions tools */
function flattenTools(tools: unknown): ChatTool[] {
  if (!Array.isArray(tools)) return [];
  const out: ChatTool[] = [];
  const seen = new Set<string>();

  const pushFn = (name: string, description: string, parameters: any) => {
    if (!name || seen.has(name)) return;
    seen.add(name);
    const params =
      parameters && typeof parameters === "object"
        ? { ...parameters }
        : { type: "object", properties: {} };
    if (!params.type || params.type === "null") params.type = "object";
    out.push({
      type: "function",
      function: {
        name,
        description: description || "",
        parameters: params,
      },
    });
  };

  for (const t of tools as any[]) {
    if (!t || typeof t !== "object") continue;
    if (t.type === "function" && t.name) {
      pushFn(t.name, t.description || "", t.parameters || t.input_schema);
      continue;
    }
    if (t.type === "function" && t.function?.name) {
      pushFn(t.function.name, t.function.description || "", t.function.parameters);
      continue;
    }
    if (t.type === "namespace" && Array.isArray(t.tools)) {
      for (const nt of t.tools) {
        if (!nt || nt.type !== "function" || !nt.name) continue;
        // 优先裸名；冲突时加 namespace 前缀（Codex 回写同名）
        const leaf = nt.name;
        const qualified = `${t.name}.${nt.name}`;
        pushFn(seen.has(leaf) ? qualified : leaf, nt.description || "", nt.parameters);
      }
    }
    // web_search 等非 function：chat 上游不认，跳过
  }
  return out;
}

function inputToMessages(input: unknown, instructions?: string): Msg[] {
  const out: Msg[] = [];
  if (instructions && String(instructions).trim()) {
    out.push({ role: "system", content: String(instructions) });
  }

  let pendingCalls: NonNullable<Msg["tool_calls"]> = [];
  const flushCalls = () => {
    if (!pendingCalls.length) return;
    out.push({ role: "assistant", content: null, tool_calls: pendingCalls });
    pendingCalls = [];
  };

  const items: any[] =
    typeof input === "string"
      ? [{ type: "message", role: "user", content: input }]
      : Array.isArray(input)
        ? input
        : [{ type: "message", role: "user", content: JSON.stringify(input ?? "") }];

  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const it = item as any;

    if (it.type === "function_call") {
      pendingCalls.push({
        id: it.call_id || it.id || `call_${pendingCalls.length}`,
        type: "function",
        function: {
          name: it.name || "unknown",
          arguments: typeof it.arguments === "string" ? it.arguments : JSON.stringify(it.arguments ?? {}),
        },
      });
      continue;
    }

    if (it.type === "function_call_output") {
      flushCalls();
      out.push({
        role: "tool",
        tool_call_id: it.call_id || "",
        content: typeof it.output === "string" ? it.output : JSON.stringify(it.output ?? ""),
      });
      continue;
    }

    if (it.type === "reasoning" || it.type === "web_search_call") continue;

    flushCalls();

    if (it.role === "tool" || it.type === "tool") {
      out.push({
        role: "tool",
        tool_call_id: it.tool_call_id || it.call_id || "",
        content: textFromContent(it.content) || String(it.output || ""),
      });
      continue;
    }

    const roleRaw = (it.role || "user") as string;
    const role =
      roleRaw === "developer" || roleRaw === "system"
        ? "system"
        : roleRaw === "assistant"
          ? "assistant"
          : "user";
    const text = textFromContent(it.content) || (typeof it.text === "string" ? it.text : "");
    if (text || role === "assistant") {
      const msg: Msg = { role, content: text || "" };
      if (Array.isArray(it.tool_calls) && it.tool_calls.length) {
        msg.tool_calls = it.tool_calls;
        msg.content = text || null;
      }
      out.push(msg);
    }
  }
  flushCalls();

  if (!out.some(m => m.role === "user" || m.role === "tool")) {
    out.push({ role: "user", content: "hi" });
  }
  return out;
}

function writeEvent(res: ServerResponse, event: string, data: unknown): void {
  res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
}

function chatToResponses(chat: any, model: string): any {
  const msg = chat?.choices?.[0]?.message || {};
  let text = typeof msg.content === "string" ? msg.content : "";
  text = cleanThink(text || "");
  const id = `resp_${Date.now()}`;
  const output: any[] = [];

  if (text) {
    output.push({
      type: "message",
      id: `msg_${Date.now()}`,
      status: "completed",
      role: "assistant",
      content: [{ type: "output_text", text }],
    });
  }

  const tcs = Array.isArray(msg.tool_calls) ? msg.tool_calls : [];
  for (const tc of tcs) {
    output.push({
      type: "function_call",
      id: `fc_${Date.now()}_${output.length}`,
      call_id: tc.id || `call_${output.length}`,
      name: tc.function?.name || "unknown",
      arguments: tc.function?.arguments || "{}",
      status: "completed",
    });
  }

  if (!output.length) {
    output.push({
      type: "message",
      id: `msg_${Date.now()}`,
      status: "completed",
      role: "assistant",
      content: [{ type: "output_text", text: "" }],
    });
  }

  return {
    id,
    object: "response",
    created_at: Math.floor(Date.now() / 1000),
    status: "completed",
    model,
    output,
    usage: {
      input_tokens: chat?.usage?.prompt_tokens || 0,
      output_tokens: chat?.usage?.completion_tokens || 0,
      total_tokens: chat?.usage?.total_tokens || 0,
    },
  };
}

export async function handleResponses(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const t0 = Date.now();
  let b: any;
  try {
    b = await readBody(req);
  } catch {
    return json(res, 400, { error: { message: "Invalid JSON" } });
  }

  const client = cauth(req);
  const model = b.model || "flash";
  if (!cmay(client, model)) {
    return json(res, 403, { error: { message: `Client not authorized for model: ${model}` } });
  }
  if (client?.qe) return json(res, 429, { error: { message: "Client daily quota exceeded" } });

  const messages = inputToMessages(b.input, b.instructions);
  const stream = !!b.stream;
  const maxTokens = b.max_output_tokens || b.max_tokens || 8192;
  const chatTools = flattenTools(b.tools);

  const chatBody: any = {
    model,
    messages,
    max_tokens: maxTokens,
    stream,
    ...(stream ? { stream_options: { include_usage: true } } : {}),
  };
  if (typeof b.temperature === "number") chatBody.temperature = b.temperature;
  if (chatTools.length) {
    chatBody.tools = chatTools;
    chatBody.tool_choice = b.tool_choice ?? "auto";
    if (typeof b.parallel_tool_calls === "boolean") {
      chatBody.parallel_tool_calls = b.parallel_tool_calls;
    }
  }

  const affKey =
    (typeof b.prompt_cache_key === "string" && b.prompt_cache_key) ||
    affinityKey(messages, { headers: req.headers, system: b.instructions });
  const tier = resolveRequestTier(model, "flash");
  const ru = route(tier, affKey);
  const up = ru.upstream;
  if (!up?.api_key) {
    res.setHeader("Retry-After", "60");
    return json(res, 502, { error: { message: "No available upstream" } });
  }

  if (!stream) {
    const result = await nonStreamWithFallback(ru, async (candidate, wallSignal) => {
      const cFbm = ru.fallback_model || candidate.fallback_model || null;
      const cUpm = cFbm || candidate.upstream_model || String(model).replace(/^opencode-go\//, "");
      try {
        const signals = [AbortSignal.timeout(TIMEOUTS.NONSTREAM_MS), wallSignal].filter(Boolean) as AbortSignal[];
        const signal =
          signals.length > 1 && typeof AbortSignal.any === "function" ? AbortSignal.any(signals) : signals[0];
        const body: any = {
          ...chatBody,
          model: cUpm,
          stream: false,
          ...(candidate.request_overrides || {}),
        };
        applyOpenAIPromptCache(body, { promptCacheKey: affKey });
        const resp = await upstreamFetch(candidate, candidate.base_url + "/chat/completions", {
          method: "POST",
          headers: { Authorization: `Bearer ${candidate.api_key}`, "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal,
        });
        const d = await resp.json();
        return { response: resp, body: d };
      } catch {
        return null;
      }
    });

    applyTrailHeaders(res, result.upstream?.name, result.trail);
    if (!result.upstream) {
      const retry = result.retryAfterSec || 60;
      res.setHeader("Retry-After", String(retry));
      return json(res, 503, {
        error: {
          type: "service_unavailable",
          message: result.errorMessage || "All upstreams exhausted",
          retry_after_sec: retry,
        },
      });
    }

    const respObj = chatToResponses(result.body, model);
    logUsage({
      timestamp: Date.now(),
      upstream: result.upstream.name,
      client: client?.id || "anonymous",
      model,
      total_tokens: respObj.usage?.total_tokens || 0,
      prompt_tokens: respObj.usage?.input_tokens || 0,
      success: true,
      latency_ms: Date.now() - t0,
    });
    recordProviderSuccess(result.upstream);
    if (affKey) {
      affinitySet(affKey, result.upstream.name, { pinPaid: isPaidUpstream(result.upstream) });
    }
    return json(res, 200, respObj);
  }

  // ── Stream: chat SSE → responses SSE（文本 + function_call）──
  let headersSent = false;
  let streamOk = false;
  let pT = 0;
  let cT = 0;
  let tt = 0;
  let textAcc = "";
  let messageStarted = false;
  let outputIndex = 0;
  let msgOutputIndex = 0;
  const respId = `resp_${Date.now()}`;
  const msgId = `msg_${Date.now()}`;
  const itemId = `item_${Date.now()}`;
  const toolsByIndex = new Map<number, ToolAcc>();

  const ensureCreated = () => {
    if (headersSent) return;
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    });
    headersSent = true;
    writeEvent(res, "response.created", {
      type: "response.created",
      response: {
        id: respId,
        object: "response",
        created_at: Math.floor(Date.now() / 1000),
        status: "in_progress",
        model,
        output: [],
      },
    });
  };

  const ensureMessage = () => {
    ensureCreated();
    if (messageStarted) return;
    messageStarted = true;
    msgOutputIndex = outputIndex++;
    writeEvent(res, "response.output_item.added", {
      type: "response.output_item.added",
      output_index: msgOutputIndex,
      item: { type: "message", id: msgId, status: "in_progress", role: "assistant", content: [] },
    });
    writeEvent(res, "response.content_part.added", {
      type: "response.content_part.added",
      item_id: itemId,
      output_index: msgOutputIndex,
      content_index: 0,
      part: { type: "output_text", text: "" },
    });
  };

  const ensureTool = (idx: number, patch: { id?: string; name?: string; args?: string }) => {
    ensureCreated();
    let tc = toolsByIndex.get(idx);
    if (!tc) {
      const oi = outputIndex++;
      tc = {
        id: patch.id || `call_${Date.now()}_${idx}`,
        name: patch.name || "",
        args: "",
        itemId: `fc_${Date.now()}_${idx}`,
        outputIndex: oi,
        started: false,
      };
      toolsByIndex.set(idx, tc);
    }
    if (patch.id) tc.id = patch.id;
    if (patch.name) tc.name = patch.name;
    if (patch.args) tc.args += patch.args;

    if (!tc.started && tc.name) {
      tc.started = true;
      writeEvent(res, "response.output_item.added", {
        type: "response.output_item.added",
        output_index: tc.outputIndex,
        item: {
          type: "function_call",
          id: tc.itemId,
          call_id: tc.id,
          name: tc.name,
          arguments: "",
          status: "in_progress",
        },
      });
    }
    if (patch.args && tc.started) {
      writeEvent(res, "response.function_call_arguments.delta", {
        type: "response.function_call_arguments.delta",
        item_id: tc.itemId,
        output_index: tc.outputIndex,
        delta: patch.args,
      });
    }
    return tc;
  };

  const result = await streamWithFallback(
    ru,
    async (candidate, signal) => {
      const cFbm = ru.fallback_model || candidate.fallback_model || null;
      const cUpm = cFbm || candidate.upstream_model || String(model).replace(/^opencode-go\//, "");
      const body: any = {
        ...chatBody,
        model: cUpm,
        stream: true,
        stream_options: { include_usage: true },
        ...(candidate.request_overrides || {}),
      };
      applyOpenAIPromptCache(body, { promptCacheKey: affKey });
      try {
        return await upstreamFetch(candidate, candidate.base_url + "/chat/completions", {
          method: "POST",
          headers: { Authorization: `Bearer ${candidate.api_key}`, "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal,
        });
      } catch (e) {
        if (signal?.aborted || /timeout|aborted|TimeoutError/i.test((e as Error)?.name + (e as Error)?.message)) {
          throw e;
        }
        return null;
      }
    },
    {
      getBytesWritten: () => (headersSent ? 1 : 0),
      consume: async ({ reader, firstLines, buffered, stallMs }) => {
        const decoder = new TextDecoder();
        let buf = buffered || "";
        textAcc = "";

        const handleDataLine = (line: string) => {
          const s = line.trim();
          if (!s || s.startsWith(":")) return;
          if (!s.startsWith("data:")) return;
          const payload = s.startsWith("data: ") ? s.slice(6).trim() : s.slice(5).trim();
          if (!payload || payload === "[DONE]") return;
          let obj: any;
          try {
            obj = JSON.parse(payload);
          } catch {
            return;
          }

          const delta = obj?.choices?.[0]?.delta || {};
          if (typeof delta.content === "string" && delta.content) {
            ensureMessage();
            const cleaned = cleanThink(delta.content);
            if (cleaned) {
              textAcc += cleaned;
              writeEvent(res, "response.output_text.delta", {
                type: "response.output_text.delta",
                item_id: itemId,
                output_index: msgOutputIndex,
                content_index: 0,
                delta: cleaned,
              });
            }
          }

          if (Array.isArray(delta.tool_calls)) {
            for (const tc of delta.tool_calls) {
              const idx = typeof tc.index === "number" ? tc.index : 0;
              ensureTool(idx, {
                id: tc.id,
                name: tc.function?.name,
                args: tc.function?.arguments,
              });
            }
          }

          if (obj?.usage) {
            pT = obj.usage.prompt_tokens || pT;
            cT = obj.usage.completion_tokens || cT;
            tt = obj.usage.total_tokens || tt;
          }
        };

        const feed = (lines: string[]) => {
          for (const line of lines) handleDataLine(line);
        };

        ensureCreated();
        if (firstLines?.length) feed(firstLines);

        while (true) {
          const { done, value } = await streamReadWithTimeout(reader, stallMs);
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() || "";
          feed(lines);
        }
        streamOk = true;
      },
    },
  );

  applyTrailHeaders(res, result.upstream?.name, result.trail);

  if (!result.consumedOk && !headersSent) {
    const retry = result.retryAfterSec || 60;
    res.setHeader("Retry-After", String(retry));
    return json(res, 503, {
      error: {
        type: "service_unavailable",
        message: result.errorMessage || "All upstreams exhausted",
        retry_after_sec: retry,
      },
    });
  }

  if (headersSent && res.writable) {
    const finalText = cleanThink(textAcc);
    const output: any[] = [];

    if (messageStarted) {
      writeEvent(res, "response.output_text.done", {
        type: "response.output_text.done",
        item_id: itemId,
        output_index: msgOutputIndex,
        content_index: 0,
        text: finalText,
      });
      writeEvent(res, "response.output_item.done", {
        type: "response.output_item.done",
        output_index: msgOutputIndex,
        item: {
          type: "message",
          id: msgId,
          status: "completed",
          role: "assistant",
          content: [{ type: "output_text", text: finalText }],
        },
      });
      output.push({
        type: "message",
        id: msgId,
        status: "completed",
        role: "assistant",
        content: [{ type: "output_text", text: finalText }],
      });
    }

    const sortedTools = [...toolsByIndex.entries()].sort((a, b) => a[0] - b[0]);
    for (const [, tc] of sortedTools) {
      if (!tc.started && tc.name) {
        // name arrived without args stream — still emit item
        writeEvent(res, "response.output_item.added", {
          type: "response.output_item.added",
          output_index: tc.outputIndex,
          item: {
            type: "function_call",
            id: tc.itemId,
            call_id: tc.id,
            name: tc.name,
            arguments: "",
            status: "in_progress",
          },
        });
        tc.started = true;
      }
      if (!tc.started) continue;
      writeEvent(res, "response.function_call_arguments.done", {
        type: "response.function_call_arguments.done",
        item_id: tc.itemId,
        output_index: tc.outputIndex,
        arguments: tc.args || "{}",
      });
      const item = {
        type: "function_call",
        id: tc.itemId,
        call_id: tc.id,
        name: tc.name,
        arguments: tc.args || "{}",
        status: "completed",
      };
      writeEvent(res, "response.output_item.done", {
        type: "response.output_item.done",
        output_index: tc.outputIndex,
        item,
      });
      output.push(item);
    }

    if (!output.length) {
      output.push({
        type: "message",
        id: msgId,
        status: "completed",
        role: "assistant",
        content: [{ type: "output_text", text: "" }],
      });
    }

    writeEvent(res, "response.completed", {
      type: "response.completed",
      response: {
        id: respId,
        object: "response",
        created_at: Math.floor(Date.now() / 1000),
        status: "completed",
        model,
        output,
        usage: {
          input_tokens: pT,
          output_tokens: cT || Math.max(0, tt - pT),
          total_tokens: tt || pT + (cT || 0),
        },
      },
    });
    res.end();
  }

  if (result.upstream) {
    logUsage({
      timestamp: Date.now(),
      upstream: result.upstream.name,
      client: client?.id || "anonymous",
      model,
      total_tokens: tt,
      prompt_tokens: pT,
      success: streamOk,
      latency_ms: Date.now() - t0,
    });
    if (streamOk) {
      recordProviderSuccess(result.upstream);
      if (affKey) {
        affinitySet(affKey, result.upstream.name, { pinPaid: isPaidUpstream(result.upstream) });
      }
    }
  }
}
