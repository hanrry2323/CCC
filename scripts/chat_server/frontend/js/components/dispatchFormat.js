/**
 * 定稿协议：主路径 ```ccc-transfer``` JSON（对齐 Desktop / transfer-gate）。
 * 旧 <<<CCC_DISPATCH>>> 仅兼容回退。
 */

import { FINALIZE_WORK_PREFIX } from './quickPrompts.js';

/** 定稿快捷词：与 App QuickPrompts 一致，要求产出 ccc-transfer。 */
export const FINALIZE_PLAN_PROMPT = FINALIZE_WORK_PREFIX;

const TRANSFER_FENCE_RE =
  /```\s*ccc-transfer\s*\r?\n([\s\S]*?)\r?\n```/i;
const LEGACY_BLOCK_RE =
  /<<<CCC_DISPATCH>>>\s*([\s\S]*?)\s*<<<END_CCC_DISPATCH>>>/i;
const TITLE_RE = /^title:\s*(.+)$/im;
const COMPLEXITY_RE = /^complexity:\s*(small|medium|large)\s*$/im;
const PLAN_RE = /---PLAN---\s*([\s\S]*?)\s*---END_PLAN---/i;
const PHASES_RE = /---PHASES---\s*([\s\S]*?)\s*---END_PHASES---/i;

function _asStringArray(v) {
  if (Array.isArray(v)) {
    return v.map((x) => String(x || '').trim()).filter(Boolean);
  }
  if (typeof v === 'string' && v.trim()) return [v.trim()];
  return [];
}

/**
 * @returns {object} 统一字段：ok, source, title, goal, acceptance, pipeline,
 *   feasibility, feasibility_reason, executor_intent, skills_hint, plan_md,
 *   complexity, summary, error?
 */
export function parseDispatchBlock(text) {
  const src = String(text || '');
  const fence = TRANSFER_FENCE_RE.exec(src);
  if (fence) {
    let obj;
    try {
      obj = JSON.parse(fence[1].trim());
    } catch (e) {
      return { ok: false, error: 'transfer_json_invalid', raw: fence[1].slice(0, 200) };
    }
    if (!obj || typeof obj !== 'object') {
      return { ok: false, error: 'transfer_not_object' };
    }
    const title = String(obj.title || '').trim();
    if (!title) return { ok: false, error: 'missing_title' };
    const goal = String(obj.goal || '').trim();
    const plan_md = String(obj.plan_md || obj.plan || '').trim();
    const acceptance = _asStringArray(obj.acceptance);
    if (!goal && !plan_md) {
      return { ok: false, error: 'missing_goal_or_plan' };
    }
    const complexity = String(obj.complexity || 'medium').toLowerCase();
    const skills = _asStringArray(obj.skills_hint || obj.skills);
    return {
      ok: true,
      source: 'ccc-transfer',
      title,
      goal: goal || title,
      acceptance: acceptance.length ? acceptance : ['见 plan_md 验收'],
      pipeline: String(obj.pipeline || 'dev').trim() || 'dev',
      feasibility: String(obj.feasibility || 'ok').trim() || 'ok',
      feasibility_reason: String(obj.feasibility_reason || '').trim(),
      executor_intent: String(obj.executor_intent || 'opencode').trim() || 'opencode',
      skills_hint: skills,
      plan_md: plan_md || ('# Plan\n\n## 目标\n' + (goal || title) + '\n'),
      complexity: ['small', 'medium', 'large'].includes(complexity)
        ? complexity
        : 'medium',
      bump_version: !!obj.bump_version,
      human_note: String(obj.human_note || '').trim(),
      summary: (goal || plan_md).split('\n').slice(0, 8).join('\n').slice(0, 400),
      raw_json: fence[1].trim(),
    };
  }

  // 兼容旧 CCC_DISPATCH
  const m = LEGACY_BLOCK_RE.exec(src);
  if (!m) {
    return { ok: false, error: 'no_dispatch_block', raw: src.slice(0, 200) };
  }
  const body = m[1];
  const titleM = TITLE_RE.exec(body);
  const title = (titleM?.[1] || '').trim();
  if (!title) return { ok: false, error: 'missing_title' };
  const cM = COMPLEXITY_RE.exec(body);
  const complexity = (cM?.[1] || 'medium').toLowerCase();
  const planM = PLAN_RE.exec(body);
  const plan_md = (planM?.[1] || '').trim();
  if (!plan_md) return { ok: false, error: 'missing_plan' };
  const acceptLines = [];
  const acceptSec = plan_md.match(/^##\s*(验收|验证)\s*\n([\s\S]*?)(?=\n##\s|\s*$)/m);
  if (acceptSec) {
    for (const line of acceptSec[2].split('\n')) {
      const t = line.replace(/^[-*]\s*/, '').trim();
      if (t) acceptLines.push(t);
    }
  }
  const goalMatch = plan_md.match(/^##\s*目标\s*\n([\s\S]*?)(?=\n##\s|\s*$)/m);
  const goal =
    (goalMatch?.[1] || '')
      .split('\n')
      .map((l) => l.replace(/^[-*]\s*/, '').trim())
      .filter(Boolean)
      .join('；') || title;
  return {
    ok: true,
    source: 'ccc-dispatch-legacy',
    title,
    goal,
    acceptance: acceptLines.length ? acceptLines : ['见 plan_md 验收'],
    pipeline: 'dev',
    feasibility: 'ok',
    feasibility_reason: '',
    executor_intent: 'opencode',
    skills_hint: [],
    plan_md,
    complexity: ['small', 'medium', 'large'].includes(complexity)
      ? complexity
      : 'medium',
    summary: plan_md.split('\n').slice(0, 8).join('\n').slice(0, 400),
  };
}

/** 从助手正文去掉 ccc-transfer fence，留给折叠块展示。 */
export function stripTransferFence(text) {
  return String(text || '').replace(TRANSFER_FENCE_RE, '').trim();
}

export function extractTransferFenceJSON(text) {
  const m = TRANSFER_FENCE_RE.exec(String(text || ''));
  return m ? m[1].trim() : null;
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
