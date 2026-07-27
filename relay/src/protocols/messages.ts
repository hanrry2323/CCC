// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — /v1/messages (Anthropic) Handler
//  含 cache 接入 (非流式) + 透明降级 + Session Affinity
// ═══════════════════════════════════════════════════════════════

import type { IncomingMessage, ServerResponse } from "http";
import { route, affinityKey, affinitySet, affinityDeleteAll, resolveRequestTier } from "../router.js";
import {
  streamWithFallback,
  nonStreamWithFallback,
  applyTrailHeaders,
  recordProviderSuccess,
} from "../fallback.js";
import { cleanThink, streamReadWithTimeout } from "../utils.js";
import {
  anthropicToOpenAI,
  openAIChunkToAnthropicSSE,
  createAnthropicSSEState,
} from "../translator/anthropic.js";
import { cauth, cmay } from "../auth.js";
import { logUsage } from "../usage.js";
import { json, readBody } from "../http.js";
// CCC Relay 2026-07-25 门禁②补丁:流式/非流式超时走可配
import { TIMEOUTS } from "../config.js";
import { cacheKey, cacheGet, cacheSet, prefixCacheKey, trackPrefix, isCacheableRequest, shouldCacheWrite } from "../cache.js";
import { upstreamFetch } from "../egress.js";

export async function handleMessages(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const t0 = Date.now();
  let b: any;
  try { b = await readBody(req); } catch {
    return json(res, 400, { error: { type: "invalid_request_error", message: "Invalid JSON" } });
  }

  const client = cauth(req);
  if (!cmay(client, b.model || "")) {
    return json(res, 403, { error: { message: `Client not authorized for model: ${b.model}` } });
  }
  if (client?.qe) return json(res, 429, { error: { message: "Client daily quota exceeded" } });

  // ── Cache lookup (工具请求跳过) ──
  const stream = !!b.stream;
  const cacheable = isCacheableRequest(b);
  const ckey = cacheable ? cacheKey(b) : "";
  const pkey = prefixCacheKey(b);
  const prefixHit = trackPrefix(pkey);
  if (ckey) {
    const hit = cacheGet(ckey);
    if (hit) {
      const ar = hit.response as any;
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
        writeAnthropicResponseAsSSE(res, ar, b.model);
        res.end();
        return;
      }
      res.setHeader("X-Cache", "HIT");
      res.setHeader("X-Cache-Prefix", prefixHit.seen ? `HIT-${prefixHit.hitCount}` : "MISS");
      return json(res, 200, ar);
    }
  }

  const affKey = affinityKey(b.messages, { headers: req.headers, system: b.system });
  const tier = resolveRequestTier(b.model, "flash");
  const ru = route(tier, affKey);
  const up = ru.upstream;
  if (!up?.api_key) {
    res.setHeader("Retry-After", "60");
    return json(res, 502, { error: { message: "No available upstream" } });
  }

  // ── Stream ──
  if (stream) {
    let bytesWritten = 0;
    let contentBytesWritten = 0;
    let headersSent = false;
    let streamOk = false;
    let pT = 0, tt = 0, ctk = 0;
    const respId = "msg_" + Date.now();
    const oaiState = createAnthropicSSEState();
    const acc = { text: "", thinking: "", tools: [] as Array<{ id: string; name: string; args: string }>, stopReason: "end_turn" as string };

    const result = await streamWithFallback(
      ru,
      async (candidate, signal) => {
        const cFbm = ru.fallback_model || candidate.fallback_model || null;
        const cUpm = cFbm || candidate.upstream_model || b.model.replace(/^opencode-go\//, "");
        const body = anthropicToOpenAI(b, cUpm, { promptCacheKey: affKey });
        body.stream = true;
        Object.assign(body, candidate.request_overrides || {});
        try {
          // 勿用 CONNECT_MS 包整段 fetch：大 prompt TTFB 常 >8s，会把付费保底一起误杀
          return await upstreamFetch(candidate, candidate.base_url + "/chat/completions", {
            method: "POST",
            headers: { Authorization: `Bearer ${candidate.api_key}`, "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal,
          });
        } catch (e) {
          // 墙钟/attempt abort 必须冒泡，勿吞成 null 再同钥重试拖死
          if (signal?.aborted || /timeout|aborted|TimeoutError/i.test((e as Error)?.name + (e as Error)?.message)) {
            throw e;
          }
          return null;
        }
      },
      {
        getBytesWritten: () => contentBytesWritten,
        consume: async ({ reader, firstLines, buffered, stallMs }) => {
          const decoder = new TextDecoder();
          let buf = buffered;
          let pendingFirst: string[] | null = firstLines;

          const writeLines = (lines: string[]) => {
            for (const ln of lines) {
              const tr = ln.trim();
              if (!tr || tr.startsWith(":")) continue;
              if (!tr.startsWith("data: ")) continue;
              const d = tr.slice(6);
              if (d === "[DONE]") continue;
              try {
                const p = JSON.parse(d);
                if (p.choices?.[0]?.delta?.content) {
                  p.choices[0].delta.content = cleanThink(p.choices[0].delta.content);
                  acc.text += p.choices[0].delta.content;
                }
                if (p.choices?.[0]?.delta?.reasoning_content) {
                  acc.thinking += p.choices[0].delta.reasoning_content;
                } else if (p.choices?.[0]?.delta?.reasoning) {
                  acc.thinking += p.choices[0].delta.reasoning;
                }
                if (p.choices?.[0]?.delta?.tool_calls) {
                  for (const tc of p.choices[0].delta.tool_calls) {
                    const idx = tc.index ?? 0;
                    if (!acc.tools[idx]) acc.tools[idx] = { id: "", name: "", args: "" };
                    if (tc.id) acc.tools[idx].id = tc.id;
                    if (tc.function?.name) acc.tools[idx].name = tc.function.name;
                    if (tc.function?.arguments) acc.tools[idx].args += tc.function.arguments;
                  }
                }
                if (p.choices?.[0]?.finish_reason) {
                  acc.stopReason = p.choices[0].finish_reason === "tool_calls" ? "tool_use"
                    : p.choices[0].finish_reason === "length" ? "max_tokens"
                    : "end_turn";
                }
                if (p.usage) {
                  pT = p.usage.prompt_tokens || pT;
                  tt = p.usage.total_tokens || tt;
                  ctk = p.usage.prompt_tokens_details?.cached_tokens || ctk;
                }
                const evs = openAIChunkToAnthropicSSE(p, oaiState);
                for (const ev of evs) {
                  const chunk = `data: ${JSON.stringify(ev)}\n\n`;
                  // 推迟锁定渠道：message_start 不计入 contentBytes，stall 仍可换渠
                  if (!headersSent) {
                    res.writeHead(200, {
                      "Content-Type": "text/event-stream",
                      "Cache-Control": "no-cache",
                      "Connection": "keep-alive",
                      "X-Cache-Prefix": prefixHit.seen ? `HIT-${prefixHit.hitCount}` : "MISS",
                    });
                    const start = `data: ${JSON.stringify({
                      type: "message_start",
                      message: {
                        id: respId, type: "message", role: "assistant", content: [], model: b.model,
                        stop_reason: null, stop_sequence: null,
                        usage: { input_tokens: 0, output_tokens: 0 },
                      },
                    })}\n\n`;
                    res.write(start);
                    bytesWritten += start.length;
                    headersSent = true;
                  }
                  res.write(chunk);
                  bytesWritten += chunk.length;
                  if (ev.type !== "message_start") contentBytesWritten += chunk.length;
                }
              } catch { /* ignore */ }
            }
          };

          const flushStart = (extra: string[]) => {
            // 不在此 writeHead：等 writeLines 产出真实 delta 再锁定渠道（stall 可换渠）
            if (pendingFirst) {
              writeLines(pendingFirst);
              pendingFirst = null;
            }
            writeLines(extra);
          };

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

          if (res.writable) {
            if (!headersSent) {
              res.writeHead(200, {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Cache-Prefix": prefixHit.seen ? `HIT-${prefixHit.hitCount}` : "MISS",
              });
              headersSent = true;
            }
            if (oaiState.thinkingOpen) {
              res.write(`data: ${JSON.stringify({ type: "content_block_stop", index: oaiState.thinkingIndex })}\n\n`);
              oaiState.thinkingOpen = false;
            }
            if (oaiState.textOpen) {
              res.write(`data: ${JSON.stringify({ type: "content_block_stop", index: oaiState.textIndex })}\n\n`);
              oaiState.textOpen = false;
            }
            for (const k in oaiState.toolBlocks) {
              const tb = oaiState.toolBlocks[k];
              if (!tb.closed) {
                res.write(`data: ${JSON.stringify({ type: "content_block_stop", index: tb.index })}\n\n`);
                tb.closed = true;
              }
            }
            res.write(`data: ${JSON.stringify({
              type: "message_delta",
              delta: { stop_reason: acc.stopReason, stop_sequence: null },
              usage: {
                input_tokens: Math.max(0, pT - ctk),
                cache_read_input_tokens: ctk,
                output_tokens: Math.max(0, tt - pT),
              },
            })}\n\n`);
            res.write(`data: ${JSON.stringify({ type: "message_stop" })}\n\n`);
          }
          streamOk = true;
        },
      },
    );

    applyTrailHeaders(res, result.upstream?.name, result.trail);

    if (!result.consumedOk && !result.stalledAfterWrite) {
      // 勿清 affinity：保住 Go prompt_cache 会话粘性
      if (!headersSent) {
        const retry = result.retryAfterSec || 60;
        res.setHeader("Retry-After", String(retry));
        return json(res, 503, {
          error: {
            type: "service_unavailable",
            message: result.errorMessage || "当前所有上游不可用，请检查 upstreams.json 配置",
            retry_after_sec: retry,
            trail: result.trail,
          },
        });
      }
    }

    if (result.stalledAfterWrite && res.writable) {
      res.write(`data: ${JSON.stringify({
        type: "error",
        error: { type: "api_error", message: "upstream stream stall" },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: "message_stop" })}\n\n`);
    }

    if (streamOk && ckey && shouldCacheWrite(b, undefined, { stream: true }) && !acc.tools.length) {
      const cached = buildAnthropicResponseFromAcc(acc, b.model, respId, pT, tt);
      if (shouldCacheWrite(b, cached, { stream: true })) {
        cacheSet(ckey, cached, { input: pT, output: tt });
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
        if (ctk > 0) {
          try { res.setHeader("X-Upstream-Cached-Tokens", String(ctk)); } catch { /* headers sent */ }
        }
      }
    }

    if (res.writable && headersSent) res.end();
    return;
  }

  // ── Non-stream (with cache write) ──
  const nonStreamResult = await nonStreamWithFallback(ru, async (candidate, wallSignal) => {
    const cFbm = ru.fallback_model || candidate.fallback_model || null;
    const cUpm = cFbm || candidate.upstream_model || b.model.replace(/^opencode-go\//, "");
    const body = Object.assign(anthropicToOpenAI(b, cUpm, { promptCacheKey: affKey }), candidate.request_overrides || {});
    try {
      const signals = [AbortSignal.timeout(TIMEOUTS.NONSTREAM_MS), wallSignal].filter(Boolean) as AbortSignal[];
      const signal = signals.length > 1 && typeof AbortSignal.any === "function"
        ? AbortSignal.any(signals)
        : signals[0];
      const resp = await upstreamFetch(candidate, candidate.base_url + "/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${candidate.api_key}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
        // CCC Relay 2026-07-25:非流式超时可配(默认 600s),别再用 30s 硬切；墙钟 signal 可打断
        signal,
      });
      const d = await resp.json();
      return { response: resp, body: d };
    } catch {
      return null;
    }
  });

  applyTrailHeaders(res, nonStreamResult.upstream?.name, nonStreamResult.trail);

  if (!nonStreamResult.upstream) {
    if (affKey) affinityDeleteAll(affKey);
    const retry = nonStreamResult.retryAfterSec || 60;
    res.setHeader("Retry-After", String(retry));
    return json(res, 503, {
      error: {
        type: "service_unavailable",
        message: nonStreamResult.errorMessage || "当前所有上游不可用，请检查 upstreams.json 配置",
        retry_after_sec: retry,
        trail: nonStreamResult.trail,
      },
    });
  }

  const d = nonStreamResult.body;
  const ch = d.choices?.[0];
  const msg = ch?.message || {};
  const ct = cleanThink(msg.content || "");
  const rc = msg.reasoning_content || "";
  const tcs = msg.tool_calls;

  const ar: Record<string, unknown> = {
    id: "msg_" + Date.now(),
    type: "message",
    role: "assistant",
    content: [],
    model: b.model,
    stop_reason: ch?.finish_reason === "tool_calls" ? "tool_use"
      : ch?.finish_reason === "length" ? "max_tokens"
      : "end_turn",
    stop_sequence: null,
    usage: {
      input_tokens: d.usage?.prompt_tokens || 0,
      output_tokens: d.usage?.completion_tokens || 0,
    },
  };
  if (rc) (ar.content as any[]).push({ type: "redacted_thinking", data: rc });
  if (ct) (ar.content as any[]).push({ type: "text", text: ct });
  if (tcs) {
    for (const tc of tcs) {
      (ar.content as any[]).push({
        type: "tool_use",
        id: tc.id,
        name: tc.function.name,
        input: (() => { try { return JSON.parse(tc.function.arguments || "{}"); } catch { return {}; } })(),
      });
    }
  }

  // 写入 cache（无 tools）
  if (ckey && shouldCacheWrite(b, ar)) {
    cacheSet(ckey, ar, {
      input: d.usage?.prompt_tokens || 0,
      output: d.usage?.completion_tokens || 0,
    });
  }

  logUsage({
    timestamp: Date.now(),
    upstream: nonStreamResult.upstream.name,
    client: client?.id || "anonymous",
    model: b.model,
    total_tokens: d.usage?.total_tokens || 0,
    cached_tokens: d.usage?.prompt_tokens_details?.cached_tokens || 0,
    success: true,
    latency_ms: Date.now() - t0,
  });
  recordProviderSuccess(nonStreamResult.upstream);
  if (affKey && !ru.is_fallback) affinitySet(affKey, nonStreamResult.upstream.name);
  res.setHeader("X-Cache-Prefix", prefixHit.seen ? `HIT-${prefixHit.hitCount}` : "MISS");
  return json(res, 200, ar);
}

// ── R4 Helpers: 流式响应 ↔ 非流式 response 互转 ──

interface StreamAccumulator {
  text: string;
  thinking: string;
  tools: Array<{ id: string; name: string; args: string }>;
  stopReason: string;
}

/** 从流式累积状态拼回非流式 Anthropic response (用于缓存) */
function buildAnthropicResponseFromAcc(
  acc: StreamAccumulator,
  model: string,
  id: string,
  promptTokens: number,
  totalTokens: number,
): Record<string, unknown> {
  const content: any[] = [];
  if (acc.thinking) content.push({ type: "redacted_thinking", data: acc.thinking });
  if (acc.text) content.push({ type: "text", text: acc.text });
  for (const tc of acc.tools) {
    let input: any = {};
    try { input = JSON.parse(tc.args || "{}"); } catch { /* keep empty */ }
    content.push({ type: "tool_use", id: tc.id, name: tc.name, input });
  }
  return {
    id,
    type: "message",
    role: "assistant",
    content,
    model,
    stop_reason: acc.stopReason,
    stop_sequence: null,
    usage: {
      input_tokens: promptTokens,
      output_tokens: Math.max(0, totalTokens - promptTokens),
    },
  };
}

/** 把非流式 Anthropic response 重新包装为 SSE (供流式缓存命中) */
function writeAnthropicResponseAsSSE(
  res: ServerResponse,
  ar: any,
  reqModel: string,
): void {
  const id = ar.id || ("msg_" + Date.now());
  res.write(`data: ${JSON.stringify({
    type: "message_start",
    message: {
      id, type: "message", role: "assistant", content: [],
      model: ar.model || reqModel,
      stop_reason: null, stop_sequence: null,
      usage: { input_tokens: ar.usage?.input_tokens || 0, output_tokens: 0 },
    },
  })}\n\n`);

  const blocks: any[] = Array.isArray(ar.content) ? ar.content : [];
  let idx = 0;
  for (const b of blocks) {
    if (b.type === "text") {
      res.write(`data: ${JSON.stringify({
        type: "content_block_start", index: idx,
        content_block: { type: "text", text: "" },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({
        type: "content_block_delta", index: idx,
        delta: { type: "text_delta", text: b.text || "" },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: "content_block_stop", index: idx })}\n\n`);
      idx++;
    } else if (b.type === "redacted_thinking") {
      res.write(`data: ${JSON.stringify({
        type: "content_block_start", index: idx,
        content_block: { type: "thinking", thinking: "" },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({
        type: "content_block_delta", index: idx,
        delta: { type: "thinking_delta", thinking: b.data || "" },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: "content_block_stop", index: idx })}\n\n`);
      idx++;
    } else if (b.type === "tool_use") {
      res.write(`data: ${JSON.stringify({
        type: "content_block_start", index: idx,
        content_block: { type: "tool_use", id: b.id, name: b.name, input: {} },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({
        type: "content_block_delta", index: idx,
        delta: { type: "input_json_delta", partial_json: JSON.stringify(b.input || {}) },
      })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: "content_block_stop", index: idx })}\n\n`);
      idx++;
    }
  }

  res.write(`data: ${JSON.stringify({
    type: "message_delta",
    delta: { stop_reason: ar.stop_reason || "end_turn", stop_sequence: null },
    usage: { output_tokens: ar.usage?.output_tokens || 0 },
  })}\n\n`);
  res.write(`data: ${JSON.stringify({ type: "message_stop" })}\n\n`);
}
