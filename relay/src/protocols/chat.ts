// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.2 — /v1/chat/completions (OpenAI Chat)
// ═══════════════════════════════════════════════════════════════

import type { IncomingMessage, ServerResponse } from "http";
import { route, affinityKey, affinitySet, affinityDeleteAll, resolveRequestTier } from "../router.js";
import {
  streamWithFallback,
  nonStreamWithFallback,
  recordProviderSuccess,
  applyTrailHeaders,
} from "../fallback.js";
import { cleanThink, streamReadWithTimeout, type CleanThinkState } from "../utils.js";
import { cauth, cmay } from "../auth.js";
import { logUsage } from "../usage.js";
import { json, readBody } from "../http.js";
import { cacheKey, cacheGet, cacheSet, prefixCacheKey, trackPrefix, isCacheableRequest, shouldCacheWrite } from "../cache.js";
// CCC Relay 2026-07-25 门禁②补丁:流式/非流式超时走可配
import { TIMEOUTS } from "../config.js";

export async function handleChat(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const t0 = Date.now();
  let b: any;
  try { b = await readBody(req); } catch {
    return json(res, 400, { error: { message: "Invalid JSON" } });
  }

  const client = cauth(req);
  if (!cmay(client, b.model || "")) {
    return json(res, 403, { error: { message: `Client not authorized for model: ${b.model}` } });
  }
  if (client?.qe) return json(res, 429, { error: { message: "Client daily quota exceeded" } });

  const stream = !!b.stream;
  const cacheable = isCacheableRequest(b);
  const ckey = cacheable ? cacheKey(b) : "";
  const pkey = prefixCacheKey(b);
  trackPrefix(pkey);
  if (ckey) {
    const hit = cacheGet(ckey);
    if (hit) {
      logUsage({
        timestamp: Date.now(),
        upstream: "cache",
        client: client?.id || "anonymous",
        model: b.model,
        total_tokens: 0,
        cached_tokens: (hit.tokens?.input || 0) + (hit.tokens?.output || 0),
        success: true,
        latency_ms: Date.now() - t0,
      });
      if (stream) {
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
          "X-Cache": "HIT",
        });
        writeOpenAIResponseAsSSE(res, hit.response, b.model);
        res.end();
        return;
      }
      res.setHeader("X-Cache", "HIT");
      return json(res, 200, hit.response);
    }
  }

  const affKey = affinityKey(b.messages, { headers: req.headers, system: b.system });
  const tier = resolveRequestTier(b.model, "code");
  const ru = route(tier, affKey);
  const up = ru.upstream;
  if (!up?.api_key) {
    res.setHeader("Retry-After", "60");
    return json(res, 502, { error: { message: "No available upstream" } });
  }

  if (stream) {
    let bytesWritten = 0;
    let headersSent = false;
    let pT = 0, cT = 0, tt = 0, ctk = 0;
    let streamOk = false;
    const oaAcc = {
      text: "",
      reasoning: "",
      tools: [] as Array<{ id: string; name: string; args: string }>,
      finishReason: "stop" as string,
      respId: "chatcmpl-" + Date.now(),
    };

    const result = await streamWithFallback(
      ru,
      async (candidate) => {
        const cFbm = ru.fallback_model || candidate.fallback_model || null;
        const cUpm = cFbm || candidate.upstream_model || b.model.replace(/^opencode-go\//, "");
        const body: any = {
          ...b,
          model: cUpm,
          stream: true,
          stream_options: { include_usage: true },
          ...(candidate.request_overrides || {}),
        };
        try {
          const controller = new AbortController();
          const connectTimer = setTimeout(() => controller.abort(), TIMEOUTS.CONNECT_MS);
          try {
            return await fetch(candidate.base_url + "/chat/completions", {
              method: "POST",
              headers: { Authorization: `Bearer ${candidate.api_key}`, "Content-Type": "application/json" },
              body: JSON.stringify(body),
              signal: controller.signal,
            });
          } finally {
            clearTimeout(connectTimer);
          }
        } catch {
          return null;
        }
      },
      {
        getBytesWritten: () => bytesWritten,
        consume: async ({ reader, firstLines, buffered, stallMs }) => {
          // reset accumulators per attempt (stall failover)
          oaAcc.text = "";
          oaAcc.reasoning = "";
          oaAcc.tools = [];
          oaAcc.finishReason = "stop";
          pT = 0; cT = 0; tt = 0; ctk = 0;
          const decoder = new TextDecoder();
          let buf = buffered;
          const think: CleanThinkState = { i: false };
          let pendingFirst = firstLines;

          const writeLines = (lines: string[]) => {
            for (const ln of lines) {
              const tr = ln.trim();
              if (!tr || tr.startsWith(":")) continue;
              if (!tr.startsWith("data: ")) continue;
              const d = tr.slice(6);
              if (d === "[DONE]") {
                res.write("data: [DONE]\n\n");
                bytesWritten += 1;
                continue;
              }
              try {
                const p = JSON.parse(d);
                if (p.id) oaAcc.respId = p.id;
                if (p.choices?.[0]?.delta?.content) {
                  const cleaned = cleanThink(p.choices[0].delta.content, think);
                  p.choices[0].delta.content = cleaned;
                  oaAcc.text += cleaned;
                }
                if (p.choices?.[0]?.delta?.reasoning_content) {
                  oaAcc.reasoning += p.choices[0].delta.reasoning_content;
                } else if (p.choices?.[0]?.delta?.reasoning) {
                  oaAcc.reasoning += p.choices[0].delta.reasoning;
                }
                if (p.choices?.[0]?.delta?.tool_calls) {
                  for (const tc of p.choices[0].delta.tool_calls) {
                    const idx = tc.index ?? 0;
                    if (!oaAcc.tools[idx]) oaAcc.tools[idx] = { id: "", name: "", args: "" };
                    if (tc.id) oaAcc.tools[idx].id = tc.id;
                    if (tc.function?.name) oaAcc.tools[idx].name = tc.function.name;
                    if (tc.function?.arguments) oaAcc.tools[idx].args += tc.function.arguments;
                  }
                }
                if (p.choices?.[0]?.finish_reason) oaAcc.finishReason = p.choices[0].finish_reason;
                if (p.usage) {
                  pT = p.usage.prompt_tokens || pT;
                  cT = p.usage.completion_tokens || cT;
                  tt = p.usage.total_tokens || tt;
                  ctk = p.usage.prompt_tokens_details?.cached_tokens || ctk;
                }
                const chunk = `data: ${JSON.stringify(p)}\n\n`;
                res.write(chunk);
                bytesWritten += chunk.length;
              } catch {
                console.warn("[chat stream] skip non-JSON line:", (ln || "").slice(0, 80));
              }
            }
          };

          const flushStart = (extra: string[]) => {
            if (!headersSent) {
              res.writeHead(200, {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
              });
              headersSent = true;
            }
            if (pendingFirst) {
              writeLines(pendingFirst);
              pendingFirst = null as any;
            }
            writeLines(extra);
          };

          // Stall before any client write → failover; only flush after first successful read or stream end
          while (true) {
            const { done, value } = await streamReadWithTimeout(reader, stallMs);
            if (done) {
              flushStart([]);
              break;
            }
            buf += decoder.decode(value, { stream: true });
            const lines = buf.split("\n");
            buf = lines.pop() || "";
            flushStart(lines);
          }
          streamOk = true;
        },
      },
    );

    applyTrailHeaders(res, result.upstream?.name, result.trail);

    if (!result.consumedOk && !result.stalledAfterWrite) {
      if (affKey) affinityDeleteAll(affKey);
      if (!headersSent) {
        const retry = result.retryAfterSec || 60;
        res.setHeader("Retry-After", String(retry));
        return json(res, 503, {
          error: {
            type: "service_unavailable",
            message: result.errorMessage || "All upstreams exhausted",
            retry_after_sec: retry,
            trail: result.trail,
          },
        });
      }
    }

    if (result.stalledAfterWrite && res.writable) {
      res.write("data: [DONE]\n\n");
    }

    if (streamOk && ckey && shouldCacheWrite(b, undefined, { stream: true }) && !oaAcc.tools.length) {
      const cached = buildOpenAIResponseFromAcc(oaAcc, b.model, pT, cT || Math.max(0, tt - pT));
      if (shouldCacheWrite(b, cached, { stream: true })) {
        cacheSet(ckey, cached, { input: pT, output: cT || Math.max(0, tt - pT) });
      }
    }

    if (result.upstream) {
      logUsage({
        timestamp: Date.now(),
        upstream: result.upstream.name,
        client: client?.id || "anonymous",
        model: b.model,
        total_tokens: tt,
        cached_tokens: ctk,
        success: streamOk,
        latency_ms: Date.now() - t0,
      });
      if (streamOk) {
        recordProviderSuccess(result.upstream);
        if (affKey && !ru.is_fallback) affinitySet(affKey, result.upstream.name);
      } else if (affKey) {
        affinityDeleteAll(affKey);
      }
    }

    if (res.writable && headersSent) res.end();
    return;
  }

  // ── Non-stream ──
  const result = await nonStreamWithFallback(ru, async (candidate) => {
    const cFbm = ru.fallback_model || candidate.fallback_model || null;
    const cUpm = cFbm || candidate.upstream_model || b.model.replace(/^opencode-go\//, "");
    try {
      const resp = await fetch(candidate.base_url + "/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${candidate.api_key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ ...b, model: cUpm, ...(candidate.request_overrides || {}) }),
        signal: AbortSignal.timeout(TIMEOUTS.NONSTREAM_MS),
      });
      const d = await resp.json();
      return { response: resp, body: d };
    } catch {
      return null;
    }
  });

  applyTrailHeaders(res, result.upstream?.name, result.trail);

  if (!result.upstream) {
    if (affKey) affinityDeleteAll(affKey);
    const retry = result.retryAfterSec || 60;
    res.setHeader("Retry-After", String(retry));
    return json(res, 503, {
      error: {
        type: "service_unavailable",
        message: result.errorMessage || "All upstreams exhausted",
        retry_after_sec: retry,
        trail: result.trail,
      },
    });
  }

  const d = result.body;
  if (d.choices?.[0]?.message?.content) {
    d.choices[0].message.content = cleanThink(d.choices[0].message.content);
  }

  if (ckey && shouldCacheWrite(b, d)) {
    cacheSet(ckey, d, {
      input: d.usage?.prompt_tokens || 0,
      output: d.usage?.completion_tokens || 0,
    });
  }

  logUsage({
    timestamp: Date.now(),
    upstream: result.upstream.name,
    client: client?.id || "anonymous",
    model: b.model,
    total_tokens: d.usage?.total_tokens || 0,
    cached_tokens: d.usage?.prompt_tokens_details?.cached_tokens || 0,
    success: true,
    latency_ms: Date.now() - t0,
  });
  recordProviderSuccess(result.upstream);
  if (affKey && !ru.is_fallback) affinitySet(affKey, result.upstream.name);
  return json(res, 200, d);
}

interface OAIStreamAccumulator {
  text: string;
  reasoning: string;
  tools: Array<{ id: string; name: string; args: string }>;
  finishReason: string;
  respId: string;
}

function buildOpenAIResponseFromAcc(
  acc: OAIStreamAccumulator,
  model: string,
  promptTokens: number,
  completionTokens: number,
): Record<string, unknown> {
  const message: any = { role: "assistant", content: acc.text || null };
  if (acc.reasoning) message.reasoning_content = acc.reasoning;
  if (acc.tools.length) {
    message.tool_calls = acc.tools.map(tc => ({
      id: tc.id,
      type: "function",
      function: { name: tc.name, arguments: tc.args },
    }));
  }
  return {
    id: acc.respId,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [{ index: 0, message, finish_reason: acc.finishReason || "stop" }],
    usage: {
      prompt_tokens: promptTokens,
      completion_tokens: completionTokens,
      total_tokens: promptTokens + completionTokens,
    },
  };
}

function writeOpenAIResponseAsSSE(res: ServerResponse, d: any, reqModel: string): void {
  const id = d.id || ("chatcmpl-" + Date.now());
  const created = d.created || Math.floor(Date.now() / 1000);
  const model = d.model || reqModel;
  const ch = d.choices?.[0];
  const msg = ch?.message || {};
  const baseChunk = (delta: any, fr: any = null) => ({
    id, object: "chat.completion.chunk", created, model,
    choices: [{ index: 0, delta, finish_reason: fr }],
  });
  res.write(`data: ${JSON.stringify(baseChunk({ role: "assistant" }))}\n\n`);
  if (msg.reasoning_content) {
    res.write(`data: ${JSON.stringify(baseChunk({ reasoning_content: msg.reasoning_content }))}\n\n`);
  }
  if (msg.content) {
    res.write(`data: ${JSON.stringify(baseChunk({ content: msg.content }))}\n\n`);
  }
  if (Array.isArray(msg.tool_calls)) {
    for (let i = 0; i < msg.tool_calls.length; i++) {
      const tc = msg.tool_calls[i];
      res.write(`data: ${JSON.stringify(baseChunk({
        tool_calls: [{
          index: i, id: tc.id, type: "function",
          function: { name: tc.function?.name, arguments: tc.function?.arguments },
        }],
      }))}\n\n`);
    }
  }
  res.write(`data: ${JSON.stringify(baseChunk({}, ch?.finish_reason || "stop"))}\n\n`);
  if (d.usage) {
    res.write(`data: ${JSON.stringify({
      id, object: "chat.completion.chunk", created, model, choices: [], usage: d.usage,
    })}\n\n`);
  }
  res.write("data: [DONE]\n\n");
}
