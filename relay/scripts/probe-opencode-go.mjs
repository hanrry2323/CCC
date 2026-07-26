#!/usr/bin/env node
/**
 * 探测 upstreams.json 里 opencode-go* / opencode-code*：是否可用 + 429 重置时间。
 * 用法: node scripts/probe-opencode-go.mjs
 *       LOOP_PROBE_FILTER=code node scripts/probe-opencode-go.mjs   # 仅 code 档
 * 不登录控制台，用 API 错误信息推断额度状态（官方暂无 balance API）。
 */
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const DIR = dirname(fileURLToPath(import.meta.url));
const UPSTREAMS = process.env.LOOP_UPSTREAMS_FILE || join(DIR, "..", "upstreams.json");
const FILTER = (process.env.LOOP_PROBE_FILTER || "all").toLowerCase();

if (!existsSync(UPSTREAMS)) {
  console.error("upstreams.json not found:", UPSTREAMS);
  process.exit(2);
}

function nameMatch(name) {
  const n = String(name || "");
  if (FILTER === "code") return /opencode-code/i.test(n);
  if (FILTER === "flash" || FILTER === "go") return /opencode-go/i.test(n);
  return /opencode-(go|code)/i.test(n);
}

const list = JSON.parse(readFileSync(UPSTREAMS, "utf-8")).filter(
  (u) => u?.name && nameMatch(u.name),
);

if (!list.length) {
  console.error(`no matching opencode-* upstreams (filter=${FILTER})`);
  process.exit(2);
}

function classify(status, err) {
  const e = err || "";
  const reset = /Resets in ([^.]+)/i.exec(e)?.[1]?.trim() || null;
  if (status === 200) return { verdict: "OK", reset };
  // 月/周/5h 限额优先（文案里常带 available balance，勿误判成无余额）
  if (status === 429 || /usage limit|Monthly usage|Weekly usage|rate.?limit/i.test(e)) {
    return { verdict: "LIMIT", reset };
  }
  if (/insufficient balance|CreditsError|billing here/i.test(e) || status === 401) {
    return { verdict: "NO_BALANCE", reset };
  }
  if (!status) return { verdict: "FETCH_ERR", reset };
  return { verdict: `HTTP_${status}`, reset };
}

async function probe(u) {
  const url = String(u.base_url).replace(/\/$/, "") + "/chat/completions";
  const t0 = Date.now();
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${u.api_key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: u.upstream_model || "deepseek-v4-flash",
        messages: [{ role: "user", content: "hi" }],
        max_tokens: 8,
        temperature: 0,
      }),
      signal: AbortSignal.timeout(25_000),
    });
    const text = await resp.text();
    let err = "";
    let finish = "";
    try {
      const j = JSON.parse(text);
      err = j?.error?.message || "";
      finish = j?.choices?.[0]?.finish_reason || "";
    } catch { /* ignore */ }
    const { verdict, reset } = classify(resp.status, err);
    return {
      name: u.name,
      enabled: u.enabled !== false,
      priority: u.tier_priority ?? 99,
      status: resp.status,
      ms: Date.now() - t0,
      verdict: resp.status === 200 ? "OK" : verdict,
      finish: finish || undefined,
      reset,
      err: err ? err.slice(0, 120) : undefined,
    };
  } catch (e) {
    return {
      name: u.name,
      enabled: u.enabled !== false,
      priority: u.tier_priority ?? 99,
      verdict: "FETCH_ERR",
      ms: Date.now() - t0,
      err: String(e.message || e).slice(0, 120),
    };
  }
}

const rows = [];
for (const u of list.sort((a, b) => (a.tier_priority ?? 99) - (b.tier_priority ?? 99))) {
  rows.push(await probe(u));
}

console.log(`OpenCode Zen probe (filter=${FILTER})\n`);
for (const r of rows) {
  const en = r.enabled ? "on " : "off";
  const reset = r.reset ? `  reset≈${r.reset}` : "";
  console.log(
    `${r.name.padEnd(18)} P${String(r.priority).padEnd(2)} [${en}]  ${r.verdict.padEnd(12)}${reset}` +
      (r.err && r.verdict !== "OK" ? `\n${"".padEnd(30)}${r.err}` : ""),
  );
}
console.log("\n提示: 官方暂无 balance API；重置时间来自 429 错误文案。月限按订阅周期重置，非自然月。");
