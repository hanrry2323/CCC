import { state } from './state.js';
import { getToken, clearToken } from './auth.js';
import { cancelStream as registryCancelStream } from './streamRegistry.js';
import { friendlyChatError, humanizeBrainError } from './chatErrors.js';

/** 请求头：从 localStorage 读 ccc_chat_token，返回 Bearer 头。 */
function _headers(json = true) {
  const h = {};
  const tok = getToken();
  if (tok) h.Authorization = 'Bearer ' + tok;
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

/** 带认证的 fetch（同源相对路径）。
 * T44：仅当曾带 token 且被拒（token 失效）时派发 ccc-auth-required（且每页只弹一次）；
 * 未登录态（无 token）的 401 静默降级，不刷错误、不刷登录门。
 */
let _loginPrompted = false;

async function _fetchWithAuth(path, options = {}, json = true) {
  const tok = getToken();
  const resp = await fetch(path, {
    ...options,
    headers: { ...(options.headers || {}), ..._headers(json) },
  });
  if (resp.status === 401) {
    if (tok && !_loginPrompted) {
      _loginPrompted = true;
      clearToken();
      window.dispatchEvent(new CustomEvent('ccc-auth-required'));
    }
  }
  return resp;
}

export async function apiGet(path) {
  const resp = await _fetchWithAuth(path, { method: 'GET' }, false);
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('登录状态已失效，请刷新页面重新连接');
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
    if (resp.status === 401) throw new Error('登录状态已失效，请刷新页面重新连接');
    const msg = friendlyChatError(resp.status, data.message || data.error);
    throw new Error(msg);
  }
  return data;
}

export async function apiDelete(path) {
  const resp = await _fetchWithAuth(path, { method: 'DELETE' }, false);
  return resp.json();
}

export async function loadProjects() {
  // T47：项目来源改 GET /projects（真实业务项目），不再用 /board/summaries 任务卡分组
  const data = await apiGet('/projects');
  const projects = data.projects || [];
  if (projects.length > 0) {
    state.set('defaultProject', projects[0].id);
  }
  return projects.map((p) => ({
    id: p.id,
    name: p.name,
    role: p.is_taskable ? 'app' : 'readonly',
    engine_eligible: p.is_taskable !== false,
    is_taskable: p.is_taskable !== false,
    workspace_path: p.workspace_path || '',
    workspace: p.workspace_path || p.id, // 兼容下游 projectWorkspaceMap / 设置页
    kind: p.kind || 'business',
  }));
}

// T47：项目下会话列表（来自服务端会话存储，非本地 tabs）
export async function loadThreads(project) {
  const data = await apiGet('/projects/' + encodeURIComponent(project) + '/threads');
  return data.threads || [];
}

// T47：删除项目下会话（仅删会话存储，不动任务卡）
export async function deleteThread(project, threadId) {
  return apiDelete('/projects/' + encodeURIComponent(project) + '/threads/' + encodeURIComponent(threadId));
}

// T43/T44：对话历史长轮询增量同步（GET /conversation?after=<seq>&timeout=<s>）。
// T44：按 thread_id 分桶（每个会话独立光标 + 缓存），缺省走全局。
// 首拉无 after 全量，之后带 after=seq 增量；seq 回退（服务端重置）→ 以本次为准。
let _historyCursors = {};
// 长轮询默认超时（秒；与服务端 CCC_WEB_LONGPOLL_TIMEOUT 默认一致）
const LONGPOLL_TIMEOUT = 30;

function _historyKey(threadId) {
  return threadId || 'global';
}

async function _fetchHistory(threadId) {
  const key = _historyKey(threadId);
  const cur = _historyCursors[key] || { seq: 0, msgs: [] };
  const incremental = cur.seq > 0;
  const tid = threadId ? ('&thread_id=' + encodeURIComponent(threadId)) : '';
  const qs = incremental
    ? `?after=${cur.seq}&timeout=${LONGPOLL_TIMEOUT}${tid}`
    : (threadId ? ('?thread_id=' + encodeURIComponent(threadId)) : '');
  const data = await apiGet('/conversation' + qs);
  const msgs = data.messages || [];
  const seq = data.seq || 0;
  if (!incremental || seq < cur.seq) {
    // 首拉全量 / 服务端 seq 重置 → 以本次返回为准（含 seq 回退清空）
    cur.seq = seq;
    cur.msgs = msgs;
  } else if (msgs.length) {
    cur.seq = seq;
    cur.msgs = cur.msgs.concat(msgs);
  }
  _historyCursors[key] = cur;
  return data;
}

export async function loadHistory(project, source = 'all') {
  await _fetchHistory(project || '');
  const key = _historyKey(project || '');
  return { sessions: (_historyCursors[key]?.msgs || []).slice() };
}

export async function loadSession(id, project) {
  await _fetchHistory(id || '');
  const key = _historyKey(id || '');
  return { messages: (_historyCursors[key]?.msgs || []).slice() };
}

export async function deleteSession(id, project) {
  return {};
}

export async function cleanupTestSessions(project) {
  return {};
}

function _workspaceQs(workspace) {
  return workspace && workspace !== 'all'
    ? ('?workspace=' + encodeURIComponent(workspace))
    : '';
}

export async function loadBoard(workspace) {
  return apiGet('/board/snapshot' + _workspaceQs(workspace));
}

export async function loadBoardDashboard(workspace) {
  return apiGet('/board/snapshot' + _workspaceQs(workspace));
}

export async function loadBoardTimeline(workspace) {
  return apiGet('/board/roadmap' + _workspaceQs(workspace));
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
  const signal =
    (opts && opts.abortController && opts.abortController.signal) || null;

  const userMsgs = (messages || []).filter((m) => m.role === 'user');
  const prompt =
    (userMsgs.length ? userMsgs[userMsgs.length - 1].content : '') || '';

  // 单次流只允许一次终结（done/error/abort/EOF 先到者生效），避免重复回写
  let settled = false;
  const settleDone = () => {
    if (settled) return;
    settled = true;
    onDone(sessionId);
  };
  const settleError = (msg) => {
    if (settled) return;
    settled = true;
    onError(msg || '生成失败');
  };

  // T46 C10：网络抖动（fetch/SSE 中断）自动重连一次；连续失败不再自动重试（防抖）。
  const MAX_AUTO_RETRY = 1;
  let autoRetryLeft = MAX_AUTO_RETRY;
  let receivedAnyEvent = false;   // 已收到任意流事件 → 不自动重连（避免重复内容）
  let lastPromptSent = prompt;

  // 构造单次流请求
  async function openStream() {
    const resp = await _fetchWithAuth(
      '/conversation',
      {
        method: 'POST',
        body: JSON.stringify({
          message: lastPromptSent,
          stream: true,
          // T44：按会话分桶历史/分锁；模型档位覆盖
          thread_id: sessionId || null,
          model: state.get('model') || null,
        }),
        signal,
      },
      true
    );
    return resp;
  }

  // 上报「自动重连中」（顶部横幅，T46 C10）
  function notifyReconnecting() {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('ccc-stream-reconnecting'));
    }
  }

  function routeEvent(ev, payload) {
    if (ev === 'text') {
      onEvent('delta', (payload && payload.text) || '');
    } else if (
      ev === 'meta' ||
      ev === 'thinking' ||
      ev === 'tool_use' ||
      ev === 'tool_result' ||
      ev === 'cost'
    ) {
      onEvent(ev, payload || {});
    } else if (ev === 'done') {
      if (payload && payload.is_error) {
        settleError(humanizeBrainError((payload && (payload.error || payload.text)) || '生成失败'));
      } else {
        settleDone();
      }
    } else if (ev === 'error') {
      settleError(humanizeBrainError((payload && payload.message) || '生成失败'));
    }
  }

  async function runOnce() {
    let resp;
    try {
      resp = await openStream();
    } catch (e) {
      if (e && e.name === 'AbortError') return 'settled';
      // fetch 失败
      return 'network';
    }
    if (resp.status === 401) {
      settleError('登录状态已失效，请刷新页面重新连接');
      return 'settled';
    }
    if (!resp.ok || !resp.body) {
      const data = await resp.json().catch(() => ({}));
      settleError(friendlyChatError(resp.status, data.message || data.error));
      return 'settled';
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let eventName = null;
    let dataLines = [];

    function flushBlock() {
      if (eventName === null && dataLines.length === 0) return;
      const raw = dataLines.join('\n');
      dataLines = [];
      const ev = eventName;
      eventName = null;
      if (!raw) return;
      let payload = null;
      try { payload = JSON.parse(raw); } catch (_) { return; }
      receivedAnyEvent = true;
      routeEvent(ev, payload);
    }
    function consumeBlock(block) {
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
      }
      flushBlock();
    }
    function feed(chunk) {
      buffer += chunk;
      let idx;
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        consumeBlock(block);
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        feed(decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n'));
      }
      feed(decoder.decode().replace(/\r\n/g, '\n'));
      if (buffer.trim()) consumeBlock(buffer);
      // T45：EOF 且未收到 done/error → 流中断，统一按结束处理（UI 复位，避免假流式）
      settleDone();
      return 'settled';
    } catch (e) {
      if (e && e.name === 'AbortError') {
        settleDone();
        return 'settled';
      }
      return 'network';  // SSE 读中断
    }
  }

  // T46 C10：首次尝试；若网络失败且尚未收到任何内容 → 自动重连一次（不重复内容）。
  const first = await runOnce();
  if (first === 'network' && !receivedAnyEvent && autoRetryLeft > 0) {
    autoRetryLeft -= 1;
    notifyReconnecting();
    await runOnce();
  }
  // 连续失败：runOnce 内部已 settleError；防抖（只重试一次）已生效。
}

export async function putDesktopThreadMessages(threadId, messages, projectId) {
  return {};
}

export async function loadDesktopThread(threadId) {
  return {};
}

export function cancelStream(tabId) {
  registryCancelStream(tabId);
}

export async function getCards({ project = '', state = '', page = 1, page_size = 50 } = {}) {
  const qs = new URLSearchParams();
  if (project) qs.append('project', project);
  if (state) qs.append('state', state);
  if (page) qs.append('page', String(page));
  if (page_size) qs.append('page_size', String(page_size));
  return apiGet('/cards?' + qs.toString());
}

export async function searchCards({ q = '', project = '', state = '', page = 1 } = {}) {
  const qs = new URLSearchParams();
  if (q) qs.append('q', q);
  if (project) qs.append('project', project);
  if (state) qs.append('state', state);
  if (page) qs.append('page', String(page));
  return apiGet('/cards/search?' + qs.toString());
}