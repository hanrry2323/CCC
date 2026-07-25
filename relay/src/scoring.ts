// ═══════════════════════════════════════════════════════════════
//  AI Loop Router v4.3 — 健康评分 + 指数退避 + 持久化
// ═══════════════════════════════════════════════════════════════

import { existsSync, readFileSync, writeFileSync, mkdirSync } from "fs";
import { dirname } from "path";
import type { ScoreRecord } from "./types.js";
import { getAppContext } from "./context.js";

const EWMA_ALPHA = 0.1;
const INITIAL_SCORE = 0.8;
const MAX_BACKOFF_MULT = 16;
const MAX_BACKOFF_FAILS = 4;
const DEFAULT_SCORES_FILE = process.env.LOOP_SCORES_FILE || "logs/scores.json";

function defaultRecord(): ScoreRecord {
  return {
    ewma: INITIAL_SCORE,
    recentTs: Date.now(),
    failStreak: 0,
    lastSuccessTs: 0,
    totalSuccess: 0,
    totalFail: 0,
  };
}

export function recordOutcome(name: string, ok: boolean): void {
  const scores = getAppContext().scores;
  const cur = scores.get(name) ?? defaultRecord();
  cur.ewma = cur.ewma * (1 - EWMA_ALPHA) + (ok ? 1 : 0) * EWMA_ALPHA;
  cur.failStreak = ok ? 0 : cur.failStreak + 1;
  if (ok) {
    cur.totalSuccess++;
    cur.lastSuccessTs = Date.now();
  } else {
    cur.totalFail++;
  }
  cur.recentTs = Date.now();
  scores.set(name, cur);
}

export function getScore(name: string): number {
  return getAppContext().scores.get(name)?.ewma ?? INITIAL_SCORE;
}

export function getScoreRecord(name: string): ScoreRecord | null {
  return getAppContext().scores.get(name) ?? null;
}

export function getAllScores(): Record<string, ScoreRecord> {
  const out: Record<string, ScoreRecord> = {};
  for (const [k, v] of getAppContext().scores) out[k] = v;
  return out;
}

export function backoffMultiplier(failStreak: number): number {
  const capped = Math.min(failStreak, MAX_BACKOFF_FAILS);
  return Math.min(2 ** capped, MAX_BACKOFF_MULT);
}

export function computeBackoffCooldown(
  name: string,
  baseSec: number,
  maxSec: number,
): number {
  const score = getScore(name);
  const mult = scoreToMultiplier(score);
  return Math.min(baseSec * mult, maxSec);
}

function scoreToMultiplier(score: number): number {
  if (score >= 0.9) return 1;
  if (score >= 0.7) return 2;
  if (score >= 0.5) return 4;
  if (score >= 0.3) return 6;
  if (score >= 0.1) return 10;
  return 16;
}

/** 启动时从磁盘恢复评分（ewma / failStreak / totals） */
export function loadScores(file: string = DEFAULT_SCORES_FILE): void {
  if (!existsSync(file)) return;
  try {
    const data = JSON.parse(readFileSync(file, "utf-8"));
    if (!data || typeof data !== "object") return;
    const scores = getAppContext().scores;
    for (const [name, rec] of Object.entries(data as Record<string, Partial<ScoreRecord>>)) {
      if (!rec || typeof rec !== "object") continue;
      scores.set(name, {
        ewma: typeof rec.ewma === "number" ? rec.ewma : INITIAL_SCORE,
        recentTs: typeof rec.recentTs === "number" ? rec.recentTs : Date.now(),
        failStreak: typeof rec.failStreak === "number" ? rec.failStreak : 0,
        lastSuccessTs: typeof rec.lastSuccessTs === "number" ? rec.lastSuccessTs : 0,
        totalSuccess: typeof rec.totalSuccess === "number" ? rec.totalSuccess : 0,
        totalFail: typeof rec.totalFail === "number" ? rec.totalFail : 0,
      });
    }
    console.log(`[scoring] loaded ${scores.size} scores from ${file}`);
  } catch (e) {
    console.warn("[scoring] failed to load scores:", (e as Error).message);
  }
}

export function persistScores(file: string = DEFAULT_SCORES_FILE): void {
  try {
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, JSON.stringify(getAllScores(), null, 2) + "\n");
  } catch (e) {
    console.warn("[scoring] failed to persist scores:", (e as Error).message);
  }
}

let _persistTimer: ReturnType<typeof setInterval> | null = null;

export function startScorePersistence(file: string = DEFAULT_SCORES_FILE, intervalMs = 60_000): void {
  if (_persistTimer) return;
  loadScores(file);
  _persistTimer = setInterval(() => persistScores(file), intervalMs);
  _persistTimer.unref?.();
  const flush = () => {
    try { persistScores(file); } catch { /* ignore */ }
  };
  process.once("beforeExit", flush);
  process.once("SIGINT", () => { flush(); });
  process.once("SIGTERM", () => { flush(); });
}
