// ═══════════════════════════════════════════════════════════════
//  admin cooldowns: list + soft clear (preserve long quota cools)
// ═══════════════════════════════════════════════════════════════

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { handleAdmin } from "../src/admin.js";
import { setAppContext, createAppContext } from "../src/context.js";
import { cool, hlt, sc, usgIdx$, cls } from "../src/state.js";
import { resetConfig, loadConfig } from "../src/config.js";
import { writeFileSync, mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import type { IncomingMessage, ServerResponse } from "http";

function mockReq(method: string, urlPath: string): IncomingMessage {
  return {
    method,
    url: urlPath,
    headers: {},
    on() { return this; },
  } as unknown as IncomingMessage;
}

function mockRes(): { res: ServerResponse; get status(): number; get body(): any } {
  let status = 0;
  let body: any = null;
  const res = {
    writeHead(code: number) { status = code; },
    end(s: string) { body = JSON.parse(s); },
  } as unknown as ServerResponse;
  return {
    res,
    get status() { return status; },
    get body() { return body; },
  };
}

describe("admin cooldowns clear preserve", () => {
  let tmpDir: string;
  let prevUpstreams: string | undefined;

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
    tmpDir = mkdtempSync(join(tmpdir(), "relay-admin-"));
    const ups = join(tmpDir, "upstreams.json");
    writeFileSync(ups, "[]\n");
    prevUpstreams = process.env.LOOP_UPSTREAMS_FILE;
    process.env.LOOP_UPSTREAMS_FILE = ups;
    resetConfig();
    loadConfig();
  });
  afterEach(() => {
    cool.clear();
    resetConfig();
    if (prevUpstreams === undefined) delete process.env.LOOP_UPSTREAMS_FILE;
    else process.env.LOOP_UPSTREAMS_FILE = prevUpstreams;
    rmSync(tmpDir, { recursive: true, force: true });
  });

  it("GET /admin/cooldowns lists remaining", async () => {
    cool.set("long-key", { until: Date.now() + 3600_000, reason: "h429:quota" });
    const out = mockRes();
    await handleAdmin(mockReq("GET", "/admin/cooldowns"), out.res, "/admin/cooldowns");
    expect(out.status).toBe(200);
    expect(out.body.count).toBe(1);
    expect(out.body.cooldowns[0].name).toBe("long-key");
    expect(out.body.cooldowns[0].left_sec).toBeGreaterThan(3500);
  });

  it("POST clear preserves long cooldowns by default", async () => {
    cool.set("short", { until: Date.now() + 60_000, reason: "h429:burst" });
    cool.set("long", { until: Date.now() + 3600_000, reason: "h429:day-quota" });
    const out = mockRes();
    await handleAdmin(mockReq("POST", "/admin/cooldowns/clear"), out.res, "/admin/cooldowns/clear");
    expect(out.status).toBe(200);
    expect(out.body.cleared).toBe(1);
    expect(out.body.preserved).toBe(1);
    expect(out.body.force).toBe(false);
    expect(cool.has("long")).toBe(true);
    expect(cool.has("short")).toBe(false);
  });

  it("POST clear?force=1 clears all including long", async () => {
    cool.set("long", { until: Date.now() + 3600_000, reason: "h429:day-quota" });
    const out = mockRes();
    await handleAdmin(
      mockReq("POST", "/admin/cooldowns/clear?force=1"),
      out.res,
      "/admin/cooldowns/clear",
    );
    expect(out.status).toBe(200);
    expect(out.body.force).toBe(true);
    expect(out.body.cleared).toBe(1);
    expect(cool.size).toBe(0);
  });
});
