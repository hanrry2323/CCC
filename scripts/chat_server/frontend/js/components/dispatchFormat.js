/**
 * CCC 对话→任务标准投递格式（v0.42.2）
 *
 * 流程：讨论 →「定稿方案」→ Claude 输出 CCC_DISPATCH 块 →「转任务」卡片 → 下达并开工
 */

import { FINALIZE_WORK_PREFIX } from './quickPrompts.js';

export const FINALIZE_PLAN_PROMPT =
  FINALIZE_WORK_PREFIX +
  '<<<CCC_DISPATCH>>>\n' +
  'title: <一句可执行中文标题，≤40字>\n' +
  'complexity: small|medium|large\n' +
  '---PLAN---\n' +
  '# Plan: <标题>\n\n' +
  '## 目标\n' +
  '- …\n\n' +
  '## 范围\n' +
  '- **只改文件**: path1, path2\n\n' +
  '## Phase 1：…\n' +
  '做什么 / 怎么做 / 涉及文件\n\n' +
  '## 验收\n' +
  '- <可执行意图或命令，至少 1 条>\n' +
  '---END_PLAN---\n' +
  '---PHASES---\n' +
  '{"phase":1,"status":"pending","description":"…","scope":["相对路径"],"subtasks":{"1.1":"pending"},"timeout":600,"depends_on":[]}\n' +
  '（多 phase 则每行一个 JSON；scope 必须非空，禁止 ["all"]）\n' +
  '---END_PHASES---\n' +
  '<<<END_CCC_DISPATCH>>>\n\n' +
  '硬规则：scope 必须真实存在；必须有 ## 验收；不要写源码正文；不要 markdown 围栏包住整块。';

const BLOCK_RE =
  /<<<CCC_DISPATCH>>>\s*([\s\S]*?)\s*<<<END_CCC_DISPATCH>>>/i;
const TITLE_RE = /^title:\s*(.+)$/im;
const COMPLEXITY_RE = /^complexity:\s*(small|medium|large)\s*$/im;
const PLAN_RE = /---PLAN---\s*([\s\S]*?)\s*---END_PLAN---/i;
const PHASES_RE = /---PHASES---\s*([\s\S]*?)\s*---END_PHASES---/i;

/**
 * @returns {{ ok: boolean, title?: string, complexity?: string, plan_md?: string, phases_jsonl?: string, error?: string, raw?: string }}
 */
export function parseDispatchBlock(text) {
  const src = String(text || '');
  const m = BLOCK_RE.exec(src);
  if (!m) {
    return { ok: false, error: 'no_dispatch_block', raw: src.slice(0, 200) };
  }
  const body = m[1];
  const titleM = TITLE_RE.exec(body);
  const title = (titleM?.[1] || '').trim();
  if (!title) {
    return { ok: false, error: 'missing_title' };
  }
  const cM = COMPLEXITY_RE.exec(body);
  const complexity = (cM?.[1] || 'medium').toLowerCase();
  const planM = PLAN_RE.exec(body);
  const plan_md = (planM?.[1] || '').trim();
  if (!plan_md) {
    return { ok: false, error: 'missing_plan' };
  }
  if (!/^##\s*验收/m.test(plan_md) && !/^##\s*验证/m.test(plan_md)) {
    return { ok: false, error: 'plan_missing_acceptance' };
  }
  const phasesM = PHASES_RE.exec(body);
  const phasesRaw = (phasesM?.[1] || '').trim();
  if (!phasesRaw) {
    return { ok: false, error: 'missing_phases' };
  }
  const phaseLines = [];
  for (const line of phasesRaw.split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('（') || t.startsWith('(')) continue;
    try {
      const obj = JSON.parse(t);
      if (obj && typeof obj === 'object' && obj.phase != null) {
        phaseLines.push(JSON.stringify(obj));
      }
    } catch {
      /* skip non-json commentary */
    }
  }
  if (!phaseLines.length) {
    return { ok: false, error: 'phases_not_json' };
  }
  const schema = JSON.stringify({ schema_version: '1.1' });
  return {
    ok: true,
    title,
    complexity: ['small', 'medium', 'large'].includes(complexity)
      ? complexity
      : 'medium',
    plan_md,
    phases_jsonl: schema + '\n' + phaseLines.join('\n') + '\n',
    summary: plan_md.split('\n').slice(0, 8).join('\n').slice(0, 400),
  };
}

/** 从消息中找最近一条含定稿块的 assistant 内容 */
export function findLatestDispatch(messages) {
  const list = Array.isArray(messages) ? messages : [];
  for (let i = list.length - 1; i >= 0; i--) {
    const msg = list[i];
    if (msg?.role !== 'assistant') continue;
    const parsed = parseDispatchBlock(msg.content || '');
    if (parsed.ok) return { index: i, parsed, content: msg.content };
  }
  return null;
}
