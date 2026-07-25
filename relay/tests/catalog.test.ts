// ═══════════════════════════════════════════════════════════════
//  tests/catalog.test.ts — 免费模型目录验证
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect } from "vitest";
import { loadFreeModelCatalog, generateUpstreamEntries, computeFreeTierSummary } from "../src/catalog.js";
import { existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const DIR = dirname(fileURLToPath(import.meta.url));
const CATALOG_FILE = join(DIR, "..", "data", "free-models.json");

describe("catalog", () => {
  it("loads free-models.json", () => {
    expect(existsSync(CATALOG_FILE)).toBe(true);
    const models = loadFreeModelCatalog();
    expect(models.length).toBeGreaterThan(0);
  });

  it("generates upstream entries from catalog", () => {
    const models = loadFreeModelCatalog();
    const entries = generateUpstreamEntries(models);
    expect(entries.length).toBeGreaterThan(0);

    // All entries should be code tier
    for (const e of entries) {
      expect(e.tier).toBe("code");
      expect(e.free).toBe(true);
    }

    // Same pool key entries should be deduped
    const names = new Set(entries.map(e => e.name));
    expect(names.size).toBe(entries.length);
  });

  it("filters out tos: avoid and keyless types", () => {
    const testCatalog = [
      { provider: "bad", model_id: "bad-model", display_name: "Bad", monthly_tokens: 1000, free_type: "keyless", pool_key: null, tos: "avoid" },
    ];
    const entries = generateUpstreamEntries(testCatalog as any);
    const bad = entries.find(e => e.name.includes("bad"));
    expect(bad).toBeUndefined();
  });

  it("computeFreeTierSummary returns provider breakdown", () => {
    const summary = computeFreeTierSummary();
    expect(summary.length).toBeGreaterThan(0);
    expect(summary[0].provider).toBeTruthy();
    expect(summary[0].monthlyTokens).toBeGreaterThan(0);
  });
});
