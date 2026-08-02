import { state } from './state.js';
import { getToken, clearToken } from './auth.js';

/** 请求头：从 localStorage 读 ccc_chat_token，返回 Bearer 头。 */
function _headers(json = true) {
  const h = {};
  const tok = getToken();
  if (tok) h.Authorization = 'Bearer ' + tok;
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

/** 带认证的 fetch（同源相对路径）。401 → 清 token + 登录引导。 */
async function _fetchWithAuth(path, options = {}, json = true) {
  const resp = await fetch(path, {
    ...options,
    headers: { ...(options.headers || {}), ..._headers(json) },
  });
  if (resp.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent('ccc-auth-required'));
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
  const data = await apiGet('/board/summaries');
  const summaries = data.summaries || [];
  if (summaries.length > 0) {
    state.set('defaultProject', summaries[0]);
  }
  return summaries.map((ws) => ({ id: ws, name: ws, role: 'app' }));
}

export async function loadHistory(project, source = 'all') {
  const data = await apiGet('/conversation');
  return { sessions: data.messages || [] };
}

export async function loadSession(id, project) {
  const data = await apiGet('/conversation');
  return { messages: data.messages || [] };
}

export async function deleteSession(id, project) {
  return {};
}

export async function cleanupTestSessions(project) {
  return {};
}

export async function loadBoard(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/board/snapshot' + qs);
}

export async function loadBoardDashboard(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/board/snapshot' + qs);
}

export async function loadBoardTimeline(workspace) {
  const qs = workspace ? ('?workspace=' + encodeURIComponent(workspace)) : '';
  return apiGet('/board/roadmap' + qs);
}

export async function getBoardTask(taskId, workspace) {
  return apiGet('/tasks/' + encodeURIComponent(taskId));
}

export async function getBoardTaskEvents(taskId, workspace) {
  return [];
}

export async function createBoardTask(task) {
  throw new Error('创建任务已禁用，请使用桌面端或编排口');
}

export async function moveBoardTask(payload) {
  throw new Error('移动任务已禁用，请使用桌面端或编排口');
}

export async function desktopTransfer(payload) {
  throw new Error('文档流转已禁用，请在桌面端操作');
}

export async function nudgeOutboxFlush() {
  return null;
}

export async function loadSkills(projectId, opts = {}) {
  return [];
}

export async function loadHubConfig() {
  const data = await apiGet('/health');
  return { chat_session_max_live: 4, dialogue_url: '/' };
}

export async function renameSession(id, project, title) {
  return {};
}

export async function fetchProjectBaseline(projectId) {
  return {};
}

export async function pollTaskUntil(taskId, workspace, options = {}) {
  throw new Error('轮询已禁用');
}

export async function listProjectFiles(projectId, path = '') {
  throw new Error('文件浏览已禁用');
}

export async function readProjectFile(projectId, path) {
  throw new Error('文件浏览已禁用');
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
  const projectId = project || state.get('currentProject') || 'ccc';

  try {
    const userMsgs = (messages || []).filter((m) => m.role === 'user');
    const prompt =
      (userMsgs.length ? userMsgs[userMsgs.length - 1].content : '') || '';

    const data = await apiPost('/conversation', { message: prompt });

    const reply = data.reply || data.message || data.response || JSON.stringify(data);
    onEvent('delta', reply);
    onDone(sessionId);
  } catch (e) {
    onError('网络错误: ' + e.message);
  }
}

export async function putDesktopThreadMessages(threadId, messages, projectId) {
  return {};
}

export async function loadDesktopThread(threadId) {
  return {};
}

export function cancelStream(tabId) {
  // 无操作
}