import { escapeHtml } from '../utils.js';

export function createToolCard(toolData) {
  const card = document.createElement('div');
  card.className = 'tool-card';
  card.dataset.toolId = toolData.id || '';

  const name = toolData.name || 'tool';
  const input = toolData.input || {};
  const inputStr = Object.keys(input).length ? JSON.stringify(input, null, 2) : '';

  card.innerHTML =
    '<div class="tool-card-header">' +
      '<span class="tool-card-status pending">⏳</span>' +
      '<span class="tool-card-name">' + escapeHtml(name) + '</span>' +
      '<span class="tool-card-duration"></span>' +
      '<span class="tool-card-arrow">›</span>' +
    '</div>' +
    '<div class="tool-card-body">' +
      '<div class="tool-card-section">' +
        '<div class="tool-card-section-label">Input</div>' +
        '<pre>' + (inputStr ? escapeHtml(inputStr) : '(no input)') + '</pre>' +
      '</div>' +
      '<div class="tool-card-section tool-result-section" style="display:none">' +
        '<div class="tool-card-section-label">Result</div>' +
        '<pre></pre>' +
      '</div>' +
    '</div>';

  const header = card.querySelector('.tool-card-header');
  header.addEventListener('click', () => {
    card.classList.toggle('open');
  });

  return card;
}

export function updateToolCardStatus(card, status, data) {
  const statusEl = card.querySelector('.tool-card-status');
  const durationEl = card.querySelector('.tool-card-duration');

  statusEl.className = 'tool-card-status';

  if (status === 'running') {
    statusEl.textContent = '⋯';
    statusEl.classList.add('running');
  } else if (status === 'completed') {
    statusEl.textContent = '✓';
    statusEl.classList.add('completed');
  } else if (status === 'error') {
    statusEl.textContent = '✗';
    statusEl.classList.add('error');
  } else {
    statusEl.textContent = '⏳';
    statusEl.classList.add('pending');
  }

  if (data && data.duration) {
    durationEl.textContent = formatDuration(data.duration);
  }

  if (status === 'completed' || status === 'error') {
    card.classList.add('open');
  }
}

export function setToolResult(card, resultContent) {
  const section = card.querySelector('.tool-result-section');
  const pre = section?.querySelector('pre');
  if (!section || !pre) return;

  const content = typeof resultContent === 'string'
    ? resultContent
    : JSON.stringify(resultContent, null, 2);

  pre.textContent = content;
  section.style.display = 'block';
}

export function createThinkingIndicator() {
  const el = document.createElement('div');
  el.className = 'thinking-indicator';
  el.innerHTML = '<div class="spinner" style="width:14px;height:14px;"></div> 正在调用工具...';
  return el;
}

function formatDuration(seconds) {
  if (!seconds) return '';
  if (seconds < 1) return Math.round(seconds * 1000) + 'ms';
  if (seconds < 60) return seconds.toFixed(1) + 's';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m + 'm ' + s + 's';
}
