// ═══════════════════════════════════════════════════════════════
//  Per-upstream egress（HTTP CONNECT / SOCKS 代理）
//  用途：免费多钥拆到不同出口 IP，避免 OpenCode 同 IP RPM 整池假死
// ═══════════════════════════════════════════════════════════════

import { ProxyAgent, Agent, fetch as undiciFetch, type Dispatcher, type RequestInit as UndiciRequestInit } from "undici";
import type { UpstreamConfig } from "./types.js";

const _agents = new Map<string, Dispatcher>();
const _direct = new Agent({
  connect: { timeout: 30_000 },
  bodyTimeout: 0,
  headersTimeout: 120_000,
  keepAliveTimeout: 60_000,
});

/** 解析上游 proxy 字段；支持 http:// / https:// / socks5:// */
export function resolveUpstreamProxy(up: UpstreamConfig): string | null {
  const raw = (up.proxy || "").trim();
  if (!raw) return null;
  if (/^(https?|socks5?):\/\//i.test(raw)) return raw;
  // 允许写 host:port → 默认 http CONNECT
  if (/^[\w.\[\]:-]+:\d+$/.test(raw)) return `http://${raw}`;
  return null;
}

export function getDispatcherForUpstream(up: UpstreamConfig): Dispatcher {
  const proxy = resolveUpstreamProxy(up);
  if (!proxy) return _direct;
  let agent = _agents.get(proxy);
  if (!agent) {
    agent = new ProxyAgent({
      uri: proxy,
      requestTls: { timeout: 30_000 },
      proxyTls: { timeout: 30_000 },
    });
    _agents.set(proxy, agent);
    console.log(`[egress] proxy agent ready: ${proxy}`);
  }
  return agent;
}

/** 带上游出口的 fetch（代理失败时抛错，由 fallback 换钥）
 *
 * 必须用 undici 自带的 fetch：Node 全局 fetch 与 npm undici.ProxyAgent
 * 混用会报 InvalidArgumentError: invalid onRequestStart method。
 */
export async function upstreamFetch(
  up: UpstreamConfig,
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const dispatcher = getDispatcherForUpstream(up);
  // undici fetch 返回值与 Web Response 兼容；cast 给协议层用
  return undiciFetch(url, { ...(init as UndiciRequestInit), dispatcher }) as unknown as Promise<Response>;
}

/** 测试用：清空 agent 缓存 */
export function _resetEgressAgentsForTest(): void {
  for (const a of _agents.values()) {
    try {
      void (a as Agent).close?.();
    } catch {
      /* ignore */
    }
  }
  _agents.clear();
}
