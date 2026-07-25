#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════
//  AI Loop Router — 免费模型目录同步脚本
//  从 OmniRoute 仓库同步 free model catalog
// ═══════════════════════════════════════════════════════════════

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const DIR = dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = join(DIR, "..");
const OUTPUT = join(PROJECT_DIR, "data", "free-models.json");

// OmniRoute 参考项目路径 (可配环境变量)
const OMNIROUTE_DIR = process.env.OMNIROUTE_DIR || join(PROJECT_DIR, "..", "reference", "OmniRoute", "@omniroute");

async function main() {
  // 尝试从 OmniRoute 源读取
  const sourceFile = join(OMNIROUTE_DIR, "open-sse", "config", "freeModelCatalog.data.ts");

  if (existsSync(sourceFile)) {
    console.log(`[catalog:sync] reading from: ${sourceFile}`);
    const content = readFileSync(sourceFile, "utf-8");

    // 提取 FREE_MODEL_BUDGETS 数组 (简化的 AST 方式)
    const match = content.match(/FREE_MODEL_BUDGETS:\s*FreeModelBudget\[\]\s*=\s*(\[[\s\S]*?\]);/);
    if (match) {
      // 尝试转成 JSON: 把 TS 风格的引号修成 JSON 兼容
      // 注意: 这个提取可能不完全可靠，需要兜底
      try {
        // 移除 export const 和类型定义
        let jsonStr = match[1];
        // 替换 TS 特性
        jsonStr = jsonStr.replace(/\/\/.*$/gm, ""); // 移除注释
        jsonStr = jsonStr.replace(/:\s*"avoid"|:\s*"caution"|:\s*"ambiguous"|:\s*"ok"/g, (m) => m); // 保留 tos 值
        // 保守处理: 替换单引号为双引号 (TS 可能用单引号)
        jsonStr = jsonStr.replace(/'/g, '"');

        const data = JSON.parse(jsonStr);
        writeFileSync(OUTPUT, JSON.stringify(data, null, 2));
        console.log(`[catalog:sync] synced ${data.length} models → ${OUTPUT}`);
        process.exit(0);
      } catch (e) {
        console.warn(`[catalog:sync] AST extraction failed: ${(e as Error).message}, falling back`);
      }
    }
  }

  // 兜底: 使用现有文件
  const existing = join(PROJECT_DIR, "data", "free-models.json");
  if (existsSync(existing)) {
    const data = JSON.parse(readFileSync(existing, "utf-8"));
    console.log(`[catalog:sync] using existing: ${data.length} models`);
    process.exit(0);
  }

  console.warn("[catalog:sync] no source found, creating empty catalog");
  writeFileSync(OUTPUT, "[]");
  process.exit(0);
}

main().catch(console.error);
