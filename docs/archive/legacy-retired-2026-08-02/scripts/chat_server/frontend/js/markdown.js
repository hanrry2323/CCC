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

function highlightJS(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/\b(const|let|var|function|return|if|else|for|while|import|export|from|async|await|new|class|extends|typeof|instanceof|this|switch|case|break|continue|try|catch|finally|throw|in|of|yield|default|import\.meta)\b/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span>')
    .replace(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)/g, '<span style="color:' + SYNTAX_COLORS.string + '">$1</span>')
    .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span style="color:' + SYNTAX_COLORS.number + '">$1</span>')
    .replace(/(\/\/[^\n]*)/g, '<span style="color:' + SYNTAX_COLORS.comment + '">$1</span>')
    .replace(/\b(function|class)\b\s+(\w+)/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span> <span style="color:' + SYNTAX_COLORS.function + '">$2</span>');
}

function highlightPython(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|pass|break|continue|async|await|yield|lambda|self|None|True|False|raise|in|not|and|or|is|del|print)\b/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span>')
    .replace(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|"""(?:[^"]*(?:"""))?|'''(?:[^']*(?:'''))?)/g, '<span style="color:' + SYNTAX_COLORS.string + '">$1</span>')
    .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span style="color:' + SYNTAX_COLORS.number + '">$1</span>')
    .replace(/(#[^\n]*)/g, '<span style="color:' + SYNTAX_COLORS.comment + '">$1</span>')
    .replace(/\b(def|class)\b\s+(\w+)/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span> <span style="color:' + SYNTAX_COLORS.function + '">$2</span>');
}

function highlightHTML(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/(&lt;\/?)(\w+)/g, '$1<span style="color:' + SYNTAX_COLORS.tag + '">$2</span>')
    .replace(/(\w+)(=)("(?:[^"\\]|\\.)*")/g, '<span style="color:' + SYNTAX_COLORS.attr + '">$1</span>=$2<span style="color:' + SYNTAX_COLORS.string + '">$3</span>')
    .replace(/(&lt;!--[\s\S]*?--&gt;)/g, '<span style="color:' + SYNTAX_COLORS.comment + '">$1</span>');
}

function highlightCSS(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/(\/\*[\s\S]*?\*\/)/g, '<span style="color:' + SYNTAX_COLORS.comment + '">$1</span>')
    .replace(/(#[0-9a-fA-F]{3,8}|\b(rgb|rgba|hsl|hsla)\([^)]+\)|\b[a-z-]+(?=\s*:))/g, '<span style="color:' + SYNTAX_COLORS.attr + '">$1</span>')
    .replace(/(&quot;[^&]*&quot;)/g, '<span style="color:' + SYNTAX_COLORS.string + '">$1</span>');
}

function highlightJSON(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/("(?:[^"\\]|\\.)*")/g, '<span style="color:' + SYNTAX_COLORS.string + '">$1</span>')
    .replace(/\b(true|false|null)\b/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span>')
    .replace(/\b(\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/g, '<span style="color:' + SYNTAX_COLORS.number + '">$1</span>');
}

function highlightBash(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/(#.*$)/gm, '<span style="color:' + SYNTAX_COLORS.comment + '">$1</span>')
    .replace(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, '<span style="color:' + SYNTAX_COLORS.string + '">$1</span>')
    .replace(/\b(echo|export|cd|ls|rm|cp|mv|mkdir|touch|cat|source|sudo|chmod|chown|grep|find|sed|awk|pip|npm|yarn|node|python|curl|wget|git|docker|make|cmake)\b/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span>');
}

function highlightC(code) {
  const escaped = escapeHtml(code);
  return escaped
    .replace(/\b(int|float|double|char|void|bool|string|auto|const|static|struct|class|enum|if|else|for|while|do|switch|case|break|continue|return|try|catch|throw|new|delete|public|private|protected|namespace|using|template|typename|virtual|override|final|import|export|fn|let|mut|impl|trait|pub|async|await|let|match|move|ref|dyn|where|as|use|mod|super|crate|Self)\b/g, '<span style="color:' + SYNTAX_COLORS.keyword + '">$1</span>')
    .replace(/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, '<span style="color:' + SYNTAX_COLORS.string + '">$1</span>')
    .replace(/\b(\d+(?:\.\d+)?[fFlLuU]?)\b/g, '<span style="color:' + SYNTAX_COLORS.number + '">$1</span>')
    .replace(/(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g, '<span style="color:' + SYNTAX_COLORS.comment + '">$1</span>');
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

  // Guard code blocks
  const codeBlocks = [];
  let h = escapeHtml(text);
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const i = codeBlocks.length;
    const langLabel = lang ? '<span class="code-lang-label">' + lang + '</span>' : '';
    const highlighted = lang ? highlightSyntax(code, lang) : code;
    codeBlocks.push(
      '<div class="code-block-wrap">' +
      langLabel +
      '<pre><code>' + highlighted + '</code></pre>' +
      '<button class="copy-btn" onclick="copyCode(this)">复制</button>' +
      '</div>'
    );
    return '\x00CB' + i + '\x00';
  });

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

  // Inline transforms — links, images, bold, italic, strikethrough
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;margin:10px 0;border-radius:var(--ccc-radius-md)">');
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
