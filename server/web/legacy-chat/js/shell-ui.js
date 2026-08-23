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
  // navigator.clipboard 仅存在于安全上下文（HTTPS/localhost）；CCC 明确支持
  // 手机经 HTTP 内网 IP 直连 :7788，此时需降级 execCommand，且同步抛错要兜住
  const done = () => {
    const orig = btn.textContent;
    btn.textContent = '已复制';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  };
  const fail = () => { btn.textContent = '复制失败'; };
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done).catch(fail);
      return;
    }
    const ta = document.createElement('textarea');
    ta.value = code;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    ok ? done() : fail();
  } catch (_) {
    fail();
  }
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
