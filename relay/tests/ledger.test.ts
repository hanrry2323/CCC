// ═══════════════════════════════════════════════════════════════
//  tests/ledger.test.ts — 配额账本 RPM/RPD/TPM/TPD
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach } from "vitest";
import { setAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import {
  ledgerWouldExceed,
  ledgerReserve,
  ledgerSettle,
  ledgerSnapshot,
  ledgerReset,
} from "../src/ledger.js";
import { isUpstreamOk } from "../src/tiers.js";
import type { UpstreamConfig } from "../src/types.js";

const makeUp = (overrides: Partial<UpstreamConfig> = {}): UpstreamConfig => ({
  name: "led-up",
  base_url: "https://api.test/v1",
  api_key: "sk-test",
  tier: "code",
  tier_priority: 1,
  models: ["code"],
  upstream_model: "m",
  quota: { rpm: 2, rpd: 10, tpm: 100, tpd: 1000 },
  ...overrides,
});

describe("ledger", () => {
  beforeEach(() => {
    cool.clear();
    hlt.clear();
    sc.clear();
    setAppContext(createAppContext({
      clients: cls,
      usage: { value: [] },
      recentLogs: { value: [] },
      health: hlt,
      cooldowns: cool,
      scores: sc,
      startTime: Date.now(),
      cacheStats: { hits: 0, misses: 0, prefixHits: 0, prefixMisses: 0 },
      usageIndex: usgIdx$,
    }));
    ledgerReset();
  });

  it("allows requests under rpm then blocks", () => {
    const up = makeUp();
    expect(ledgerReserve(up)).toBe(true);
    ledgerSettle(up, { success: true, tokens: 10 });
    expect(ledgerReserve(up)).toBe(true);
    ledgerSettle(up, { success: true, tokens: 10 });
    expect(ledgerWouldExceed(up)).toBe("rpm");
    expect(ledgerReserve(up)).toBe(false);
  });

  it("isUpstreamOk skips when ledger exceeded (no cooldown)", () => {
    const up = makeUp({ quota: { rpm: 1 } });
    ledgerReserve(up);
    ledgerSettle(up, { success: true, tokens: 0 });
    expect(cool.has(up.name)).toBe(false);
    expect(isUpstreamOk(up)).toBe(false);
    const snap = ledgerSnapshot(up);
    expect(snap.exceed).toBe("rpm");
  });

  it("rollbackRequest does not count failed attempt", () => {
    const up = makeUp({ quota: { rpm: 1 } });
    expect(ledgerReserve(up)).toBe(true);
    ledgerSettle(up, { success: false, rollbackRequest: true });
    expect(ledgerWouldExceed(up)).toBeNull();
    expect(ledgerReserve(up)).toBe(true);
  });

  it("no limits → always ok", () => {
    const up = makeUp({ quota: undefined });
    expect(ledgerWouldExceed(up)).toBeNull();
    expect(ledgerReserve(up)).toBe(true);
  });
});
