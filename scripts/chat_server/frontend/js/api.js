import { state } from './state.js';
import { hubUrl, agentUrl } from './ports.js';
import { friendlyChatError } from './chatErrors.js';
import { getToken, clearToken } from './auth.js';
import { reportConnectionFailure } from './chatStatus.js';

/** Hub 请求头：Bearer 会话 token（无 token → 空头；登录换 token 走 auth.js login）。 */
function _headers(json = true) {
  const h = {};
  const tok = getToken();
  if (tok) h.Authorization = 'Bearer ' + tok;
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

function _agentToken(_forcePrompt = false) {
  // 内网默认无鉴权；若曾手动存过 token 仍可带上。不再弹窗索要 Token。
  return (
    sessionStorage.getItem('ccc_agent_token') ||
    localStorage.getItem('ccc_agent_token') ||
    ''
  ).trim();
}

function _agentHeaders(json = true, forcePrompt = false) {
  const h = {};
  const tok = _agentToken(forcePrompt);
  if (tok) h.Authorization = 'Bearer ' + tok;
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

/** Hub 请求（Bearer token + hubBase）。401 → 清 token + 登录引导（不白屏不弹裸错误）。 */
async function _fetchWithAuth(pathOrUrl, options = {}, json = true) {
  const url = pathOrUrl.startsWith('http') ? pathOrUrl : hubUrl(pathOrUrl);
  const resp = await fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), ..._headers(json) },
  });
  if (resp.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent('ccc-auth-required'));
  }
  return resp;
}

/** Agent sidecar 请求（Bearer）；禁止走 Hub /api/agent 反代。 */
async function _fetchAgent(pathOrUrl, options = {}, json = true) {
  const url = pathOrUrl.startsWith('http') ? pathOrUrl : agentUrl(pathOrUrl);
  let resp;
  try {
    resp = await fetch(url, {
      ...options,
      headers: { ...(options.headers || {}), ..._agentHeaders(json, false) },
    });
  } catch (e) {
    // 网络层抛错（sidecar 不可达）→ 上报断连横幅，再按原路径抛出
    reportConnectionFailure();
    throw e;
  }
  if (resp.status === 401) {
    sessionStorage.removeItem('ccc_agent_token');
    localStorage.removeItem('ccc_agent_token');
    window.showToast?.(
      '对话口鉴权已开启但未通过：请关鉴权（默认）或配置服务端 Token',
      'error'
    );
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
  if (data.default_project) {
    state.set('defaultProject', data.default_project);
  }
  return data.projects || [];
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

/** Desktop 同构：POST /api/desktop/transfer（transfer-gate）。 */
export async function desktopTransfer(payload) {
  const data = await apiPost('/api/desktop/transfer', payload || {});
  if (data && data.ok === false) {
    const errs = Array.isArray(data.errors)
      ? data.errors.map((e) => e.message || e.code || JSON.stringify(e)).join('; ')
      : data.error || 'transfer failed';
    throw new Error(errs);
  }
  if (!data?.epic_id) {
    throw new Error(data?.error || 'transfer 未返回 epic_id');
  }
  return data;
}

/** 轻推 sidecar 冲刷 transfer-outbox（与 App nudge 同构；失败可忽略）。 */
export async function nudgeOutboxFlush() {
  try {
    const resp = await _fetchAgent('/api/outbox/flush', { method: 'POST' }, true);
    if (!resp.ok) return null;
    return await resp.json().catch(() => ({}));
  } catch (_) {
    return null;
  }
}

export async function loadSkills(projectId, opts = {}) {
  const params = new URLSearchParams();
  if (projectId) params.set('project', projectId);
  if (opts.includeEngine) params.set('include_engine', 'true');
  const qs = params.toString() ? '?' + params.toString() : '';
  return apiGet('/api/skills' + qs);
}

export async function loadHubConfig() {
  return apiGet('/api/hub-config');
}

export async function renameSession(id, project, title) {
  const resp = await _fetchWithAuth(
    '/api/history/' +
      encodeURIComponent(id) +
      '?project=' +
      encodeURIComponent(project),
    {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    },
    true
  );
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || data.error || '重命名失败');
  }
  return data;
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

  const projectId = project || state.get('currentProject') || 'ccc';
  const { desktopThreadId, resolveProjectPath } = await import('./utils.js');
  const threadId = desktopThreadId(projectId, sessionId || `${projectId}::main`);
  const projectPath = resolveProjectPath(projectId);

  try {
    const model = state.get('model') || 'flash';
    const toolMode = state.get('toolMode') || 'discuss';
    const userMsgs = (messages || []).filter((m) => m.role === 'user');
    const prompt =
      (userMsgs.length ? userMsgs[userMsgs.length - 1].content : '') || '';
    const body = {
      prompt,
      messages: prompt ? [] : messages,
      session_id: threadId,
      project: projectId,
      project_id: projectId,
      project_path: projectPath,
      model,
      tool_mode: toolMode,
      timeout: 600,
    };
    const resume = state.get('claudeSessionIdByThread')?.[threadId];
    if (resume) body.claude_session_id = resume;
    if (attachments && attachments.length) {
      body.attachments = attachments;
    }

    const resp = await _fetchAgent('/api/chat', {
      method: 'POST',
      body: JSON.stringify(body),
      signal: abortController.signal,
    }, true);

    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      const detail = errBody.detail || errBody.message || errBody.error;
      const errText = friendlyChatError(resp.status, detail);
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
            // keepalive
          } else if (data.type === 'done') {
            if (data.claude_session_id) {
              const map = {
                ...(state.get('claudeSessionIdByThread') || {}),
              };
              map[threadId] = data.claude_session_id;
              state.set('claudeSessionIdByThread', map);
            }
            onDone(data.session_id || threadId);
          } else if (data.type === 'error') {
            onError(data.content);
          }
        } catch (_) {
          /* skip */
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      // TypeError = fetch 网络层失败（sidecar 不可达）→ 友好文案，不裸显 "Failed to fetch"
      const msg =
        e instanceof TypeError
          ? friendlyChatError(503, null)
          : '网络错误: ' + e.message;
      onError(msg);
    }
  } finally {
    if (!opts.abortController) {
      state.set('abortController', null);
    }
  }
}

export async function putDesktopThreadMessages(threadId, messages, projectId) {
  const resp = await _fetchWithAuth(
    '/api/desktop/threads/' + encodeURIComponent(threadId) + '/messages',
    {
      method: 'PUT',
      body: JSON.stringify({
        project_id: projectId || state.get('currentProject') || 'ccc',
        messages,
      }),
    },
    true
  );
  if (!resp.ok) throw new Error('PUT messages ' + resp.status);
  return resp.json();
}

export async function loadDesktopThread(threadId) {
  return apiGet('/api/desktop/threads/' + encodeURIComponent(threadId));
}

export function cancelStream(tabId) {
  const project = state.get('currentProject') || 'ccc';
  import('./utils.js').then(async ({ desktopThreadId, resolveProjectPath }) => {
    const tid = desktopThreadId(
      project,
      state.get('currentSessionId') || tabId
    );
    try {
      await _fetchAgent(
        '/api/session/drop',
        {
          method: 'POST',
          body: JSON.stringify({
            project_path: resolveProjectPath(project),
            session_id: tid,
            reason: 'cancel',
            tool_mode: state.get('toolMode') || 'discuss',
          }),
        },
        true
      );
    } catch (_) {}
  });
  import('./streamRegistry.js')
    .then((m) => m.cancelStream(tabId))
    .catch(() => {
      const ac = state.get('abortController');
      if (ac) ac.abort();
    });
}
