function toggleMobileSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (!sidebar) return;
  sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('show');
  /* Hub 壳始终锁死 body 滚动（iOS 勿放开，否则整页可滑） */
  document.body.style.overflow = 'hidden';
}

function copyCode(btn) {
  const pre = btn.closest('.code-block-wrap')?.querySelector('pre');
  const code = pre ? (pre.textContent || pre.innerText) : '';
  navigator.clipboard.writeText(code).then(() => {
    const orig = btn.textContent;
    btn.textContent = '已复制';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  }).catch(() => {
    btn.textContent = '复制失败';
  });
}

document.addEventListener('DOMContentLoaded', function () {
  const fab = document.getElementById('scroll-fab');
  const messages = document.getElementById('messages');
  if (fab && messages) {
    messages.addEventListener('scroll', function () {
      const atBottom = messages.scrollTop + messages.clientHeight >= messages.scrollHeight - 200;
      fab.classList.toggle('show', !atBottom);
    });
    fab.addEventListener('click', function () {
      messages.scrollTop = messages.scrollHeight;
      fab.classList.remove('show');
    });
  }

  const sidebarToggle = document.getElementById('sidebar-toggle');
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', toggleMobileSidebar);
  }
  const overlay = document.getElementById('sidebar-overlay') || document.querySelector('.sidebar-overlay');
  if (overlay) {
    overlay.addEventListener('click', toggleMobileSidebar);
  }
});

// markdown.js / message.js 仍通过 onclick 调用全局函数
window.toggleMobileSidebar = toggleMobileSidebar;
window.copyCode = copyCode;
