import { state } from './state.js';

/** F-SEC-01/02: 不硬编码口令；首次从 localStorage / prompt 取。 */
function _authHeader() {
  let user = localStorage.getItem('ccc_chat_user') || 'ccc';
  let pass = localStorage.getItem('ccc_chat_pass') || '';
  if (!pass) {
    pass = window.prompt('CCC Chat 密码（写入 localStorage，不会提交到仓库）') || '';
    if (pass) localStorage.setItem('ccc_chat_pass', pass);
  }
  return 'Basic ' + btoa(user + ':' + pass);
}

function _headers(json = true) {
  const h = { Authorization: _authHeader() };
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

export async function apiGet(path) {
  const resp = await fetch(path, { headers: _headers(false) });
  if (!resp.ok) throw new Error('GET ' + path + ' ' + resp.status);
  return resp.json();
}

export async function apiPost(path, body) {
  const resp = await fetch(path, {
    method: 'POST',
    headers: _headers(true),
    body: JSON.stringify(body || {}),
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const msg = data.message || data.error || ('POST ' + path + ' ' + resp.status);
    throw new Error(msg);
  }
  return data;
}

export async function apiDelete(path) {
  const resp = await fetch(path, { method: 'DELETE', headers: _headers(false) });
  return resp.json();
}

export async function loadProjects() {
  const data = await apiGet('/api/projects');
  return data.projects;
}

export async function loadHistory(project) {
  const data = await apiGet('/api/history?project=' + encodeURIComponent(project));
  return data.sessions;
}

export async function loadSession(id, project) {
  return await apiGet('/api/history/' + id + '?project=' + encodeURIComponent(project));
}

export async function deleteSession(id, project) {
  return await apiDelete('/api/history/' + id + '?project=' + encodeURIComponent(project));
}

export async function loadBoard(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/board' + qs);
}

export async function loadBoardDashboard(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/dashboard' + qs);
}

export async function createBoardTask(task) {
  return apiPost('/api/board/proxy/tasks', task);
}

export async function moveBoardTask(payload) {
  return apiPost('/api/board/proxy/tasks/move', payload);
}

export async function listProjectFiles(projectId, path = '') {
  const qs = path ? ('?path=' + encodeURIComponent(path)) : '';
  return apiGet('/api/projects/' + encodeURIComponent(projectId) + '/files' + qs);
}

export async function readProjectFile(projectId, path) {
  return apiGet(
    '/api/projects/' + encodeURIComponent(projectId) + '/file?path=' + encodeURIComponent(path)
  );
}

export async function streamChat(messages, sessionId, project, onEvent, onDone, onError, attachments) {
  const abortController = new AbortController();
  state.set('abortController', abortController);

  try {
    const model = state.get('model') || 'flash';
    const body = {
      messages,
      session_id: sessionId,
      project,
      model,
      timeout: 180,
    };
    if (attachments && attachments.length) {
      body.attachments = attachments;
    }

    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: _headers(true),
      body: JSON.stringify(body),
      signal: abortController.signal,
    });

    if (!resp.ok) {
      const errText = resp.status === 400 ? '危险指令已被拦截或附件无效'
        : resp.status === 429 ? '前一个执行中，请稍候'
        : '请求失败: HTTP ' + resp.status;
      onError(errText);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'delta') {
            onEvent('delta', data.content);
          } else if (data.type === 'tool_use') {
            onEvent('tool_use', data);
          } else if (data.type === 'tool_result') {
            onEvent('tool_result', data);
          } else if (data.type === 'cost') {
            onEvent('cost', data);
          } else if (data.type === 'done') {
            onDone(data.session_id || sessionId);
          } else if (data.type === 'error') {
            onError(data.content);
          }
        } catch (e) { /* skip bad json */ }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      onError('网络错误: ' + e.message);
    }
  } finally {
    state.set('abortController', null);
  }
}

export function cancelStream() {
  const ac = state.get('abortController');
  if (ac) ac.abort();
}
