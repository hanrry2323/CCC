const MAX_BYTES = 8 * 1024 * 1024;
const ALLOWED_EXT = new Set([
  '.png', '.jpg', '.jpeg', '.gif', '.webp',
  '.txt', '.md', '.csv', '.json', '.py', '.js', '.ts', '.html', '.css',
]);

let pending = [];

function extOf(name) {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i).toLowerCase() : '';
}

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('读取文件失败'));
    reader.readAsDataURL(file);
  });
}

export async function fileToAttachment(file) {
  if (!file) throw new Error('无效文件');
  if (file.size > MAX_BYTES) throw new Error('附件过大（>8MB）: ' + file.name);
  const ext = extOf(file.name || '');
  if (ext && !ALLOWED_EXT.has(ext)) throw new Error('不支持的类型: ' + ext);
  if (pending.length >= 8) throw new Error('最多 8 个附件');

  const dataUrl = await readAsDataURL(file);
  const att = {
    id: 'att-' + Date.now() + '-' + Math.random().toString(36).slice(2, 7),
    name: file.name || ('file' + ext),
    type: file.type || 'application/octet-stream',
    size: file.size,
    content_base64: dataUrl,
    preview: file.type.startsWith('image/') ? dataUrl : null,
  };
  pending.push(att);
  return att;
}

export function getPendingAttachments() {
  return pending.slice();
}

export function clearAttachments() {
  pending = [];
}

export function removeAttachment(id) {
  pending = pending.filter(a => a.id !== id);
}

export function renderAttachmentChips() {
  const wrap = document.getElementById('attachment-chips');
  if (!wrap) return;
  if (!pending.length) {
    wrap.innerHTML = '';
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  wrap.innerHTML = pending.map(a => {
    const thumb = a.preview
      ? '<img class="att-thumb" src="' + a.preview + '" alt="">'
      : '<span class="att-file-icon">📄</span>';
    return '<div class="att-chip" data-id="' + a.id + '">' +
      thumb +
      '<span class="att-name">' + escape(a.name) + '</span>' +
      '<button type="button" class="att-remove" data-id="' + a.id + '" aria-label="移除">×</button>' +
      '</div>';
  }).join('');

  wrap.querySelectorAll('.att-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      removeAttachment(btn.dataset.id);
      renderAttachmentChips();
      const input = document.getElementById('composer-input');
      const sendBtn = document.getElementById('send-btn');
      if (sendBtn) {
        sendBtn.disabled = (!input?.value.trim() && !pending.length);
      }
    });
  });
}

function escape(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
