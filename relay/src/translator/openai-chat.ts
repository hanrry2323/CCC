// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — OpenAI Chat 协议 (pass-through)
//  只替换 model 字段, 其余透传
// ═══════════════════════════════════════════════════════════════

import type { OpenAIChatRequest } from "../types.js";

export function openAIChatToUpstream(
  req: OpenAIChatRequest,
  upstreamModel: string,
): OpenAIChatRequest {
  return {
    ...req,
    model: upstreamModel,
  };
}
