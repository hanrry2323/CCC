// ═══════════════════════════════════════════════════════════════
//  IPv4-first egress DNS
//  本网（M1 / Mac2017）到 opencode.ai（Cloudflare）IPv6 黑洞：
//  curl -6 超时、curl -4 秒级通。Node 默认 verbatim 先 AAAA →
//  undici 卡满 CONNECT/ATTEMPT，表现为 sole flash「attempt timeout」。
// ═══════════════════════════════════════════════════════════════

import dns from "node:dns";

/** Prefer A records before AAAA for all subsequent lookups. */
export function preferIpv4Dns(): void {
  try {
    dns.setDefaultResultOrder("ipv4first");
  } catch {
    /* Node < 17 */
  }
}

/** undici Agent `connect` options: force AF_INET (skip broken AAAA path). */
export const EGRESS_CONNECT_IPV4 = {
  family: 4 as const,
};
