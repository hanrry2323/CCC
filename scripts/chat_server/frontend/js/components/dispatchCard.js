/**
 * 对话下方「转任务」卡片：核实标题 → Skill 软偏好 → 下达并开工
 */

import { state } from '../state.js';
import { createBoardTask, loadProjects, loadSkills } from '../api.js';
import { escapeHtml } from '../utils.js';
import { parseDispatchBlock, findLatestDispatch } from './dispatchFormat.js';

const MAX_SKILLS = 3;

function nowIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? '+' : '-';
  const oh = pad(Math.floor(Math.abs(offset) / 60));
  const om = pad(Math.abs(offset) % 60);
  return (
    d.getFullYear() +
    '-' +
    pad(d.getMonth() + 1) +
    '-' +
    pad(d.getDate()) +
    'T' +
    pad(d.getHours()) +
    ':' +
    pad(d.getMinutes()) +
    ':' +
    pad(d.getSeconds()) +
    sign +
    oh +
    ':' +
    om
  );
}

function slugify(title) {
  const base =
    String(title || 'task')
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'task';
  const ascii =
    base.replace(/[^a-z0-9_-]+/g, '').replace(/^-+|-+$/g, '') || 'task';
  return ascii + '-' + Date.now().toString(36).slice(-4);
}

function projectToWorkspace(projectId) {
  const map = state.get('projectWorkspaceMap') || {};
  if (projectId && map[projectId]) return map[projectId];
  if (!projectId) return 'CCC';
  if (projectId === 'ccc') return 'CCC';
  return projectId;
}

function ensureHost() {
  let host = document.getElementById('dispatch-card-host');
  if (host) return host;
  const composer = document.getElementById('composer');
  if (!composer?.parentNode) return null;
  host = document.createElement('div');
  host.id = 'dispatch-card-host';
  host.className = 'dispatch-card-host';
  composer.parentNode.insertBefore(host, composer);
  return host;
}

function hideCard() {
  const host = document.getElementById('dispatch-card-host');
  if (host) {
    host.hidden = true;
    host.innerHTML = '';
  }
}

function skillChipsHtml(skills) {
  const list = skills || [];
  if (!list.length) {
    return (
      '<p class="dispatch-skill-empty">未扫描到可用 Skill；可手写 skill id（逗号分隔）。</p>'
    );
  }
  const common = list.filter((s) => s.tier === 'common').slice(0, 8);
  const specialized = list
    .filter((s) => s.tier !== 'common' && s.tier !== 'engine')
    .slice(0, 12);
  const engine = list.filter((s) => s.tier === 'engine').slice(0, 8);

  function chips(items) {
    return items
      .map(
        (s) =>
          '<button type="button" class="dispatch-skill-chip" data-skill="' +
          escapeHtml(s.id) +
          '" title="' +
          escapeHtml(s.description || s.name || s.id) +
          '">' +
          escapeHtml(s.name || s.id) +
          '</button>'
      )
      .join('');
  }

  let html = '';
  if (common.length) {
    html +=
      '<div class="dispatch-skill-group"><span class="dispatch-skill-group-label">常用</span><div class="dispatch-skill-chips">' +
      chips(common) +
      '</div></div>';
  }
  if (specialized.length) {
    html +=
      '<div class="dispatch-skill-group"><span class="dispatch-skill-group-label">专项</span><div class="dispatch-skill-chips">' +
      chips(specialized) +
      '</div></div>';
  }
  if (engine.length) {
    html +=
      '<div class="dispatch-skill-group"><span class="dispatch-skill-group-label">Engine 角色</span><div class="dispatch-skill-chips">' +
      chips(engine) +
      '</div></div>';
  }
  if (!html) {
    html =
      '<div class="dispatch-skill-chips">' + chips(list.slice(0, 16)) + '</div>';
  }
  return html;
}

/**
 * @param {object} opts
 * @param {object} [opts.parsed] parseDispatchBlock 结果
 * @param {string} [opts.content] 原始消息（无 parsed 时再解析）
 */
export async function showDispatchCard(opts = {}) {
  const host = ensureHost();
  if (!host) return;

  let parsed = opts.parsed;
  if (!parsed?.ok && opts.content) {
    parsed = parseDispatchBlock(opts.content);
  }
  if (!parsed?.ok) {
    const found = findLatestDispatch(state.get('currentMessages') || []);
    if (found?.parsed?.ok) parsed = found.parsed;
  }

  if (!parsed?.ok) {
    host.hidden = false;
    host.innerHTML =
      '<div class="dispatch-card dispatch-card--warn">' +
      '<div class="dispatch-card-title">还不能转任务</div>' +
      '<p class="dispatch-card-help">' +
      '<b>流程</b>：自由讨论 → <b>定稿方案</b>（产出 CCC_DISPATCH）→ <b>转任务</b>（核标题下达）。' +
      '<br>请先点工具条 <b>定稿方案</b>；核对无误后再点 <b>转任务</b>。</p>' +
      '<div class="dispatch-card-actions">' +
      '<button type="button" class="btn-secondary" id="dispatch-dismiss">关闭</button>' +
      '<button type="button" class="btn-primary" id="dispatch-finalize">去定稿方案</button>' +
      '</div></div>';
    host.querySelector('#dispatch-dismiss')?.addEventListener('click', hideCard);
    host.querySelector('#dispatch-finalize')?.addEventListener('click', () => {
      hideCard();
      import('./fixedActions.js').then((m) => {
        const act = m.FIXED_ACTIONS.find((a) => a.id === 'finalize-plan');
        if (act?.prompt) {
          import('./message.js').then((msg) =>
            msg.sendMessage(act.prompt, [], {
              uiLabel: act.uiLabel || act.label || '定稿方案',
            })
          );
        }
      });
    });
    return;
  }

  const projects = await loadProjects().catch(() => []);
  const dispatchable = projects.filter(
    (p) => p.role !== 'orch' && p.engine_eligible !== false
  );
  const optsSrc = dispatchable.length ? dispatchable : [];
  if (!optsSrc.length) {
    window.showToast?.(
      '无业务项目可下达。CCC 编排仓请用 Cursor 改；请先登记业务仓。',
      'error'
    );
    return;
  }
  const prefer =
    optsSrc.find((p) => p.id === state.get('currentProject')) ||
    optsSrc.find((p) => p.id === state.get('defaultProject')) ||
    optsSrc[0];
  const projectOpts = optsSrc
    .map(
      (p) =>
        '<option value="' +
        escapeHtml(p.id) +
        '"' +
        (p.id === prefer.id ? ' selected' : '') +
        '>' +
        escapeHtml(p.name) +
        '</option>'
    )
    .join('');

  const phaseCount = (parsed.phases_jsonl || '')
    .split('\n')
    .filter((l) => l.trim().startsWith('{') && l.includes('"phase"')).length;

  const projectId0 = prefer.id;
  let showEngine = false;
  let skillsPayload = { skills: [] };
  try {
    skillsPayload = await loadSkills(projectId0, { includeEngine: false });
  } catch {
    skillsPayload = { skills: [] };
  }

  const selected = new Set();

  host.hidden = false;
  host.innerHTML =
    '<div class="dispatch-card">' +
    '<div class="dispatch-card-head">' +
    '<span class="dispatch-card-badge">转任务</span>' +
    '<span class="dispatch-card-meta">定稿已就绪 · plan + ' +
    phaseCount +
    ' phase · 下达跳过 product</span>' +
    '<button type="button" class="dispatch-card-x" id="dispatch-dismiss" title="关闭">×</button>' +
    '</div>' +
    '<div class="dispatch-card-body">' +
    '<p class="dispatch-flow-hint">定稿方案 = 产出方案块；本卡 = 核实标题并下达开工。Skill 为可选软偏好，最多 ' +
    MAX_SKILLS +
    ' 个。</p>' +
    '<label class="dispatch-field"><span>标题</span>' +
    '<input type="text" id="dispatch-title" maxlength="500" value="' +
    escapeHtml(parsed.title) +
    '"></label>' +
    '<label class="dispatch-field"><span>项目</span>' +
    '<select id="dispatch-project">' +
    projectOpts +
    '</select></label>' +
    '<label class="dispatch-field"><span>复杂度</span>' +
    '<select id="dispatch-complexity">' +
    ['small', 'medium', 'large']
      .map(
        (c) =>
          '<option value="' +
          c +
          '"' +
          (c === parsed.complexity ? ' selected' : '') +
          '>' +
          c +
          '</option>'
      )
      .join('') +
    '</select></label>' +
    '<div class="dispatch-preview"><span class="dispatch-preview-label">方案摘要（只读）</span>' +
    '<pre>' +
    escapeHtml(parsed.summary || parsed.plan_md.slice(0, 400)) +
    '</pre></div>' +
    '<div class="dispatch-skills">' +
    '<div class="dispatch-skills-head">' +
    '<span class="dispatch-preview-label">Skill 偏好（可选）</span>' +
    '<span class="dispatch-skills-count" id="dispatch-skills-count">0/' +
    MAX_SKILLS +
    '</span>' +
    '</div>' +
    '<div id="dispatch-skill-chips">' +
    skillChipsHtml(skillsPayload.skills || []) +
    '</div>' +
    '<label class="dispatch-engine-toggle"><input type="checkbox" id="dispatch-show-engine"> 显示 Engine 角色（ccc-*）</label>' +
    '<input type="text" id="dispatch-skill-extra" class="dispatch-skill-extra" ' +
    'placeholder="或手写 skill id，逗号分隔" maxlength="200" autocomplete="off">' +
    '<input type="text" id="dispatch-skill-note" class="dispatch-skill-extra" ' +
    'placeholder="补充说明（可选）" maxlength="200" autocomplete="off">' +
    '</div>' +
    '</div>' +
    '<div class="dispatch-card-actions">' +
    '<button type="button" class="btn-secondary" id="dispatch-dismiss2">取消</button>' +
    '<button type="button" class="btn-primary" id="dispatch-submit">下达并开工</button>' +
    '</div></div>';

  const close = () => hideCard();
  host.querySelector('#dispatch-dismiss')?.addEventListener('click', close);
  host.querySelector('#dispatch-dismiss2')?.addEventListener('click', close);

  const countEl = host.querySelector('#dispatch-skills-count');
  const syncCount = () => {
    if (countEl) countEl.textContent = selected.size + '/' + MAX_SKILLS;
  };

  host.querySelector('#dispatch-skill-chips')?.addEventListener('click', (e) => {
    const btn = e.target.closest('.dispatch-skill-chip');
    if (!btn) return;
    const id = btn.getAttribute('data-skill');
    if (!id) return;
    if (selected.has(id)) {
      selected.delete(id);
      btn.classList.remove('is-on');
    } else if (selected.size < MAX_SKILLS) {
      selected.add(id);
      btn.classList.add('is-on');
    } else {
      window.showToast?.('最多选 ' + MAX_SKILLS + ' 个 Skill', 'error');
    }
    syncCount();
  });

  async function reloadSkills(pid) {
    const chips = host.querySelector('#dispatch-skill-chips');
    if (!chips) return;
    try {
      const data = await loadSkills(pid, { includeEngine: showEngine });
      chips.innerHTML = skillChipsHtml(data.skills || []);
      selected.clear();
      syncCount();
    } catch {
      /* keep */
    }
  }

  host.querySelector('#dispatch-show-engine')?.addEventListener('change', (e) => {
    showEngine = !!e.target.checked;
    const pid =
      host.querySelector('#dispatch-project')?.value || state.get('currentProject');
    reloadSkills(pid);
  });

  host.querySelector('#dispatch-project')?.addEventListener('change', async (e) => {
    await reloadSkills(e.target.value);
  });

  host.querySelector('#dispatch-submit')?.addEventListener('click', async () => {
    const title = host.querySelector('#dispatch-title')?.value.trim();
    const complexity =
      host.querySelector('#dispatch-complexity')?.value || parsed.complexity;
    const projectId =
      host.querySelector('#dispatch-project')?.value || state.get('currentProject');
    if (!title) {
      window.showToast?.('请填写标题', 'error');
      return;
    }
    const meta = projects.find((p) => p.id === projectId);
    if (meta && (meta.role === 'orch' || meta.engine_eligible === false)) {
      window.showToast?.(
        'CCC 编排仓不可下达。平台请用 Cursor 改 CCC；业务请选登记项目。',
        'error'
      );
      return;
    }
    const btn = host.querySelector('#dispatch-submit');
    if (btn) btn.disabled = true;
    const ts = nowIso();
    const id = slugify(title);
    const workspace = projectToWorkspace(projectId);
    const description =
      '（定稿投递）详见已挂载 plan/phases。\n\n' + (parsed.summary || title);

    const extraRaw = host.querySelector('#dispatch-skill-extra')?.value || '';
    const note = (host.querySelector('#dispatch-skill-note')?.value || '').trim();
    const skills = [...selected];
    for (const part of extraRaw.split(/[,，\s]+/)) {
      const s = part.trim();
      if (s && !skills.includes(s) && skills.length < MAX_SKILLS) skills.push(s);
    }
    const hints =
      skills.length || note
        ? { ...(skills.length ? { skills } : {}), ...(note ? { note } : {}) }
        : undefined;

    try {
      const payload = {
        id,
        title,
        description,
        status: 'backlog',
        created_at: ts,
        updated_at: ts,
        schema_version: '1.2',
        complexity,
        tags: ['from-chat', 'dispatch-card'],
        workspace,
        plan_md: parsed.plan_md,
        phases_jsonl: parsed.phases_jsonl,
      };
      if (hints) payload.hints = hints;

      const res = await createBoardTask(payload);
      const tid = res.task_id || id;
      const skip =
        res.skip_product || (res.seeded?.plan && res.seeded?.phases)
          ? '（已挂 plan，跳过 product）'
          : '';
      const wake = res.engine_wake || res.plan_adopt;
      const wakeHint =
        wake && wake.ok !== false ? ' · Engine 已唤醒' : ' · 请确认 Engine';
      const skillHint = skills.length ? ' · Skill×' + skills.length : '';
      window.showToast?.('已下达 ' + tid + skip + wakeHint + skillHint, 'success');
      document.dispatchEvent(
        new CustomEvent('ccc-task-dispatched', { detail: { id: tid, workspace } })
      );
      hideCard();
      import('./boardPanel.js').then((m) => {
        m.openBoardPanel?.();
        m.trackDispatchedTask?.(tid, workspace);
        m.refreshBoardPanel?.();
      });
    } catch (err) {
      window.showToast?.(err.message || '下达失败', 'error');
      if (btn) btn.disabled = false;
    }
  });
}

/** 消息「转任务」入口：有定稿块则出卡片，否则引导定稿 */
export function openTransferFromMessage(content) {
  const parsed = parseDispatchBlock(content || '');
  showDispatchCard({ parsed, content });
}

export function openTransferFromLatest() {
  showDispatchCard({});
}
