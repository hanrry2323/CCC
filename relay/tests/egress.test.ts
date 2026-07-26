import { describe, it, expect, afterEach } from "vitest";
import { resolveUpstreamProxy, _resetEgressAgentsForTest } from "../src/egress.js";
import type { UpstreamConfig } from "../src/types.js";

const up = (proxy?: string): UpstreamConfig => ({
  name: "t",
  base_url: "https://example.com",
  api_key: "k",
  tier: "flash",
  tier_priority: 1,
  models: ["flash"],
  upstream_model: "m",
  proxy,
});

describe("resolveUpstreamProxy", () => {
  afterEach(() => _resetEgressAgentsForTest());

  it("returns null when unset", () => {
    expect(resolveUpstreamProxy(up())).toBeNull();
    expect(resolveUpstreamProxy(up(""))).toBeNull();
  });

  it("keeps http/socks URIs", () => {
    expect(resolveUpstreamProxy(up("http://127.0.0.1:18080"))).toBe("http://127.0.0.1:18080");
    expect(resolveUpstreamProxy(up("socks5://127.0.0.1:11080"))).toBe("socks5://127.0.0.1:11080");
  });

  it("normalizes host:port to http", () => {
    expect(resolveUpstreamProxy(up("127.0.0.1:18080"))).toBe("http://127.0.0.1:18080");
  });
});
