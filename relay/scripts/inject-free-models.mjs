// ═══════════════════════════════════════════════════════════════
//  将 data/code-pool.curated.json 注入 upstreams.json（占位 key）
//  运行: node scripts/inject-free-models.mjs
//  不会覆盖已有同名上游；不会写入真实密钥
// ═══════════════════════════════════════════════════════════════

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const DIR = dirname(fileURLToPath(import.meta.url));
const UPSTREAMS_FILE = process.env.LOOP_UPSTREAMS_FILE || join(DIR, "..", "upstreams.json");
const CURATED = join(DIR, "..", "data", "code-pool.curated.json");

function main() {
  if (!existsSync(CURATED)) {
    console.error("missing", CURATED);
    process.exit(1);
  }
  const curated = JSON.parse(readFileSync(CURATED, "utf-8"));
  let upstreams = [];
  if (existsSync(UPSTREAMS_FILE)) {
    upstreams = JSON.parse(readFileSync(UPSTREAMS_FILE, "utf-8"));
  }

  const injected = [];
  for (const c of curated) {
    if (upstreams.find((u) => u.name === c.name)) {
      console.log("skip existing", c.name);
      continue;
    }
    const envKey = c.env_key || `FREE_API_KEY_${c.name.toUpperCase().replace(/[^A-Z0-9]/g, "_")}`;
    const apiKey = process.env[envKey] || `sk-${c.name}-placeholder`;
    injected.push({
      name: c.name,
      base_url: c.base_url,
      api_key: apiKey,
      tier: "code",
      tier_priority: c.tier_priority ?? 99,
      models: ["code"],
      upstream_model: c.upstream_model,
      provider_group: c.provider_group,
      free: !!c.free,
      free_type: c.free_type,
      quota: c.quota || undefined,
      enabled: false,
      _note: c.note || "curated code pool — enable after probe",
    });
  }

  if (!injected.length) {
    console.log("nothing to inject");
    return;
  }

  upstreams.push(...injected);
  writeFileSync(UPSTREAMS_FILE, JSON.stringify(upstreams, null, 2) + "\n");
  console.log(`injected ${injected.length} curated code upstreams (enabled:false) → ${UPSTREAMS_FILE}`);
  console.log("Next: fill keys, probe, then set enabled:true");
}

main();
