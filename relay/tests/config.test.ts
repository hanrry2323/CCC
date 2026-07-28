// ═══════════════════════════════════════════════════════════════
//  tests/config.test.ts — ConfigLoader 验证
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, unlinkSync, existsSync } from "fs";
import { loadConfig, reloadConfig, getConfig, resetConfig, validateConfig, startConfigWatcher, stopConfigWatcher, isAutoReloadEnabled } from "../src/config.js";
import type { UpstreamConfig } from "../src/types.js";

const TEST_FILE = "/tmp/test-upstreams.json";

const MINIMAL_UPSTREAMS: UpstreamConfig[] = [
  {
    name: "opencode-go-paid-flash",
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-test-key",
    tier: "flash",
    tier_priority: 1,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
  },
  {
    name: "opencode-go-paid-flash-b",
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-test-key-2",
    tier: "flash",
    tier_priority: 2,
    models: ["flash"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
    enabled: false,
  },
  {
    name: "a-pro-high",
    base_url: "https://api.provider.com/v1",
    api_key: "sk-pro",
    tier: "pro",
    tier_priority: 1,
    models: ["pro"],
    upstream_model: "claude-opus-4",
    enabled: false,
  },
  {
    name: "code-idle",
    base_url: "https://opencode.ai/zen/go/v1",
    api_key: "sk-code",
    tier: "code",
    tier_priority: 1,
    models: ["code"],
    upstream_model: "deepseek-v4-flash",
    free: false,
    billing: "opencode-go",
    enabled: false,
  },
];

function writeTestConfig(ups: UpstreamConfig[] = MINIMAL_UPSTREAMS) {
  writeFileSync(TEST_FILE, JSON.stringify(ups, null, 2));
}

describe("config.ts", () => {
  beforeEach(() => {
    writeTestConfig();
  });

  afterEach(() => {
    if (existsSync(TEST_FILE)) unlinkSync(TEST_FILE);
    resetConfig();
  });

  it("loads upstreams and builds tier registry", () => {
    const reg = loadConfig(TEST_FILE);

    // enabled:false 不进运行时 all（备份钥人切后才 reload）
    expect(reg.all.length).toBe(1);
    expect(reg.names).toEqual(["flash"]);
    expect(reg.tiers.has("flash")).toBe(true);
  });

  it("sorts upstreams by tier_priority within each tier", () => {
    const reg = loadConfig(TEST_FILE);

    const flash = reg.tiers.get("flash")!;
    expect(flash.length).toBe(1);
    expect(flash[0].name).toBe("opencode-go-paid-flash");
  });

  it("handles empty models[] by falling back to tier field", () => {
    const withMissingModels: UpstreamConfig[] = [
      {
        name: "no-models",
        base_url: "https://x.ai/v1",
        api_key: "sk-x",
        tier: "code",
        tier_priority: 1,
        models: [],
        upstream_model: "grok-3",
      },
    ];
    writeTestConfig(withMissingModels);
    const reg = loadConfig(TEST_FILE);
    expect(reg.all.length).toBe(1);
    expect(reg.tiers.get("code")?.length).toBe(1);
  });

  it("handles empty upstreams gracefully", () => {
    writeTestConfig([]);
    const reg = loadConfig(TEST_FILE);
    expect(reg.all.length).toBe(0);
    expect(reg.names).toEqual([]);
    expect(reg.tiers.size).toBe(0);
  });

  it("supports hot reload", () => {
    const reg1 = loadConfig(TEST_FILE);
    expect(reg1.all.length).toBe(1);

    // Add a new enabled upstream
    const ups = [...MINIMAL_UPSTREAMS, {
      name: "new-upstream",
      base_url: "https://new.api/v1",
      api_key: "sk-new",
      tier: "flash" as const,
      tier_priority: 2,
      models: ["flash" as const],
      upstream_model: "gpt-5",
      free: false,
      billing: "opencode-go",
    }];

    writeTestConfig(ups);
    reloadConfig();
    const reg2 = getConfig();
    expect(reg2.all.length).toBe(2);
    expect(reg2.tiers.get("flash")?.length).toBe(2);
  });

  it("validateConfig skips invalid entries and collects warnings", () => {
    const { valid, warnings } = validateConfig([
      { base_url: "https://x/v1", api_key: "sk", tier: "flash", models: ["flash"] },
      { name: "no-url", api_key: "sk", tier: "flash", models: ["flash"] },
      { name: "no-key", base_url: "https://x/v1", tier: "flash", models: ["flash"] },
      { name: "no-tier", base_url: "https://x/v1", api_key: "sk", models: [] },
      { name: "ok", base_url: "https://x/v1", api_key: "sk", tier: "flash", models: ["flash"], upstream_model: "m" },
    ] as any);
    expect(valid.length).toBe(1);
    expect(valid[0].name).toBe("ok");
    expect(warnings.length).toBe(4);
    expect(warnings[0]).toContain('missing "name"');
    expect(warnings[1]).toContain('no-url');
    expect(warnings[2]).toContain('no-key');
    expect(warnings[3]).toContain('no-tier');
  });

  it("isAutoReloadEnabled respects LOOP_AUTO_RELOAD env", () => {
    const prev = process.env.LOOP_AUTO_RELOAD;
    process.env.LOOP_AUTO_RELOAD = "false";
    expect(isAutoReloadEnabled()).toBe(false);
    if (prev === undefined) delete process.env.LOOP_AUTO_RELOAD;
    else process.env.LOOP_AUTO_RELOAD = prev;
  });

  it("auto-reloads when upstreams file changes", async () => {
    loadConfig(TEST_FILE);
    stopConfigWatcher();
    const before = getConfig().all.length;
    startConfigWatcher();
    const ups = [...MINIMAL_UPSTREAMS, {
      name: "watch-test",
      base_url: "https://watch.api/v1",
      api_key: "sk-watch",
      tier: "flash" as const,
      tier_priority: 9,
      models: ["flash" as const],
      upstream_model: "test",
    }];
    // 确保 mtime 变化（部分 FS 对同秒写入不触发）
    await new Promise(r => setTimeout(r, 50));
    writeTestConfig(ups);
    let reloaded = false;
    for (let i = 0; i < 40; i++) {
      if (getConfig().all.length === before + 1) { reloaded = true; break; }
      await new Promise(r => setTimeout(r, 250));
    }
    expect(reloaded).toBe(true);
    stopConfigWatcher();
  }, 15_000);
});

describe("config v4.3 normalize + reconcile", () => {
  beforeEach(() => {
    writeTestConfig();
  });
  afterEach(() => {
    if (existsSync(TEST_FILE)) unlinkSync(TEST_FILE);
    resetConfig();
  });

  it("normalizeUpstream derives models from tier and tier from models", async () => {
    const { normalizeUpstream, assertValidUpstreamList } = await import("../src/config.js");
    const a = normalizeUpstream({
      name: "t-only", base_url: "https://x/v1", api_key: "sk", tier: "flash",
    } as any);
    expect(a!.models).toEqual(["flash"]);
    expect(a!.tier).toBe("flash");

    const b = normalizeUpstream({
      name: "m-only", base_url: "https://x/v1", api_key: "sk", models: ["code"],
    } as any);
    expect(b!.tier).toBe("code");
    expect(b!.models).toEqual(["code"]);

    expect(assertValidUpstreamList([])).toContain("Empty");
    expect(assertValidUpstreamList([{ name: "bad" }])).toBeTruthy();
  });
});
