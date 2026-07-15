let container = null;

function ensureContainer() {
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = [
      'position: fixed',
      'top: 52px',
      'right: 16px',
      'z-index: 200',
      'display: flex',
      'flex-direction: column',
      'gap: 8px',
      'max-width: 360px',
      'pointer-events: none',
    ].join(';');
    document.body.appendChild(container);
  }
  return container;
}

export function showToast(message, type = 'info', duration = 3000) {
  const c = ensureContainer();
  const el = document.createElement('div');
  const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
  el.style.cssText = [
    'padding: 10px 16px',
    'border-radius: 10px',
    'font-size: 13px',
    'line-height: 1.4',
    'background: var(--ccc-bg-surface)',
    'color: var(--ccc-text-base)',
    'border: 0.5px solid var(--ccc-border-base)',
    'box-shadow: var(--ccc-shadow-floating)',
    'pointer-events: auto',
    'display: flex',
    'align-items: center',
    'gap: 8px',
    'animation: msg-in 0.2s ease-out',
    'backdrop-filter: blur(20px)',
    'max-width: 100%',
  ].join(';');
  el.innerHTML = '<span>' + (icons[type] || '') + '</span><span>' + message + '</span>';
  c.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(20px)';
    el.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
    setTimeout(() => el.remove(), 200);
  }, duration);
}

window.showToast = showToast;
