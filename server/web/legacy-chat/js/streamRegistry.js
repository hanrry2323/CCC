/** Per-tab stream registry — enables concurrent Hub conversations. */

import { state } from './state.js';

/** @type {Map<string, { abort: AbortController, sessionId: string, projectId?: string }>} */
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

export function getMaxLiveStreams() {
  const n = Number(state.get('maxLiveStreams'));
  return Number.isFinite(n) && n >= 1 ? n : 4;
}

export function streamingCount() {
  return _streams.size;
}

/** Projects that currently have at least one live stream. */
export function streamingProjectIds() {
  const ids = new Set();
  for (const entry of _streams.values()) {
    if (entry.projectId) ids.add(entry.projectId);
  }
  return [...ids];
}

/**
 * @param {string} tabId
 * @param {string} sessionId
 * @param {{ projectId?: string }} [meta]
 * @returns {AbortController|null} null if at max concurrent (and not replacing same tab)
 */
export function beginStream(tabId, sessionId, meta = {}) {
  if (!tabId) return null;
  const existing = _streams.get(tabId);
  if (existing) {
    try {
      existing.abort.abort();
    } catch (_) {}
  } else if (_streams.size >= getMaxLiveStreams()) {
    return null;
  }
  const abort = new AbortController();
  _streams.set(tabId, {
    abort,
    sessionId: sessionId || tabId,
    projectId: meta.projectId || state.get('currentProject') || null,
  });
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
  state.set('streaming', isCurrentTabStreaming());
  document.dispatchEvent(
    new CustomEvent('ccc-streams-changed', {
      detail: {
        ids: streamingTabIds(),
        count: _streams.size,
        max: getMaxLiveStreams(),
        projects: streamingProjectIds(),
      },
    })
  );
}

/** Keep legacy `streaming` flag aligned when switching tabs */
export function syncStreamingFlagForActiveTab() {
  state.set('streaming', isCurrentTabStreaming());
  document.dispatchEvent(
    new CustomEvent('ccc-streams-changed', {
      detail: {
        ids: streamingTabIds(),
        count: _streams.size,
        max: getMaxLiveStreams(),
        projects: streamingProjectIds(),
      },
    })
  );
}
