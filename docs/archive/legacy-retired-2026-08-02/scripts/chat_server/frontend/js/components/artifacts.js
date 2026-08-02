import { escapeHtml } from '../utils.js';

const ARTIFACT_RE = /```(html|svg|mermaid|markdown|md)\n([\s\S]*?)```/gi;

export function extractArtifacts(content) {
  const items = [];
  let m;
  const re = new RegExp(ARTIFACT_RE.source, 'gi');
  while ((m = re.exec(content)) !== null) {
    items.push({ lang: m[1].toLowerCase(), code: m[2] });
  }
  return items;
}

export function maybeShowArtifacts(content) {
  const items = extractArtifacts(content);
  if (!items.length) return;
  const last = items[items.length - 1];
  openArtifactPanel(last);
}

export function openArtifactPanel(item) {
  let panel = document.getElementById('artifact-panel');
  if (!panel) {
    panel = document.createElement('aside');
    panel.id = 'artifact-panel';
    panel.innerHTML =
      '<div class="artifact-header">' +
        '<span class="artifact-title">Preview</span>' +
        '<div class="artifact-actions">' +
          '<button type="button" id="artifact-open-tab" class="artifact-btn">新标签</button>' +
          '<button type="button" id="artifact-close" class="artifact-btn">关闭</button>' +
        '</div>' +
      '</div>' +
      '<div class="artifact-body" id="artifact-body"></div>';
    document.getElementById('layout')?.appendChild(panel);
    document.getElementById('artifact-close')?.addEventListener('click', closeArtifactPanel);
  }

  const body = document.getElementById('artifact-body');
  const lang = item.lang === 'md' ? 'markdown' : item.lang;

  if (lang === 'html' || lang === 'svg') {
    body.innerHTML = '<iframe class="artifact-frame" sandbox="allow-scripts" title="artifact"></iframe>';
    const frame = body.querySelector('iframe');
    const doc = lang === 'svg'
      ? '<!DOCTYPE html><html><body style="margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#faf8f5">' +
        item.code + '</body></html>'
      : item.code;
    frame.srcdoc = doc;
    document.getElementById('artifact-open-tab')?.addEventListener('click', () => {
      const w = window.open('', '_blank');
      if (w) {
        w.document.write(doc);
        w.document.close();
      }
    }, { once: true });
  } else if (lang === 'mermaid') {
    body.innerHTML = '<pre class="artifact-code">' + escapeHtml(item.code) + '</pre>' +
      '<p class="artifact-note">Mermaid 源码预览（渲染器未内置，可复制到支持 Mermaid 的工具）</p>';
  } else {
    body.innerHTML = '<pre class="artifact-code">' + escapeHtml(item.code) + '</pre>';
  }

  panel.classList.add('open');
  document.getElementById('layout')?.classList.add('with-artifact');
}

export function closeArtifactPanel() {
  document.getElementById('artifact-panel')?.classList.remove('open');
  document.getElementById('layout')?.classList.remove('with-artifact');
}
