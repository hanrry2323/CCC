import { describe, it, expect } from "vitest";
import dns from "node:dns";
import { preferIpv4Dns, EGRESS_CONNECT_IPV4 } from "../src/dns-prefer-ipv4.js";

describe("dns-prefer-ipv4", () => {
  it("forces undici connect family 4", () => {
    expect(EGRESS_CONNECT_IPV4.family).toBe(4);
  });

  it("sets dns result order to ipv4first", () => {
    preferIpv4Dns();
    expect(dns.getDefaultResultOrder()).toBe("ipv4first");
  });
});
