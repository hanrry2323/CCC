import { state } from './state.js';

const AUTH = 'Basic ' + btoa('ccc:claude2026');

export async function apiGet(path) {
  const resp = await fetch(path, { headers: { Authorization: AUTH } });
  if (!resp.ok) throw new Error(`GET ${path} ${resp.status}`);
  return resp.json();
}

export async function apiDelete(path) {
  const resp = await fetch(path, { method: 'DELETE', headers: { Authorization: AUTH } });
  return resp.json();
}

export async function loadProjects() {
  const data = await apiGet('/api/projects');
  return data.projects;
}

export async function loadHistory(project) {
  const data = await apiGet(`/api/history?project=${encodeURIComponent(project)}`);
  return data.sessions;
}

export async function loadSession(id, project) {
  return await apiGet(`/api/history/${id}?project=${encodeURIComponent(project)}`);
}

export async function deleteSession(id, project) {
  return await apiDelete(`/api/history/${id}?project=${encodeURIComponent(project)}`);
}

export async function streamChat(messages, sessionId, project, onEvent, onDone, onError) {
  const abortController = new AbortController();
  state.set('abortController', abortController);

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: AUTH },
      body: JSON.stringify({
        messages,
        session_id: sessionId,
        project,
        timeout: 120,
      }),
      signal: abortController.signal,
    });

    if (!resp.ok) {
      const errText = resp.status === 400 ? '危险指令已被拦截'
        : resp.status === 429 ? '前一个执行中，请稍候'
        : `请求失败: HTTP ${resp.status}`;
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
