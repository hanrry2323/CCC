import { escapeHtml } from './utils.js';

const SYNTAX_COLORS = {
  keyword: '#ff6b6b',
  string: '#69db7c',
  number: '#ffd43b',
  comment: '#868e96',
  function: '#74c0fc',
  class: '#b197fc',
  tag: '#ff8787',
  attr: '#63e6be',
  punctuation: '#dee2e6',
};

// ── 占位符保护管线（2026-08-24 重构）─────────────────────────
// 旧实现对「已注入 <span style="…"> 的中间结果」继续跑后续正则，
// 字符串规则会吞掉自身 style 属性的引号 → 带语言代码块确定性花屏。
// 新约定：每趟命中立刻转义、包 span、存入 store 并替换为占位符；
// 后续趟只处理未保护的原文，互不污染；最后统一还原。
function _wrap(cls, raw, store) {
  store.push('<span style="color:' + SYNTAX_COLORS[cls] + '">' + escapeHtml(raw) + '</span>');
  return '\x00HP' + (store.length - 1) + '\x00';
}
function _restore(s, store) {
  return s.replace(/\x00HP(\d+)\x00/g, (_, i) => store[+i] || '');
}

function highlightJS(code) {
  const store = [];
  let h = code
    .replace(/(\/\/[^\n]*)/g, (m) => _wrap('comment', m, store))
    .replace(/("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|`(?:[^`\\]|\\.)*`)/g, (m) => _wrap('string', m, store))
    .replace(/\b(const|let|var|function|return|if|else|for|while|import|export|from|async|await|new|class|extends|typeof|instanceof|this|switch|case|break|continue|try|catch|finally|throw|in|of|yield|default)\b/g, (m) => _wrap('keyword', m, store))
    .replace(/\b(function|class)\b(\s*)(\w+)/g, (_, kw, sp, name) =>
      _wrap('keyword', kw, store) + escapeHtml(sp) + _wrap('function', name, store))
    .replace(/\b(\d+(?:\.\d+)?)\b/g, (m) => _wrap('number', m, store));
  return _restore(h, store);
}

function highlightPython(code) {
  const store = [];
  let h = code
    .replace(/(#[^\n]*)/g, (m) => _wrap('comment', m, store))
    .replace(/("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')/g, (m) => _wrap('string', m, store))
    .replace(/\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|pass|break|continue|async|await|yield|lambda|self|None|True|False|raise|in|not|and|or|is|del|print)\b/g, (m) => _wrap('keyword', m, store))
    .replace(/\b(def|class)\b(\s*)(\w+)/g, (_, kw, sp, name) =>
      _wrap('keyword', kw, store) + escapeHtml(sp) + _wrap('function', name, store))
    .replace(/\b(\d+(?:\.\d+)?)\b/g, (m) => _wrap('number', m, store));
  return _restore(h, store);
}

function highlightHTML(code) {
  // HTML/XML 只能在实体化之后的文本上识别标签结构
  const store = [];
  let h = escapeHtml(code)
    .replace(/(&lt;!--[\s\S]*?--&gt;)/g, (m) => { store.push('<span style="color:' + SYNTAX_COLORS.comment + '">' + m + '</span>'); return '\x00HP' + (store.length - 1) + '\x00'; })
    .replace(/(&lt;\/?)(\w+)/g, (_, lt, name) =>
      // lt 是已实体化的 &lt;/&lt;/（勿再转义），仅标签名需要包 span
      lt + (() => { store.push('<span style="color:' + SYNTAX_COLORS.tag + '">' + name + '</span>'); return '\x00HP' + (store.length - 1) + '\x00'; })())
    .replace(/([\w-]+)(=)(&quot;[\s\S]*?&quot;)/g, (_, attr, eq, val) => {
      const parts = [];
      parts.push(_storeHtml('<span style="color:' + SYNTAX_COLORS.attr + '">' + attr + '</span>', store));
      parts.push(eq);
      parts.push(_storeHtml('<span style="color:' + SYNTAX_COLORS.string + '">' + val + '</span>', store));
      return parts.join('');
    });
  return _restore(h, store);
}
function _storeHtml(html, store) { store.push(html); return '\x00HP' + (store.length - 1) + '\x00'; }

function highlightCSS(code) {
  const store = [];
  let h = code
    .replace(/(\/\*[\s\S]*?\*\/)/g, (m) => _wrap('comment', m, store))
    .replace(/("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')/g, (m) => _wrap('string', m, store))
    .replace(/(#[0-9a-fA-F]{3,8}\b|\b[a-z-]+(?=\s*:))/g, (m) => _wrap('attr', m, store));
  return _restore(h, store);
}

function highlightJSON(code) {
  const store = [];
  let h = code
    .replace(/("(?:[^"\\]|\\.)*")(\s*:)?/g, (m, str, colon) => {
      // 键与值同色即可；冒号留在原文
      const out = _wrap('string', str, store);
      return colon ? out + colon : out;
    })
    .replace(/\b(true|false|null)\b/g, (m) => _wrap('keyword', m, store))
    .replace(/\b(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/gi, (m) => _wrap('number', m, store));
  return _restore(h, store);
}

function highlightBash(code) {
  const store = [];
  let h = code
    .replace(/(#.*$)/gm, (m) => _wrap('comment', m, store))
    .replace(/("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')/g, (m) => _wrap('string', m, store))
    .replace(/\b(echo|export|cd|ls|rm|cp|mv|mkdir|touch|cat|source|sudo|chmod|chown|grep|find|sed|awk|pip|npm|yarn|node|python|curl|wget|git|docker|make|cmake)\b/g, (m) => _wrap('keyword', m, store));
  return _restore(h, store);
}

function highlightC(code) {
  const store = [];
  let h = code
    .replace(/(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g, (m) => _wrap('comment', m, store))
    .replace(/("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')/g, (m) => _wrap('string', m, store))
    .replace(/\b(int|float|double|char|void|bool|string|auto|const|static|struct|class|enum|if|else|for|while|do|switch|case|break|continue|return|try|catch|throw|new|delete|public|private|protected|namespace|using|template|typename|virtual|override|final|import|export|fn|let|mut|impl|trait|pub|async|await|match|move|ref|dyn|where|as|use|mod|super|crate|Self)\b/g, (m) => _wrap('keyword', m, store))
    .replace(/\b(\d+(?:\.\d+)?[fFlLuU]?)\b/g, (m) => _wrap('number', m, store));
  return _restore(h, store);
}

function highlightSyntax(code, lang) {
  lang = lang.toLowerCase();
  if (['js', 'javascript', 'ts', 'typescript', 'jsx', 'tsx'].includes(lang)) {
    return highlightJS(code);
  }
  if (['py', 'python'].includes(lang)) return highlightPython(code);
  if (['html', 'xml', 'svg'].includes(lang)) return highlightHTML(code);
  if (['css', 'scss', 'less'].includes(lang)) return highlightCSS(code);
  if (['json'].includes(lang)) return highlightJSON(code);
  if (['bash', 'sh', 'zsh', 'shell'].includes(lang)) return highlightBash(code);
  if (['c', 'cpp', 'c++', 'java', 'cs', 'go', 'rust'].includes(lang)) return highlightC(code);
  return escapeHtml(code);
}

export function renderMarkdown(text) {
  if (!text) return '';

  // 折叠 ccc-transfer 契约（白话给人看，JSON 折叠）
  let transferFold = '';
  text = String(text).replace(
    /```\s*ccc-transfer\s*\r?\n([\s\S]*?)\r?\n```/gi,
    (_, json) => {
      transferFold +=
        '<details class="transfer-fold"><summary>转任务契约（ccc-transfer）</summary><pre>' +
        escapeHtml(String(json || '').trim()) +
        '</pre></details>';
      return '';
    }
  );

  // Guard tool_call XML
  const toolCalls = [];
  text = text.replace(/<tool_call>[\s\S]*?<\/tool_call>/g, (m) => {
    const i = toolCalls.length;
    toolCalls.push(m);
    return '\x00TC' + i + '\x00';
  });

  // Guard code blocks（2026-08-24 修复双重转义：先在原文上截获围栏原始代码，
  // 高亮器内部各自 escapeHtml 一次；占位符 \x00CBn\x00 不受后续全文转义影响）
  const codeBlocks = [];
  text = text.replace(/```(\w*)[ \t]*\r?\n([\s\S]*?)```/g, (_, lang, code) => {
    const i = codeBlocks.length;
    const langLabel = lang ? '<span class="code-lang-label">' + lang + '</span>' : '';
    const highlighted = lang ? highlightSyntax(code, lang) : escapeHtml(code);
    codeBlocks.push(
      '<div class="code-block-wrap">' +
      langLabel +
      '<pre><code>' + highlighted + '</code></pre>' +
      '<button class="copy-btn" onclick="copyCode(this)">复制</button>' +
      '</div>'
    );
    return '\x00CB' + i + '\x00';
  });

  let h = escapeHtml(text);

  // Guard inline code
  const inlineCodes = [];
  h = h.replace(/`([^`]+)`/g, (_, c) => {
    const i = inlineCodes.length;
    inlineCodes.push('<code>' + c + '</code>');
    return '\x00IC' + i + '\x00';
  });

  // Block-level transforms
  const lines = h.split('\n');
  const out = [];
  let inTable = false;
  let inList = false;
  let listType = null;

  function closeList() {
    if (inList) {
      out.push(listType === 'ol' ? '</ol>' : '</ul>');
      inList = false;
      listType = null;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trimEnd();

    // HR
    if (/^[-*_]{3,}\s*$/.test(line.trim())) {
      closeList(); inTable = false;
      out.push('<hr>');
      continue;
    }

    // Headers (h1-h4)
    const hMatch = line.match(/^(#{1,4})\s+(.+)$/);
    if (hMatch) {
      closeList(); inTable = false;
      const level = hMatch[1].length;
      out.push('<h' + level + '>' + hMatch[2] + '</h' + level + '>');
      continue;
    }

    // Blockquote
    const bq = line.match(/^> ?(.+)$/);
    if (bq) { closeList(); inTable = false; out.push('<blockquote>' + bq[1] + '</blockquote>'); continue; }

    // Task list
    const task = line.match(/^[-*+] \[([ xX])\] (.+)$/);
    if (task) {
      if (!inList || listType !== 'ul') { closeList(); out.push('<ul>'); inList = true; listType = 'ul'; }
      const checked = task[1] !== ' ' ? ' checked' : '';
      out.push('<li style="list-style:none;margin-left:-20px"><label style="display:flex;align-items:center;gap:6px;cursor:pointer">' +
        '<input type="checkbox"' + checked + ' disabled style="accent-color:var(--ccc-bg-accent)">' +
        task[2] + '</label></li>');
      continue;
    }

    // Unordered list
    const ul = line.match(/^[-*+] (.+)$/);
    if (ul) {
      if (!inList || listType !== 'ul') { closeList(); out.push('<ul>'); inList = true; listType = 'ul'; }
      out.push('<li>' + ul[1] + '</li>');
      continue;
    }

    // Ordered list
    const ol = line.match(/^\d+\.\s+(.+)$/);
    if (ol) {
      if (!inList || listType !== 'ol') { closeList(); out.push('<ol>'); inList = true; listType = 'ol'; }
      out.push('<li>' + ol[1] + '</li>');
      continue;
    }

    // Table
    if (line.includes('|')) {
      const cells = line.split('|').filter(Boolean);
      if (!inTable && i + 1 < lines.length && /^[\s|:-]+$/.test(lines[i + 1].trim())) {
        closeList();
        const headerCells = cells.map(c => {
          const trimmed = c.trim();
          const align = trimmed.startsWith(':') && trimmed.endsWith(':') ? ' style="text-align:center"'
            : trimmed.endsWith(':') ? ' style="text-align:right"'
            : '';
          return '<th' + align + '>' + trimmed.replace(/:-+/g, '').replace(/-+/g, '').trim() + '</th>';
        });
        out.push('<table><thead><tr>' + headerCells.join('') + '</tr></thead><tbody>');
        inTable = true;
        i++;
        continue;
      } else if (inTable && cells.length > 1) {
        out.push('<tr>' + cells.map(c => '<td>' + c.trim() + '</td>').join('') + '</tr>');
        continue;
      }
    } else if (inTable) {
      out.push('</tbody></table>');
      inTable = false;
    }

    closeList();

    if (line.trim() === '') {
      out.push('</p><p>');
      continue;
    }

    out.push(line);
  }
  closeList();
  if (inTable) out.push('</tbody></table>');

  h = out.join('\n');

  // Wrap paragraphs
  h = h.replace(/^(?!<[a-z/]|$)(.+)$/gm, '<p>$1</p>');
  h = h.replace(/<\/p>\s*<p><\/p>/g, '</p><p>');

  // Inline transforms — images（先于 links，否则 ![alt](url) 被链接规则吃掉）、
  // links（2026-08-24 安全修复：href 协议白名单，堵 javascript:/data:/vbscript: 注入）、
  // bold, italic, strikethrough
  const _safeUrl = (u) => {
    const clean = String(u).replace(/[\s\x00-\x1f]/g, '');
    return /^(https?:\/\/|mailto:|#|\/|\.\.?\/)/i.test(clean);
  };
  const _safeImg = (u) => {
    const clean = String(u).replace(/[\s\x00-\x1f]/g, '');
    return /^(https?:\/\/|data:image\/(png|jpeg|gif|webp);)/i.test(clean);
  };
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (m, alt, src) =>
    _safeImg(src)
      ? '<img src="' + src + '" alt="' + alt + '" style="max-width:100%;margin:10px 0;border-radius:var(--ccc-radius-md)">'
      : alt); // alt/src 均取自已转义文本，回退分支无注入面
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, txt, url) =>
    _safeUrl(url)
      ? '<a href="' + url + '" target="_blank" rel="noopener">' + txt + '</a>'
      : txt + '（' + url + '）');
  h = h.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');

  // Restore inline code
  h = h.replace(/\x00IC(\d+)\x00/g, (_, i) => inlineCodes[parseInt(i)] || '');

  // Tool calls
  h = h.replace(/\x00TC(\d+)\x00/g, (_, i) => {
    const raw = toolCalls[parseInt(i)] || '';
    const nameMatch = raw.match(/<tool_call>[\s\S]*?"name"\s*:\s*"([^"]+)"/);
    const argMatch = raw.match(/<tool_call>[\s\S]*?"arguments"\s*:\s*\{([^}]+)\}/);
    const name = nameMatch ? nameMatch[1] : 'tool';
    const args = argMatch ? '{' + argMatch[1] + '}' : raw.replace(/<\/?tool_call>/g, '').trim();
    return '<details class="tool-card" style="margin:8px 0">' +
      '<summary style="padding:8px 12px;cursor:pointer;font-size:13px;font-weight:500;color:var(--ccc-text-accent);display:flex;align-items:center;gap:6px;">' +
      '<span>🛠</span> ' + escapeHtml(name) + '</summary>' +
      '<pre style="padding:8px 12px;font-size:13px;overflow-x:auto;border-top:0.5px solid var(--ccc-border-base);white-space:pre-wrap;margin:0;">' +
      escapeHtml(args) + '</pre></details>';
  });

  // Restore code blocks
  h = h.replace(/\x00CB(\d+)\x00/g, (_, i) => codeBlocks[parseInt(i)] || '');

  // Cleanup
  h = h.replace(/<p><\/p>/g, '');
  h = h.replace(/<p>\s*<\/p>/g, '');

  return h + transferFold;
}
