/**
 * api.js — CCC 前端数据层（ccc-plan-045 P1.5 随对话栈拆除同步精简）。
 *
 * 保留：页面级 GET 作用域 abort、内存 TTL 缓存+在途去重+写后代次失效、
 *       15s 超时、瞬时网络错误静默重试一次；看板/计划/线路图/运维/巡检/控制台数据面。
 * P0（2026-08-29 写链路打通）：全站统一 token 出口——请求自动携带 Bearer，
 *       401 自动清 token→弹口令重签（POST /session）→重放一次；
 *       恢复原「拆除 token 登录态」的决定：服务端写闸+读闸（2026-08-24/08-29）使
 *       LAN 免登录只覆盖公开读，写与敏感读必须有 token。
 * 拆除：大脑对话流（streamChat）、会话历史长轮询、Claude/DSH 会话镜像。
 */

// ===== 页面级请求作用域：切路由时 abort 全部页面级在途 GET =====
let _pageAbort = new AbortController();
/** 切路由时调用：中断旧页全部在途页面级 GET。 */
export function pageScopeAbort() {
  _pageAbort.abort();
  _pageAbort = new AbortController();
}
function _pageScopeSignal() {
  return _pageAbort.signal;
}

// ===== 内存短 TTL 缓存（GET 可缓存接口）=====
const _cache = new Map();    // key -> { t, data }
const _inflight = new Map(); // key -> Promise（同 key 在途合并，防重复请求）
const CACHE_TTL_MS = 10000;
let _cacheGen = 0;           // 缓存代次：invalidate 时递增；在途请求回填前校验，防写后旧数据回填
// 可缓存前缀（状态类/实时类接口绝不缓存：/cards、/tasks、/board/ready_for_merge 等）
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
  if (e) _cache.delete(key); // 过期条目即删，防长驻会话慢性增长
  return undefined;
}
function _cacheSet(key, data) {
  _cache.set(key, { t: Date.now() + CACHE_TTL_MS, data });
}
/** 写操作成功后调用：清缓存并递增代次，在途旧响应回填时被丢弃。 */
export function invalidateCache(prefix) {
  _cacheGen++;
  if (!prefix) {
    _cache.clear();
    return;
  }
  for (const k of _cache.keys()) {
    if (k.includes(prefix)) _cache.delete(k);
  }
}

// ===== GET 统一 15s 超时 + 瞬时错误 1 次静默重试 =====
const GET_TIMEOUT_MS = 15000;
function _cacheDisabled() {
  return !!(typeof window !== 'undefined' && window.__CCC_CACHE_DISABLED__);
}
/** 仅「切换中」视为主动中止（不弹网络错误）；后台标签失败如实上报。 */
let _routeSwitching = false;
export function setRouteSwitching(v) {
  _routeSwitching = !!v;
}
function _isNavAbort() {
  return _routeSwitching;
}
function _mergedSignal({ signal, pageScoped, noTimeout } = {}) {
  if (noTimeout && !pageScoped && !signal) return undefined;
  const parts = [];
  if (!noTimeout && typeof AbortSignal !== 'undefined' && AbortSignal.timeout) {
    parts.push(AbortSignal.timeout(GET_TIMEOUT_MS));
  }
  if (signal) parts.push(signal);
  if (pageScoped) parts.push(_pageScopeSignal());
  if (!parts.length) return undefined;
  if (parts.length === 1) return parts[0];
  if (typeof AbortSignal !== 'undefined' && AbortSignal.any) {
    return AbortSignal.any(parts);
  }
  // 老环境无 AbortSignal.any：手工合并——任一源中止即中止合成信号（保留超时护栏）
  const merged = new AbortController();
  const _onAbort = () => merged.abort();
  for (const p of parts) {
    if (p.aborted) { _onAbort(); break; }
    p.addEventListener('abort', _onAbort, { once: true });
  }
  return merged.signal;
}

function _headers(json = true) {
  const h = {};
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

// ===== 看板口令 token（P0 写链路打通 2026-08-29）=====
// 服务端写端点与读闸端点（/wall/api/*、/ops/* 等）均要求 Bearer token；
// token 经 POST /session 换签，暂存 localStorage，401 时清除并走登录页重换一次。
// 登录页本体见 login.js（打开即见登录页；此处动态 import 避开静态循环依赖）。
const TOKEN_KEY = 'ccc_token';
let _tokenInflight = null;

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (_) { return ''; }
}

export function setToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token); } catch (_) {}
}

export function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY); } catch (_) {}
}

/** 确保持有 token：无则唤起登录页换签（并发调用合并为一次登录页）。 */
export function ensureToken() {
  const existing = getToken();
  if (existing) return Promise.resolve(existing);
  if (_tokenInflight) return _tokenInflight;
  _tokenInflight = (async () => {
    const { showLogin } = await import('./login.js');
    return showLogin();
  })().finally(() => { _tokenInflight = null; });
  return _tokenInflight;
}

async function _fetchWithAuth(path, options = {}, json = true, allowReauth = true) {
  const method = options.method || 'GET';
  const signal = _mergedSignal({
    signal: options.signal,
    pageScoped: options.pageScoped !== false && method === 'GET',
    noTimeout: options.noTimeout === true,
  });
  const headers = { ...(options.headers || {}), ..._headers(json) };
  const tok = getToken();
  if (tok) headers['Authorization'] = 'Bearer ' + tok;
  const resp = await fetch(path, {
    method,
    headers,
    body: options.body,
    signal,
  });
  // 401（token 缺失/过期）：清掉旧 token，弹口令重签一次后重放。
  // 导航切换中不弹窗（切页 abort 的 401 无意义）。
  if (resp.status === 401 && allowReauth && !_isNavAbort()) {
    clearToken();
    await ensureToken();
    return _fetchWithAuth(path, options, json, false);
  }
  return resp;
}

function _checkGetOk(path, resp) {
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
  const cacheable = !options.signal && !_cacheDisabled() && _isCacheable(path);
  if (!cacheable) return _doGet(path, options);
  const key = _cacheKey('GET', path);
  const cached = _cacheGet(key);
  if (cached !== undefined) return cached;
  if (_inflight.has(key)) return _inflight.get(key); // 同 key 在途合并
  const genAtStart = _cacheGen;
  const p = _doGet(path, options)
    .then((data) => {
      // 写后清缓存发生在本请求在途期间 → 本次响应是写前旧快照，丢弃不回填
      if (genAtStart === _cacheGen) _cacheSet(key, data);
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
    throw new Error(data.message || data.error || ('HTTP ' + resp.status));
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
    throw new Error(data.message || data.error || ('HTTP ' + resp.status));
  }
  invalidateCache('/');
  return data;
}

export async function apiDelete(path) {
  const resp = await _fetchWithAuth(path, { method: 'DELETE' }, false);
  const data = await resp.json().catch(() => ({}));
  if (resp.ok) invalidateCache('/');
  return data;
}

// ===== 业务数据面（看板/计划/设置）=====

export async function loadProjects() {
  const data = await apiGet('/projects');
  return (data.projects || []).map((p) => ({
    id: p.id,
    name: p.name,
    role: p.is_taskable ? 'app' : 'readonly',
    engine_eligible: p.is_taskable !== false,
    is_taskable: p.is_taskable !== false,
    workspace_path: p.workspace_path || '',
    workspace: p.workspace_path || p.id,
    kind: p.kind || 'business',
  }));
}

export async function getBoardTask(taskId, workspace) {
  return apiGet('/tasks/' + encodeURIComponent(taskId));
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
