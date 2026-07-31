// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — 工具函数
//  classifyErr, normTools, cleanThink
// ═══════════════════════════════════════════════════════════════

import { appendFileSync, mkdirSync } from "fs";
import { dirname } from "path";
import type { ClassifiedError, OpenAIFunctionTool, AnthropicTool } from "./types.js";

// ── Stall (v4.2) ──

export class StallError extends Error {
  constructor(message = "stream stall") {
    super(message);
    this.name = "StallError";
  }
}

// #region agent log
/** Debug-mode NDJSON sink (session b671cf). Env: LOOP_DEBUG_LOG */
export function agentDebugLog(
  hypothesisId: string,
  location: string,
  message: string,
  data: Record<string, unknown> = {},
): void {
  try {
    const logPath =
      process.env.LOOP_DEBUG_LOG ||
      "/Users/fan/.ccc/logs/debug-b671cf.ndjson";
    mkdirSync(dirname(logPath), { recursive: true });
    appendFileSync(
      logPath,
      JSON.stringify({
        sessionId: "b671cf",
        hypothesisId,
        location,
        message,
        data,
        timestamp: Date.now(),
      }) + "\n",
    );
  } catch {
    /* never break relay on debug I/O */
  }
}
// #endregion

export function getStallIdleMs(): number {
  const n = parseInt(process.env.STALL_IDLE_MS || "120000", 10);
  return Number.isFinite(n) && n > 0 ? n : 120_000;
}

// ── 错误分类 ──

export function classifyErr(msg: unknown): ClassifiedError | null {
  if (!msg) return null;
  // If it's an object, try to extract a string from common fields
  let s: string;
  if (typeof msg === "object") {
    s = String((msg as any).message || (msg as any).error || (msg as any).msg || JSON.stringify(msg));
  } else {
    s = String(msg);
  }
  if (!s) return null;
  // 1. 限流/网络类错误 → 短冷却 60s（最先检查，避免被宽泛配额词误判）
  //    包含「超限」「超出限制」等通用限流表述，防止它们命中配额正则
  if (/(访问量过大|速率限制|rate[\s_-]?limit|限流|超限|超出限制|1305|1302|网络错误|网络超时|网络异常|ECONN|ETIMEDOUT|aborted|fetch failed|timeout|socket hang up|connect ETIMEDOUT|UND_ERR)/i.test(s)) {
    return { sec: 60, quota: false };
  }
  // 2. 认证/授权类错误 → 长冷却 300s，需人工介入修复
  if (/(authorization failed|auth.*fail|unauthorized|身份验证|认证失败|invalid api key|invalid key)/i.test(s)) {
    return { sec: 300, quota: false };
  }
  // 3. 上游服务故障类错误 → 中冷却 120s
  if (/(Error from provider|upstream request failed|upstream error|internal server error|service error)/i.test(s)) {
    return { sec: 120, quota: false };
  }
  // 4. 配额/余额类错误
  //    4a) 付费渠道余额不足/billing → 短冷却 60s（用户一充值就好，不能走 4h 反而是灾难）
  if (/(insufficient balance|manage your billing|billing here|payment required|balance is zero|credits? error|余额不足)/i.test(s)) {
    return { sec: 60, quota: false };
  }
  //    4b) 真正的周期配额（免费档耗尽）→ 长冷却 300s，清 affinity
  if (/(usage limit reached|usage quota (exceeded|exhausted)|用量上限|额度用完|流量用完|配额已用完|配额耗尽|insufficient quota|已用完|FreeUsage)/i.test(s)) {
    return { sec: 300, quota: true };
  }
  // 5. exceeded 通用匹配 → 排除 rate/timeout/token/context/length/size
  //    这些是 request/response 级别限制，非配额耗尽
  if (/\bexceeded\b/i.test(s) && !/rate|timeout|token|context|length|size/i.test(s)) {
    return { sec: 300, quota: true };
  }
  return null;
}

// ── 工具标准化 ──

const EMOJI_REGEX = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{200D}\u{20E3}\u{231A}-\u{231B}\u{23E9}-\u{23F3}\u{23F8}-\u{23FA}\u{25AA}-\u{25AB}\u{25B6}\u{25C0}\u{25FB}-\u{25FE}]/gu;

export interface CleanThinkState {
  i: boolean;
}

export function cleanThink(t: string, st?: CleanThinkState): string {
  if (!t) return "";
  st = st || { i: false };
  let o = "", r = t;
  while (r.length) {
    if (st.i) {
      const j = r.indexOf("</think>");
      if (j >= 0) { st.i = false; r = r.slice(j + 8); }
      else break;
    } else {
      const j = r.indexOf("<think>");
      if (j >= 0) { o += r.slice(0, j); r = r.slice(j + 7); st.i = true; }
      else { o += r; break; }
    }
  }
  return o.replace(EMOJI_REGEX, "");
}

/**
 * 带超时的 stream reader.read()
 * 上游停止发送数据时不会无限挂起，超时后 cancel reader 并抛 StallError
 */
export async function streamReadWithTimeout<T>(
  reader: ReadableStreamDefaultReader<T>,
  timeoutMs: number,
): Promise<ReadableStreamReadResult<T>> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reader.cancel().catch(() => {});
      reject(new StallError(`Stream read timeout after ${timeoutMs}ms`));
    }, timeoutMs);
    reader.read().then(
      (r) => { clearTimeout(timer); resolve(r); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

export function normTools(tools: (AnthropicTool | OpenAIFunctionTool)[]): OpenAIFunctionTool[] {
  return tools
    .filter(t => t && (t as any).name)
    .map(t => {
      const p = (t as any).parameters || (t as AnthropicTool).input_schema || {};
      if (!p.type || p.type === "null") p.type = "object";
      return {
        type: "function" as const,
        function: {
          name: (t as any).name,
          description: (t as any).description || "",
          parameters: p,
        },
      };
    });
}

// ── Thinking 指令剥离 (R2) ──
// Claude Code 在 system 里夹带 "You must always output a thinking block..." 指令，
// 转给 DeepSeek / non-thinking 上游会触发 HTTP 400。转换时主动剥离。
const THINKING_PATTERNS: RegExp[] = [
  /<thinking>[\s\S]*?<\/thinking>/gi,
  /<\/?think>/gi,
  /You must always (start |)output (a |)thinking block[\s\S]{0,500}?(\.\s|\n|$)/gi,
  /When you (provide|output) thinking[\s\S]{0,500}?(\.\s|\n|$)/gi,
  /Assistant must always (start |)output (a |)thinking block[\s\S]{0,500}?(\.\s|\n|$)/gi,
  /Always (start |)with (a |)thinking block[\s\S]{0,500}?(\.\s|\n|$)/gi,
  /Put your thinking inside <thinking>[\s\S]{0,200}?(\.\s|\n|$)/gi,
];

export function stripThinkingDirectives(s: string): string {
  if (!s) return "";
  let out = s;
  for (const re of THINKING_PATTERNS) out = out.replace(re, "");
  return out
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
