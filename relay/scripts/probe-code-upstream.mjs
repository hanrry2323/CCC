#!/usr/bin/env node
/**
 * 探针：对 upstreams.json 中单个 code 上游做 TTFB / 简单 chat / 可选 tools。
 * 用法: node scripts/probe-code-upstream.mjs --name code-groq
 * 退出码 0 = 过检；非 0 = 未过检
 */
import { readFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const DIR = dirname(fileURLToPath(import.meta.url));
const UPSTREAMS = process.env.LOOP_UPSTREAMS_FILE || join(DIR, "..", "upstreams.json");

function arg(name, def) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : def;
}

const name = arg("--name");
if (!name) {
  console.error("Usage: node scripts/probe-code-upstream.mjs --name <upstream-name>");
  process.exit(2);
}

if (!existsSync(UPSTREAMS)) {
  console.error("upstreams.json not found:", UPSTREAMS);
  process.exit(2);
}

const list = JSON.parse(readFileSync(UPSTREAMS, "utf-8"));
const up = list.find((u) => u.name === name);
if (!up) {
  console.error("upstream not found:", name);
  process.exit(2);
}
if (!up.api_key || /your-|placeholder|sk-your/i.test(up.api_key)) {
  console.error("api_key looks like placeholder — fill a real key first");
  process.exit(2);
}

const url = up.base_url.replace(/\/$/, "") + "/chat/completions";
const body = {
  model: up.upstream_model,
  messages: [{ role: "user", content: "Reply with exactly: pong" }],
  max_tokens: 32,
  temperature: 0,
};

const t0 = Date.now();
let status = 0;
let text = "";
try {
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${up.api_key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  status = resp.status;
  text = await resp.text();
} catch (e) {
  console.error("FAIL fetch:", e.message);
  process.exit(1);
}

const ttfb = Date.now() - t0;
console.log(`status=${status} ttfb_ms=${ttfb}`);
if (status === 429) {
  console.error("FAIL rate-limited (429) — check quota / wait");
  process.exit(1);
}
if (status < 200 || status >= 300) {
  console.error("FAIL http:", text.slice(0, 400));
  process.exit(1);
}

let content = "";
try {
  const j = JSON.parse(text);
  content = j.choices?.[0]?.message?.content || "";
  if (j.error) {
    console.error("FAIL body error:", j.error.message || j.error);
    process.exit(1);
  }
} catch {
  console.error("FAIL non-json body:", text.slice(0, 200));
  process.exit(1);
}

console.log("content:", content.slice(0, 120));
if (!content.trim()) {
  console.error("FAIL empty content");
  process.exit(1);
}

// optional tools probe
if (process.argv.includes("--tools")) {
  const toolBody = {
    model: up.upstream_model,
    messages: [{ role: "user", content: "Call the tool echo with text hi" }],
    tools: [{
      type: "function",
      function: {
        name: "echo",
        description: "echo text",
        parameters: { type: "object", properties: { text: { type: "string" } }, required: ["text"] },
      },
    }],
    max_tokens: 64,
  };
  const r2 = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${up.api_key}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(toolBody),
    signal: AbortSignal.timeout(30_000),
  });
  const j2 = await r2.json();
  const tc = j2.choices?.[0]?.message?.tool_calls;
  console.log("tools:", tc ? "ok" : "no tool_calls", r2.status);
  if (!tc) process.exit(1);
}

console.log("PASS", name);
process.exit(0);
