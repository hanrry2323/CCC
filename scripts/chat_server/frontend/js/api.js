import { state } from './state.js';

/** Hub Basic Auth：默认用户名/密码均为 ccc；可被 localStorage 覆盖。 */
function _authHeader(forcePrompt = false) {
  // 一次性清掉旧长口令缓存，避免 401 死循环
  if (!localStorage.getItem('ccc_hub_auth_v2')) {
    localStorage.removeItem('ccc_chat_pass');
    localStorage.setItem('ccc_hub_auth_v2', '1');
  }
  let user = localStorage.getItem('ccc_chat_user') || 'ccc';
  let pass = forcePrompt ? '' : (localStorage.getItem('ccc_chat_pass') || 'ccc');
  if (!pass) {
    pass = window.prompt('CCC Hub 密码（用户名/密码默认均为 ccc）') || '';
    if (pass) localStorage.setItem('ccc_chat_pass', pass);
  }
  if (!localStorage.getItem('ccc_chat_user')) {
    localStorage.setItem('ccc_chat_user', user);
  }
  if (!localStorage.getItem('ccc_chat_pass') && pass === 'ccc') {
    localStorage.setItem('ccc_chat_pass', 'ccc');
  }
  return 'Basic ' + btoa(user + ':' + pass);
}

function _clearAuth() {
  localStorage.removeItem('ccc_chat_pass');
}

function _headers(json = true, forcePrompt = false) {
  const h = { Authorization: _authHeader(forcePrompt) };
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

/** On 401: clear stored password, re-prompt once, retry the request. */
async function _fetchWithAuth(url, options = {}, json = true) {
  let resp = await fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), ..._headers(json, false) },
  });
  if (resp.status === 401) {
    _clearAuth();
    window.showToast?.('认证失败，请重新输入密码', 'error');
    resp = await fetch(url, {
      ...options,
      headers: { ...(options.headers || {}), ..._headers(json, true) },
    });
  }
  return resp;
}

export async function apiGet(path) {
  const resp = await _fetchWithAuth(path, { method: 'GET' }, false);
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('认证失败 (401)：密码错误，请刷新后重试');
    throw new Error('GET ' + path + ' ' + resp.status);
  }
  return resp.json();
}

export async function apiPost(path, body) {
  const resp = await _fetchWithAuth(path, {
    method: 'POST',
    body: JSON.stringify(body || {}),
  }, true);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('认证失败 (401)：密码错误，请刷新后重试');
    const msg = data.message || data.error || ('POST ' + path + ' ' + resp.status);
    throw new Error(msg);
  }
  return data;
}

export async function apiDelete(path) {
  const resp = await _fetchWithAuth(path, { method: 'DELETE' }, false);
  return resp.json();
}

export async function loadProjects() {
  const data = await apiGet('/api/projects');
  return data.projects;
}

export async function loadHistory(project, source = 'all') {
  const data = await apiGet(
    '/api/history?project=' + encodeURIComponent(project) +
    '&source=' + encodeURIComponent(source || 'all')
  );
  return data.sessions;
}

export async function loadSession(id, project) {
  return await apiGet(
    '/api/history/' + encodeURIComponent(id) +
    '?project=' + encodeURIComponent(project)
  );
}

export async function deleteSession(id, project) {
  return await apiDelete(
    '/api/history/' + encodeURIComponent(id) +
    '?project=' + encodeURIComponent(project)
  );
}

export async function cleanupTestSessions(project) {
  return await apiPost(
    '/api/history/cleanup-tests?project=' + encodeURIComponent(project),
    {}
  );
}

export async function loadBoard(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/board' + qs);
}

export async function loadBoardDashboard(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/dashboard' + qs);
}

export async function loadBoardTimeline(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/timeline' + qs);
}

export async function getBoardTask(taskId, workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/tasks/' + encodeURIComponent(taskId) + qs);
}

export async function getBoardTaskEvents(taskId, workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/api/board/proxy/tasks/' + encodeURIComponent(taskId) + '/events' + qs);
}

export async function createBoardTask(task) {
  return apiPost('/api/board/proxy/tasks', task);
}

export async function loadSkills(projectId) {
  const qs = projectId ? ('?project=' + encodeURIComponent(projectId)) : '';
  return apiGet('/api/skills' + qs);
}

export async function moveBoardTask(payload) {
  return apiPost('/api/board/proxy/tasks/move', payload);
}

export async function fetchProjectBaseline(projectId) {
  const id = projectId || state.get('currentProject') || 'ccc';
  return apiGet('/api/projects/' + encodeURIComponent(id) + '/baseline');
}

/** Poll task column until terminal or timeout. Returns final task snapshot. */
export async function pollTaskUntil(taskId, workspace, options = {}) {
  const {
    intervalMs = 4000,
    timeoutMs = 30 * 60 * 1000,
    terminal = ['verified', 'released', 'abnormal'],
    onTick,
  } = options;
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    try {
      last = await getBoardTask(taskId, workspace);
      const col = last._column || last.status;
      if (typeof onTick === 'function') onTick(last, col);
      if (terminal.includes(col)) return last;
    } catch (err) {
      if (typeof onTick === 'function') onTick({ error: err.message }, null);
    }
    await new Promise(r => setTimeout(r, intervalMs));
  }
  return last;
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

export async function streamChat(
  messages,
  sessionId,
  project,
  onEvent,
  onDone,
  onError,
  attachments,
  opts = {}
) {
  const abortController = opts.abortController || new AbortController();
  if (!opts.abortController) {
    state.set('abortController', abortController);
  }

  try {
    const model = state.get('model') || 'flash';
    const body = {
      messages,
      session_id: sessionId,
      project,
      model,
      // 服务端按空闲超时解释；≤180 会被抬到 CCC_CHAT_IDLE_TIMEOUT（默认 600）
      timeout: 600,
    };
    if (attachments && attachments.length) {
      body.attachments = attachments;
    }

    const resp = await _fetchWithAuth('/api/chat', {
      method: 'POST',
      body: JSON.stringify(body),
      signal: abortController.signal,
    }, true);

    if (!resp.ok) {
      const errText = resp.status === 401 ? '认证失败 (401)：请刷新，用户名/密码均为 ccc'
        : resp.status === 400 ? '危险指令已被拦截或附件无效'
        : resp.status === 429 ? '该会话仍在执行中，请稍候或新开对话'
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
          } else if (data.type === 'ping') {
            // SSE keepalive — ignore
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
    if (!opts.abortController) {
      state.set('abortController', null);
    }
  }
}

export function cancelStream(tabId) {
  import('./streamRegistry.js')
    .then((m) => m.cancelStream(tabId))
    .catch(() => {
      const ac = state.get('abortController');
      if (ac) ac.abort();
    });
}
