/** Hub 远程管理对话页 — 会话分区（hub::），薄 UI */

import {
  apiGet,
  apiPost,
  loadProjects,
  streamRemoteChat,
  cancelRemoteChat,
} from '../api.js';

let _root = null;
let _state = {
  project: '',
  threadId: '',
  toolMode: 'discuss',
  messages: [],
  claudeSessionId: '',
  streaming: false,
  transferResult: null,
};

function _esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function _defaultThread(project) {
  return `hub::${project || 'ccc'}::main`;
}

function _renderMessages() {
  const box = _root?.querySelector('#rc-messages');
  if (!box) return;
  if (!_state.messages.length) {
    box.innerHTML =
      '<div class="rc-empty">在此远程对齐基线 / 讨论方案 / 下达任务。<br>' +
      '与 Desktop 本机会话相互独立。</div>';
    return;
  }
  box.innerHTML = _state.messages
    .map((m) => {
      const role = m.role === 'user' ? 'user' : 'assistant';
      const label = role === 'user' ? '你' : 'Hub';
      return (
        `<div class="rc-msg rc-${role}"><div class="rc-role">${label}</div>` +
        `<pre class="rc-body">${_esc(m.content || '')}</pre></div>`
      );
    })
    .join('');
  box.scrollTop = box.scrollHeight;
}

function _setStatus(text, kind) {
  const el = _root?.querySelector('#rc-status');
  if (!el) return;
  el.textContent = text || '';
  el.dataset.kind = kind || '';
}

async function _loadHistory() {
  const qs =
    '?project=' +
    encodeURIComponent(_state.project) +
    '&thread_id=' +
    encodeURIComponent(_state.threadId);
  const data = await apiGet('/api/remote-chat/history' + qs);
  _state.messages = data.messages || [];
  _state.claudeSessionId = data.claude_session_id || '';
  _renderMessages();
}

async function _send() {
  if (_state.streaming) return;
  const input = _root.querySelector('#rc-input');
  const text = (input?.value || '').trim();
  if (!text) return;
  input.value = '';
  _state.messages.push({ role: 'user', content: text });
  _state.messages.push({ role: 'assistant', content: '' });
  _renderMessages();
  _state.streaming = true;
  _setStatus('流式中…', 'busy');
  const stopBtn = _root.querySelector('#rc-stop');
  if (stopBtn) stopBtn.disabled = false;

  let assistant = _state.messages[_state.messages.length - 1];
  try {
    await streamRemoteChat(
      {
        project: _state.project,
        thread_id: _state.threadId,
        message: text,
        tool_mode: _state.toolMode,
        claude_session_id: _state.claudeSessionId || undefined,
      },
      (evt) => {
        if (evt.type === 'delta' && evt.content) {
          assistant.content += evt.content;
          _renderMessages();
        } else if (evt.type === 'error') {
          assistant.content +=
            (assistant.content ? '\n' : '') + '[错误] ' + (evt.content || '');
          _renderMessages();
        } else if (evt.type === 'done') {
          if (evt.claude_session_id) {
            _state.claudeSessionId = evt.claude_session_id;
          }
        }
      }
    );
    _setStatus('完成', 'ok');
  } catch (err) {
    assistant.content +=
      (assistant.content ? '\n' : '') + '[失败] ' + (err.message || err);
    _renderMessages();
    _setStatus(String(err.message || err), 'err');
  } finally {
    _state.streaming = false;
    if (stopBtn) stopBtn.disabled = true;
  }
}

async function _stop() {
  try {
    await cancelRemoteChat(_state.project, _state.threadId);
    _setStatus('已停止', 'ok');
  } catch (err) {
    _setStatus(String(err.message || err), 'err');
  }
}

async function _transfer() {
  const title = (_root.querySelector('#rc-tf-title')?.value || '').trim();
  const goal = (_root.querySelector('#rc-tf-goal')?.value || '').trim();
  const acceptanceRaw = (
    _root.querySelector('#rc-tf-acceptance')?.value || ''
  ).trim();
  const acceptance = acceptanceRaw
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
  if (!title || !goal || !acceptance.length) {
    _setStatus('转任务需填写标题、目标、验收（每行一条）', 'err');
    return;
  }
  const body = {
    project_id: _state.project,
    thread_id: _state.threadId,
    client_request_id:
      'hub-remote-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    title,
    goal,
    acceptance,
    pipeline: 'dev',
    feasibility: 'ok',
    executor_intent: 'opencode',
    plan_md:
      '# Plan\n\n## 目标\n' +
      goal +
      '\n\n## 验收\n' +
      acceptance.map((a) => '- ' + a).join('\n') +
      '\n',
  };
  _setStatus('下达中…', 'busy');
  try {
    const data = await apiPost('/api/desktop/transfer', body);
    _state.transferResult = data;
    if (data.ok) {
      _setStatus(
        '已下达 epic ' + data.epic_id + (data.idempotent_replay ? '（幂等）' : ''),
        'ok'
      );
      const out = _root.querySelector('#rc-tf-result');
      if (out) {
        out.textContent = JSON.stringify(data, null, 2);
      }
    } else {
      _setStatus(data.message || data.error || 'transfer 失败', 'err');
    }
  } catch (err) {
    _setStatus(String(err.message || err), 'err');
  }
}

function _bind() {
  _root.querySelector('#rc-send')?.addEventListener('click', () => _send());
  _root.querySelector('#rc-stop')?.addEventListener('click', () => _stop());
  _root.querySelector('#rc-transfer')?.addEventListener('click', () => _transfer());
  _root.querySelector('#rc-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      _send();
    }
  });
  _root.querySelector('#rc-mode')?.addEventListener('change', (e) => {
    _state.toolMode = e.target.value === 'engineer' ? 'engineer' : 'discuss';
  });
  _root.querySelector('#rc-project')?.addEventListener('change', async (e) => {
    _state.project = e.target.value;
    _state.threadId = _defaultThread(_state.project);
    _state.claudeSessionId = '';
    try {
      localStorage.setItem('ccc_hub_last_project', _state.project);
    } catch (_) {}
    const tidEl = _root.querySelector('#rc-thread');
    if (tidEl) tidEl.textContent = _state.threadId;
    await _loadHistory();
  });
}

export async function mountChat(root) {
  _root = root;
  let projects = [];
  try {
    projects = await loadProjects();
  } catch (err) {
    root.innerHTML =
      '<div class="rc-banner">项目加载失败：' + _esc(err.message) + '</div>';
    return;
  }
  const last =
    localStorage.getItem('ccc_hub_last_project') ||
    projects.find((p) => p.engine_eligible)?.id ||
    projects[0]?.id ||
    'ccc';
  _state.project = last;
  _state.threadId = _defaultThread(last);
  _state.toolMode = 'discuss';
  _state.messages = [];
  _state.claudeSessionId = '';

  const opts = projects
    .map(
      (p) =>
        `<option value="${_esc(p.id)}"${p.id === last ? ' selected' : ''}>` +
        `${_esc(p.name || p.id)}${p.engine_eligible ? '' : '（不可下达）'}</option>`
    )
    .join('');

  root.innerHTML = `
<div class="rc-shell">
  <div class="rc-banner">本页为 Hub 远程会话，与 Desktop 本机会话相互独立；看板与下达任务共用。</div>
  <div class="rc-toolbar">
    <label>项目 <select id="rc-project">${opts}</select></label>
    <label>模式
      <select id="rc-mode">
        <option value="discuss" selected>讨论（只读）</option>
        <option value="engineer">工程师（可写）</option>
      </select>
    </label>
    <code id="rc-thread" class="rc-thread">${_esc(_state.threadId)}</code>
    <span id="rc-status" class="rc-status"></span>
  </div>
  <div id="rc-messages" class="rc-messages"></div>
  <div class="rc-composer">
    <textarea id="rc-input" rows="3" placeholder="远程聊任务…（⌘/Ctrl+Enter 发送）"></textarea>
    <div class="rc-actions">
      <button type="button" id="rc-send" class="rc-btn primary">发送</button>
      <button type="button" id="rc-stop" class="rc-btn" disabled>停止</button>
    </div>
  </div>
  <details class="rc-transfer" open>
    <summary>下达任务卡（transfer）</summary>
    <div class="rc-tf-grid">
      <input id="rc-tf-title" placeholder="标题" />
      <textarea id="rc-tf-goal" rows="2" placeholder="目标"></textarea>
      <textarea id="rc-tf-acceptance" rows="3" placeholder="验收（每行一条）"></textarea>
      <button type="button" id="rc-transfer" class="rc-btn primary">确认转任务</button>
      <pre id="rc-tf-result" class="rc-tf-result"></pre>
    </div>
  </details>
</div>`;

  _bind();
  _renderMessages();
  try {
    await _loadHistory();
  } catch (err) {
    _setStatus('历史加载失败：' + (err.message || err), 'err');
  }
}

export function unmountChat() {
  _root = null;
}
