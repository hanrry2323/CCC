import { state } from './state.js';
import { getToken, clearToken } from './auth.js';
import { cancelStream as registryCancelStream, cancelAllStreams as registryCancelAllStreams } from './streamRegistry.js';
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

let _activeStreamController = null;
let _activePollController = null;

export function abortActiveConnections() {
  if (_activeStreamController) {
    _activeStreamController.abort();
    _activeStreamController = null;
  }
  if (_activePollController) {
    _activePollController.abort();
    _activePollController = null;
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('project-change', () => {
    abortActiveConnections();
  });
  document.addEventListener('switch-tab', () => {
    abortActiveConnections();
  });
  // 2026-08-17 M2：离开整个 SPA（全页导航/刷新/关标签）时中止在途流 + 全清 registry，
  // 避免浏览器导航 abort 在途 SSE 后残留脏流状态。
  document.addEventListener('pagehide', () => {
    try {
      abortActiveConnections();
      registryCancelAllStreams();
    } catch (_) {
      /* 卸载期清理尽力而为 */
    }
  });
}

// ===== 2026-08-17 M2：页面切换根治 · 数据层 =====
// 三件事：① 页面级 GET 作用域 abort（切页即中断旧页在途请求，配合 app.js 令牌）；
// ② 内存短 TTL 缓存（切回不重拉，stale-while-revalidate）；③ GET 统一 15s 超时
// 杜绝永久 pending。写操作成功后全清缓存。

// —— ① 页面级请求作用域：切路由时 abort 全部页面级 GET ——
let _pageAbort = new AbortController();
/** 切路由时调用：中断旧页全部在途页面级 GET。 */
export function pageScopeAbort() {
  _pageAbort.abort();
  _pageAbort = new AbortController();
}
function _pageScopeSignal() {
  return _pageAbort.signal;
}

// —— ② 内存短 TTL 缓存（GET 可缓存接口）——
const _cache = new Map();    // key -> { t, data }
const _inflight = new Map(); // key -> Promise（同 key 在途合并，防重复请求）
const CACHE_TTL_MS = 10000;
// 可缓存前缀（状态类/实时类接口绝不缓存：/cards、/tasks、/board/ready_for_merge、
// /conversation、/health、SSE）
const CACHEABLE_PREFIXES = [
  '/projects', '/config', '/claude/projects', '/claude/sessions',
  '/plans/list', '/plans/card-states', '/plans/detail',
  '/roadmap', '/board/roadmap', '/board/summaries',
  '/loop/findings', '/ops/failures', '/ops/relay-stats',
];
function _isCacheable(path) {
  for (const p of CACHEABLE_PREFIXES) {
    if (path === p || path.startsWith(p + '/') || path.startsWith(p + '?')) return true;
  }
  return false;
}
function _cacheKey(method, path) {
  return method + ' ' + path;
}
function _cacheGet(key) {
  const e = _cache.get(key);
  if (e && e.t > Date.now()) return e.data;
  return undefined;
}
function _cacheSet(key, data) {
  _cache.set(key, { t: Date.now() + CACHE_TTL_MS, data });
}
/** 写操作成功后调用：清缓存（全清最简，低频人审动作零漏清）。 */
export function invalidateCache(prefix) {
  if (!prefix) {
    _cache.clear();
    return;
  }
  for (const k of _cache.keys()) {
    if (k.includes(prefix)) _cache.delete(k);
  }
}

// —— ③ GET 统一 15s 超时 + 瞬时错误 1 次静默重试 ——
const GET_TIMEOUT_MS = 15000;
function _cacheDisabled() {
  return !!(typeof window !== 'undefined' && window.__CCC_CACHE_DISABLED__);
}
/** 导航/路由切换中止判定：切换中、页面隐藏都视为「主动中止」，不弹网络错误。 */
let _routeSwitching = false;
export function setRouteSwitching(v) {
  _routeSwitching = !!v;
}
function _isNavAbort() {
  if (typeof document === 'undefined') return false;
  return _routeSwitching || document.visibilityState === 'hidden' || document.hidden;
}
function _mergedSignal({ signal, pageScoped, noTimeout } = {}) {
  if (noTimeout && !pageScoped && !signal) return undefined;
  const parts = [];
  // 超时与页面作用域是「防卡死/防洪峰」护栏，不随缓存回滚开关关闭；
  // __CCC_CACHE_DISABLED__ 只关数据缓存（见 apiGet 的 cacheable 判断）。
  if (!noTimeout && typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
    parts.push(AbortSignal.timeout(GET_TIMEOUT_MS));
  }
  if (signal) parts.push(signal);
  if (pageScoped) parts.push(_pageScopeSignal());
  if (!parts.length) return undefined;
  if (parts.length === 1) return parts[0];
  return typeof AbortSignal !== 'undefined' && AbortSignal.any
    ? AbortSignal.any(parts)
    : parts[parts.length - 1];
}

async function _fetchWithAuth(path, options = {}, json = true) {
  const tok = getToken();
  const method = options.method || 'GET';
  // 页面级 GET 默认挂页面作用域（切路由即 abort）；POST/PUT/DELETE 写操作不挂
  // （服务端应完成，客户端忽略响应）；noTimeout 供长轮询/SSE 跳过超时。
  const signal = _mergedSignal({
    signal: options.signal,
    pageScoped: options.pageScoped !== false && method === 'GET',
    noTimeout: options.noTimeout === true,
  });
  const resp = await fetch(path, {
    method,
    headers: { ...(options.headers || {}), ..._headers(json) },
    body: options.body,
    signal,
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

function _chatBase() {
  // M1 对话桥直连（/config 下发）；空则走本机 /conversation 代理
  return (typeof window !== 'undefined' && window.__CCC_CHAT_BRIDGE_URL__) || '';
}

async function _checkGetOk(path, resp) {
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('登录状态已失效，请刷新页面重新连接');
    throw new Error('GET ' + path + ' ' + resp.status);
  }
  return resp.json();
}

/** 瞬时网络错误（TypeError: Failed to fetch）静默重试一次；Abort/导航中止/HTTP 错误不重试。 */
async function _doGet(path, options = {}) {
  try {
    const resp = await _fetchWithAuth(path, { method: 'GET', ...options }, false);
    return await _checkGetOk(path, resp);
  } catch (err) {
    if (err instanceof TypeError && !_isNavAbort()) {
      await new Promise((r) => setTimeout(r, 400)); // 退避 400ms
      const resp2 = await _fetchWithAuth(path, { method: 'GET', ...options }, false);
      return _checkGetOk(path, resp2);
    }
    throw err;
  }
}

export async function apiGet(path, options = {}) {
  // 缓存只服务默认 GET（带自定义 signal 的调用视为特殊流，跳过缓存）。
  // 写操作后 invalidateCache 已清缓存 → 下次必拉新。
  const cacheable = !options.signal && !_cacheDisabled() && _isCacheable(path);
  if (!cacheable) return _doGet(path, options);
  const key = _cacheKey('GET', path);
  const cached = _cacheGet(key);
  if (cached !== undefined) return cached;
  if (_inflight.has(key)) return _inflight.get(key); // 同 key 在途合并
  const p = _doGet(path, options)
    .then((data) => {
      _cacheSet(key, data);
      return data;
    })
    .finally(() => {
      _inflight.delete(key);
    });
  _inflight.set(key, p);
  return p;
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
  invalidateCache('/'); // 写操作成功 → 清缓存，下次必拉新
  return data;
}

export async function apiPut(path, body) {
  const resp = await _fetchWithAuth(path, {
    method: 'PUT',
    body: JSON.stringify(body || {}),
  }, true);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('登录状态已失效，请刷新页面重新连接');
    const msg = friendlyChatError(resp.status, data.message || data.error);
    throw new Error(msg);
  }
  invalidateCache('/'); // 写操作成功 → 清缓存
  return data;
}

export async function apiDelete(path) {
  const resp = await _fetchWithAuth(path, { method: 'DELETE' }, false);
  const data = await resp.json().catch(() => ({}));
  if (resp.ok) invalidateCache('/'); // 写操作成功 → 清缓存
  return data;
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
  const base = _chatBase();
  const data = await apiGet((base || '') + '/projects/' + encodeURIComponent(project) + '/threads');
  return data.threads || [];
}

// Claude Code 原生历史（M1 ~/.claude/projects，按项目 cwd 分组）
export async function loadClaudeProjects() {
  const base = _chatBase();
  const data = await apiGet((base || '') + '/claude/projects');
  return data.projects || [];
}

export async function loadClaudeSessions(projectOrPath) {
  const base = _chatBase();
  const key = String(projectOrPath || '').startsWith('/') ? 'path' : 'project';
  const data = await apiGet((base || '') + '/claude/sessions?' + key + '=' + encodeURIComponent(projectOrPath));
  return data.sessions || [];
}

export async function loadClaudeMessages(projectOrPath, file) {
  const base = _chatBase();
  const key = String(projectOrPath || '').startsWith('/') ? 'path' : 'project';
  const data = await apiGet((base || '') + '/claude/messages?' + key + '=' + encodeURIComponent(projectOrPath) + '&file=' + encodeURIComponent(file));
  return data.messages || [];
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

  // 发起新历史长轮询时，打断旧的在途长轮询，防止多会话长轮询堆叠
  if (_activePollController) {
    _activePollController.abort();
  }
  const controller = new AbortController();
  _activePollController = controller;
  const signal = controller.signal;

  let data;
  try {
    const base = _chatBase();
    const path = base
      ? base + '/chat/history' + qs + '&project=' + encodeURIComponent(state.get('currentProject') || 'ccc')
      : '/conversation' + qs;
    data = await apiGet(path, { signal, noTimeout: true, pageScoped: false });
  } catch (err) {
    if (err && err.name === 'AbortError') {
      return { messages: [], seq: cur.seq };
    }
    throw err;
  } finally {
    if (_activePollController === controller) {
      _activePollController = null;
    }
  }

  // 历史消息字段兼容：{role,message}（会话存储）→ content（前端渲染）
  const msgs = (data.messages || []).map((m) => ({
    ...m,
    content: m.content != null ? m.content : m.message,
  }));
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

export async function getBoardTask(taskId, workspace) {
  return apiGet('/tasks/' + encodeURIComponent(taskId));
}

export async function getBoardTaskEvents(taskId, workspace) {
  return [];
}

export async function createBoardTask(task) {
  throw new Error('创建任务已禁用，请走任务卡（docs/dispatch）由 Engine 派发');
}

export async function moveBoardTask(payload) {
  throw new Error('移动任务已禁用，请改卡头状态或走 Engine / 编排口');
}

export async function desktopTransfer(payload) {
  throw new Error('文档流转已禁用，请走任务卡 / Engine');
}

export async function nudgeOutboxFlush() {
  return null;
}

export async function loadSkills(projectId, opts = {}) {
  return [];
}

export async function loadHubConfig() {
  try {
    const data = await apiGet('/config');
    if (data && data.chat_bridge_url) {
      window.__CCC_CHAT_BRIDGE_URL__ = data.chat_bridge_url;
    }
    return { chat_session_max_live: 4, dialogue_url: '/' };
  } catch (e) {
    return { chat_session_max_live: 4, dialogue_url: '/' };
  }
}

export async function renameSession(id, project, title) {
  return {};
}

export async function fetchProjectBaseline(projectId) {
  return {};
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

  // 开启新流前，强制打断旧的在途流，彻底防止多会话流重叠污染
  if (_activeStreamController) {
    _activeStreamController.abort();
  }
  const controller = (opts && opts.abortController) || new AbortController();
  _activeStreamController = controller;
  const signal = controller.signal;

  const userMsgs = (messages || []).filter((m) => m.role === 'user');
  const prompt =
    (userMsgs.length ? userMsgs[userMsgs.length - 1].content : '') || '';

  // 单次流只允许一次终结（done/error/abort/EOF 先到者生效），避免重复回写
  let settled = false;
  const settleDone = () => {
    if (settled) return;
    settled = true;
    if (signal && signal.aborted) return; // 已经被 Abort 时静默丢弃，不触发 UI 回调
    onDone(sessionId);
  };
  const settleError = (msg) => {
    if (settled) return;
    settled = true;
    if (signal && signal.aborted) return; // 已经被 Abort 时静默丢弃，不触发 UI 回调
    onError(msg || '生成失败');
  };

  // T46 C10：网络抖动（fetch/SSE 中断）自动重连一次；连续失败不再自动重试（防抖）。
  const MAX_AUTO_RETRY = 1;
  let autoRetryLeft = MAX_AUTO_RETRY;
  let receivedAnyEvent = false;   // 已收到任意流事件 → 不自动重连（避免重复内容）
  let lastPromptSent = prompt;

  // 构造单次流请求
  async function openStream() {
    const base = _chatBase();
    const claudeSession =
      (typeof window !== 'undefined' && window.__claudeSession__) || null;
    const claudePath =
      (typeof window !== 'undefined' && window.__claudeProjectPath__) || null;
    const resp = await _fetchWithAuth(
      base ? base + '/chat' : '/conversation',
      {
        method: 'POST',
        body: JSON.stringify({
          message: lastPromptSent,
          stream: true,
          // T44：按会话分桶历史/分锁；模型档位覆盖
          thread_id: sessionId || null,
          project: state.get('currentProject') || projectId || 'ccc',
          path: claudePath,
          claude_session: claudeSession,
          model: state.get('model') || null,
        }),
        signal,
        noTimeout: true,
        pageScoped: false,
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
    if (signal && signal.aborted) return; // 被打断时抛弃事件流
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
      if (_isNavAbort()) {
        settleDone(); // 导航/路由切换中止：静默结算（复位 UI），不弹「网络中断」
        return 'settled';
      }
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
    function processLine(line) {
      const trimmed = line.trim();
      if (trimmed === '') {
        flushBlock();
      } else if (line.startsWith('event:')) {
        if (eventName !== null || dataLines.length > 0) {
          flushBlock();
        }
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        const d = line.slice(5);
        dataLines.push(d.startsWith(' ') ? d.slice(1) : d);
      }
    }
    function feed(chunk) {
      buffer += chunk;
      let idx;
      while ((idx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, idx).replace(/\r$/, '');
        buffer = buffer.slice(idx + 1);
        processLine(line);
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        feed(decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n'));
      }
      feed(decoder.decode().replace(/\r\n/g, '\n'));
      if (buffer.trim()) {
        processLine(buffer);
        flushBlock();
      }
      // EOF 且未收到 done/error → 不完整流，按错误复位（避免假成功；服务端也可能未落盘）
      if (!settled) {
        settleError('连接中断，回复可能不完整');
      }
      return settled ? 'settled' : 'network';
    } catch (e) {
      if (e && e.name === 'AbortError') {
        settled = true;
        return 'settled';
      }
      if (_isNavAbort()) {
        settleDone(); // 导航/路由切换中止：静默结算（复位 UI），不弹「网络中断」
        return 'settled';
      }
      return 'network';  // SSE 读中断
    }
  }

  // T46 C10：首次尝试；若网络失败且尚未收到任何内容 → 自动重连一次（不重复内容）。
  let result = await runOnce();
  if (result === 'network' && !receivedAnyEvent && autoRetryLeft > 0) {
    autoRetryLeft -= 1;
    notifyReconnecting();
    result = await runOnce();
  }
  // 连续失败或读取中断：若结果为 network 且未 settle，强制上报网络错误以复位 UI
  if (result === 'network' && !settled) {
    settleError('网络中断，请重试');
  }
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
