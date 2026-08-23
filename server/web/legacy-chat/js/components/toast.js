let container = null;
let toastId = 0;

function ensureContainer() {
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
}

export function showToast(message, type = 'info', duration = 3000) {
  const c = ensureContainer();
  const id = ++toastId;
  const el = document.createElement('div');
  el.className = 'toast-item toast-' + type;

  const icons = { info: 'ℹ', success: '✓', error: '✗', warning: '⚠' };

  // 2026-08-24 修复：message 常含服务端返回的 detail/error 原文，直插 innerHTML
  // 构成注入面；图标是内部常量可保留 innerHTML，正文改 textContent。
  el.innerHTML =
    '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
    '<span class="toast-msg"></span>' +
    '<div class="toast-progress" style="width:100%"></div>';
  el.querySelector('.toast-msg').textContent = String(message ?? '');

  c.appendChild(el);

  // Animate progress bar
  const progress = el.querySelector('.toast-progress');
  if (progress) {
    requestAnimationFrame(() => {
      progress.style.transition = 'width ' + duration + 'ms linear';
      progress.style.width = '0%';
    });
  }

  setTimeout(() => {
    el.classList.add('toast-exit');
    setTimeout(() => {
      if (el.parentNode) el.remove();
    }, 250);
  }, duration);
}

window.showToast = showToast;
