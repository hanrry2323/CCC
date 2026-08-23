/** shell-ui — 壳层全局 UI 助手。
 * 旧对话栈拆除后仅保留 copyCode：markdown 渲染的代码块复制按钮
 * （onclick="copyCode(this)" 内联调用，见 markdown.js / plansPage）。
 */

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

window.copyCode = copyCode;
