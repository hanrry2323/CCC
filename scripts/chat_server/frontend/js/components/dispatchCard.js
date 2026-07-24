/**
 * 对话下方「转任务」卡片：核实标题 → Skill 软偏好 → POST /api/desktop/transfer
 * 对齐 Desktop App / transfer-gate（ccc-transfer）。
 */

import { state } from '../state.js';
import {
  desktopTransfer,
  nudgeOutboxFlush,
  loadProjects,
  loadSkills,
} from '../api.js';
import { escapeHtml, desktopThreadId, generateId } from '../utils.js';
import { parseDispatchBlock, findLatestDispatch } from './dispatchFormat.js';

const MAX_SKILLS = 3;

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
      '<b>流程</b>：自由讨论 → <b>定稿方案</b>（产出 <code>ccc-transfer</code>）→ <b>转任务</b>（核标题下达）。' +
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

  const locked = parsed.source === 'ccc-transfer';
  const projectId0 = prefer.id;
  let showEngine = false;
  let skillsPayload = { skills: [] };
  try {
    skillsPayload = await loadSkills(projectId0, { includeEngine: false });
  } catch {
    skillsPayload = { skills: [] };
  }

  const selected = new Set(parsed.skills_hint || []);

  host.hidden = false;
  host.innerHTML =
    '<div class="dispatch-card">' +
    '<div class="dispatch-card-head">' +
    '<span class="dispatch-card-badge">转任务</span>' +
    '<span class="dispatch-card-meta">' +
    (locked ? '定稿已就绪 · ccc-transfer' : '兼容旧定稿块') +
    ' · 过桥 Hub transfer</span>' +
    '<button type="button" class="dispatch-card-x" id="dispatch-dismiss" title="关闭">×</button>' +
    '</div>' +
    '<div class="dispatch-card-body">' +
    '<p class="dispatch-flow-hint">标题可改；方案字段只读。Skill 为可选软偏好，最多 ' +
    MAX_SKILLS +
    ' 个。</p>' +
    '<label class="dispatch-field"><span>标题</span>' +
    '<input type="text" id="dispatch-title" maxlength="80" value="' +
    escapeHtml(parsed.title) +
    '"></label>' +
    '<label class="dispatch-field"><span>项目</span>' +
    '<select id="dispatch-project">' +
    projectOpts +
    '</select></label>' +
    '<label class="dispatch-field"><span>备注（可选）</span>' +
    '<input type="text" id="dispatch-human-note" maxlength="200" value="' +
    escapeHtml(parsed.human_note || '') +
    '" placeholder="人工备注"></label>' +
    '<div class="dispatch-preview"><span class="dispatch-preview-label">方案摘要（只读）</span>' +
    '<pre>' +
    escapeHtml(parsed.summary || parsed.goal || '') +
    '</pre></div>' +
    '<div class="dispatch-skills">' +
    '<div class="dispatch-skills-head">' +
    '<span class="dispatch-preview-label">Skill 偏好（可选）</span>' +
    '<span class="dispatch-skills-count" id="dispatch-skills-count">' +
    selected.size +
    '/' +
    MAX_SKILLS +
    '</span>' +
    '</div>' +
    '<div id="dispatch-skill-chips">' +
    skillChipsHtml(skillsPayload.skills || []) +
    '</div>' +
    '<label class="dispatch-engine-toggle"><input type="checkbox" id="dispatch-show-engine"> 显示 Engine 角色（ccc-*）</label>' +
    '<input type="text" id="dispatch-skill-extra" class="dispatch-skill-extra" ' +
    'placeholder="或手写 skill id，逗号分隔" maxlength="200" autocomplete="off">' +
    '</div>' +
    '</div>' +
    '<div class="dispatch-card-actions">' +
    '<button type="button" class="btn-secondary" id="dispatch-dismiss2">取消</button>' +
    '<button type="button" class="btn-primary" id="dispatch-submit">确认转任务</button>' +
    '</div></div>';

  // 预亮已选 skill
  host.querySelectorAll('.dispatch-skill-chip').forEach((btn) => {
    const id = btn.getAttribute('data-skill');
    if (id && selected.has(id)) btn.classList.add('is-on');
  });

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
    const projectId =
      host.querySelector('#dispatch-project')?.value || state.get('currentProject');
    const humanNote = (
      host.querySelector('#dispatch-human-note')?.value || ''
    ).trim();
    if (!title) {
      window.showToast?.('请填写标题', 'error');
      return;
    }
    if (parsed.feasibility && parsed.feasibility !== 'ok') {
      window.showToast?.(
        '可行性非 ok：' + (parsed.feasibility_reason || parsed.feasibility),
        'error'
      );
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

    const extraRaw = host.querySelector('#dispatch-skill-extra')?.value || '';
    const skills = [...selected];
    for (const part of extraRaw.split(/[,，\s]+/)) {
      const s = part.trim();
      if (s && !skills.includes(s) && skills.length < MAX_SKILLS) skills.push(s);
    }

    const threadId =
      state.get('currentSessionId') ||
      desktopThreadId(projectId || 'ccc', 'main');
    const clientRequestId =
      'http-' + Date.now().toString(36) + '-' + (generateId?.() || Math.random().toString(36).slice(2, 8));

    try {
      const payload = {
        project_id: projectId,
        thread_id: threadId,
        client_request_id: clientRequestId,
        title,
        goal: parsed.goal || title,
        acceptance: parsed.acceptance || ['见 plan_md'],
        pipeline: parsed.pipeline || 'dev',
        feasibility: parsed.feasibility || 'ok',
        feasibility_reason: parsed.feasibility_reason || '',
        executor_intent: parsed.executor_intent || 'opencode',
        skills_hint: skills,
        plan_md: parsed.plan_md || '',
        complexity: parsed.complexity || 'medium',
      };
      if (humanNote) payload.human_note = humanNote;
      if (parsed.bump_version) payload.bump_version = true;

      const res = await desktopTransfer(payload);
      nudgeOutboxFlush().catch(() => {});
      const tid = res.epic_id;
      const wake = res.engine_wake;
      const wakeHint =
        wake && wake.ok !== false ? ' · Engine 已唤醒' : '';
      const skillHint = skills.length ? ' · Skill×' + skills.length : '';
      window.showToast?.(
        '已下达 ' + tid + wakeHint + skillHint,
        'success'
      );
      document.dispatchEvent(
        new CustomEvent('ccc-task-dispatched', {
          detail: { id: tid, workspace: res.workspace || projectId },
        })
      );
      hideCard();
      import('./boardPanel.js').then((m) => {
        m.openBoardPanel?.();
        m.trackDispatchedTask?.(tid, res.workspace || projectId);
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
