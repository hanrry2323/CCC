import { escapeHtml } from './utils.js';

export function renderMarkdown(text) {
  if (!text) return '';

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
    codeBlocks.push(
      '<div class="code-block-wrap">' +
      langLabel +
      '<pre><code>' + code + '</code></pre>' +
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

    // Headers
    const h1 = line.match(/^# (.+)$/);
    if (h1) { closeList(); inTable = false; out.push('<h1>' + h1[1] + '</h1>'); continue; }
    const h2 = line.match(/^## (.+)$/);
    if (h2) { closeList(); inTable = false; out.push('<h2>' + h2[1] + '</h2>'); continue; }
    const h3 = line.match(/^### (.+)$/);
    if (h3) { closeList(); inTable = false; out.push('<h3>' + h3[1] + '</h3>'); continue; }
    const h4 = line.match(/^#### (.+)$/);
    if (h4) { closeList(); inTable = false; out.push('<h4>' + h4[1] + '</h4>'); continue; }

    // Blockquote
    const bq = line.match(/^> ?(.+)$/);
    if (bq) { closeList(); inTable = false; out.push('<blockquote>' + bq[1] + '</blockquote>'); continue; }

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
      if (!inTable && i + 1 < lines.length && /^[\s|:-]+$/.test(lines[i+1].trim())) {
        closeList();
        out.push('<table><thead><tr>' + cells.map(c => '<th>' + c.trim() + '</th>').join('') + '</tr></thead><tbody>');
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

  // Inline transforms
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;margin:8px 0;">');
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
      '<summary><span>🛠</span> ' + escapeHtml(name) + '</summary>' +
      '<pre>' + escapeHtml(args) + '</pre></details>';
  });

  // Code blocks
  h = h.replace(/\x00CB(\d+)\x00/g, (_, i) => codeBlocks[parseInt(i)] || '');

  // Cleanup
  h = h.replace(/<p><\/p>/g, '');
  h = h.replace(/<p>\s*<\/p>/g, '');

  return h;
}
