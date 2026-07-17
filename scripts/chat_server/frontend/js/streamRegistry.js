/** Per-tab stream registry — enables concurrent Hub conversations. */

import { state } from './state.js';

/** @type {Map<string, { abort: AbortController, sessionId: string }>} */
const _streams = new Map();

export function isTabStreaming(tabId) {
  return !!tabId && _streams.has(tabId);
}

export function isCurrentTabStreaming() {
  return isTabStreaming(state.get('activeTabId'));
}

export function anyStreaming() {
  return _streams.size > 0;
}

export function streamingTabIds() {
  return [..._streams.keys()];
}

export function beginStream(tabId, sessionId) {
  if (!tabId) return null;
  const existing = _streams.get(tabId);
  if (existing) {
    try {
      existing.abort.abort();
    } catch (_) {}
  }
  const abort = new AbortController();
  _streams.set(tabId, { abort, sessionId: sessionId || tabId });
  _emit();
  return abort;
}

export function endStream(tabId) {
  if (!tabId) return;
  _streams.delete(tabId);
  _emit();
}

export function cancelStream(tabId) {
  const sid = tabId || state.get('activeTabId');
  const entry = sid ? _streams.get(sid) : null;
  if (entry) {
    try {
      entry.abort.abort();
    } catch (_) {}
    _streams.delete(sid);
    _emit();
  }
}

export function cancelAllStreams() {
  for (const [id, entry] of _streams) {
    try {
      entry.abort.abort();
    } catch (_) {}
    _streams.delete(id);
  }
  _emit();
}

function _emit() {
  state.set('streamingCount', _streams.size);
  state.set(
    'streaming',
    isCurrentTabStreaming()
  ); // backward-compat for current-tab-only UI
  document.dispatchEvent(
    new CustomEvent('ccc-streams-changed', {
      detail: { ids: streamingTabIds(), count: _streams.size },
    })
  );
}

/** Keep legacy `streaming` flag aligned when switching tabs */
export function syncStreamingFlagForActiveTab() {
  state.set('streaming', isCurrentTabStreaming());
  document.dispatchEvent(
    new CustomEvent('ccc-streams-changed', {
      detail: { ids: streamingTabIds(), count: _streams.size },
    })
  );
}
