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

  el.innerHTML =
    '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
    '<span class="toast-msg">' + message + '</span>' +
    '<div class="toast-progress" style="width:100%"></div>';

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
