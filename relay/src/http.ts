// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v3.5 — HTTP 共享 helpers
//  readBody / json / notFound / urlParams
// ═══════════════════════════════════════════════════════════════

import type { IncomingMessage, ServerResponse } from "http";

const MAX_BODY_SIZE = 10 * 1024 * 1024; // 10MB — 防止 OOM

/** 读取并解析 JSON body（带大小限制） */
export function readBody(req: IncomingMessage): Promise<any> {
  return new Promise((ok, er) => {
    let b = "";
    let size = 0;
    req.on("data", (c: string) => {
      size += c.length;
      if (size > MAX_BODY_SIZE) {
        req.destroy();
        er(new Error("Request body too large"));
        return;
      }
      b += c;
    });
    req.on("end", () => {
      if (!b.trim()) return ok({});
      try { ok(JSON.parse(b)); } catch { er(new Error("Invalid JSON")); }
    });
    req.on("error", er);
  });
}

/** 写 JSON 响应 */
export function json(res: ServerResponse, code: number, data: any): void {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}

/** 404 响应 */
export function notFound(res: ServerResponse, path: string, mode: string): void {
  json(res, 404, { error: `Not found in mode=${mode}: ${path}` });
}

/** 解析 query 参数 */
export function urlParams(req: IncomingMessage): Map<string, string> {
  const url = new URL(req.url || "", "http://x");
  const map = new Map<string, string>();
  for (const [k, v] of url.searchParams) map.set(k, v);
  return map;
}
