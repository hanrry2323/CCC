/* CCC 看板 · 对话视图 —— Claude 风格（对齐桌面端 CCCTheme）。
 * 登录（账号密码换 token）+ 对话（POST /conversation，非流式）。
 * 仅在 HTTP API 模式（?api=... 或同源 http: 直开）下生效；file:// 零 API 模式不显示对话。
 *
 * 协议（与 T23 一致，不动 API/鉴权）：
 *   POST /session        {username,password} → {token,expires_at,ttl_s}
 *   POST /conversation   {message} + Bearer token → {reply}
 *   token：localStorage "ccc-chat-token" 优先 > URL ?token=（经 app.js cccAuth 统一管理）
 *
 * composer 视觉对齐桌面端：模型选择(flash/Pro/code) + 附件按钮 + 输入框 + 发送按钮。
 *   - 模型选择：本地偏好（localStorage），服务端 /conversation 不接受 model 字段，故仅本地；
 *   - 附件按钮：仅本地预览（服务端 /conversation 暂仅文本），不上传。
 */
(function () {
  "use strict";

  var API_BASE = window.API_BASE_URL || null;

  // ── token 统一管理：复用 app.js 的 cccAuth（localStorage 优先 > URL ?token=） ──
  function getToken() {
    if (window.cccAuth) return window.cccAuth.getToken();
    try {
      var t = localStorage.getItem("ccc-chat-token");
      if (t) return t;
    } catch (e) { /* file:// 可能禁用 localStorage */ }
    return window.BOARD_TOKEN || null;
  }
  function setToken(t) {
    if (window.cccAuth) window.cccAuth.setToken(t);
    else { try { localStorage.setItem("ccc-chat-token", t); } catch (e) {} }
  }
  function clearToken() {
    if (window.cccAuth) window.cccAuth.clearToken();
    else { try { localStorage.removeItem("ccc-chat-token"); } catch (e) {} }
  }

  // ── 模型偏好（本地） ──
  var MODEL_KEY = "ccc-chat-model";
  function getModel() {
    try { return localStorage.getItem(MODEL_KEY) || "flash"; } catch (e) { return "flash"; }
  }
  function setModel(m) {
    try { localStorage.setItem(MODEL_KEY, m); } catch (e) {}
  }

  // ── 附件（仅本地预览） ──
  var attachments = [];
  var sending = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  // ── 视图切换 ──
  function showLogin(msg, isErr) {
    document.getElementById("login-area").style.display = "";
    document.getElementById("chat-area").style.display = "none";
    if (msg) {
      var m = document.getElementById("login-msg");
      m.textContent = msg;
      m.className = "chat-form-msg" + (isErr ? " is-error" : "");
    }
  }
  function showChat() {
    document.getElementById("login-area").style.display = "none";
    document.getElementById("chat-area").style.display = "";
    syncWelcome();
  }

  function setChatMsg(text, kind) {
    var m = document.getElementById("chat-msg");
    m.textContent = text || "";
    m.className = "chat-composer-msg" + (kind ? " is-" + kind : "");
  }

  // ── 消息渲染：用户右 / Agent 左，角色标签 + 气泡 ──
  function msgInner() {
    var box = document.getElementById("chat-messages");
    var inner = box.querySelector(".chat-messages-inner");
    if (!inner) {
      inner = el("div", "chat-messages-inner");
      box.appendChild(inner);
    }
    return inner;
  }

  function renderMessage(role, text, opts) {
    opts = opts || {};
    var inner = msgInner();
    var row = el("div", "chat-msg is-" + role + (opts.typing ? " is-typing" : ""));
    row.appendChild(el("div", "chat-msg-label", role === "user" ? "我" : "Agent"));
    var bubble = el("div", "chat-msg-bubble" + (opts.typing ? " typing-dots" : ""), text);
    row.appendChild(bubble);
    inner.appendChild(row);
    var box = document.getElementById("chat-messages");
    box.scrollTop = box.scrollHeight;
    syncWelcome();
    return row;
  }

  function removeNode(node) {
    if (node && node.parentNode) node.parentNode.removeChild(node);
  }

  function syncWelcome() {
    var w = document.getElementById("chat-welcome");
    if (!w) return;
    var inner = document.getElementById("chat-messages").querySelector(".chat-messages-inner");
    var hasMsgs = inner && inner.children.length > 0;
    w.classList.toggle("is-hidden", hasMsgs);
  }

  // ── 登录：POST /session ──
  function doLogin() {
    if (!API_BASE) {
      showLogin("对话需要 HTTP API 模式：在 URL 加 ?api=http://host:port", true);
      return;
    }
    var user = document.getElementById("login-user").value.trim();
    var pass = document.getElementById("login-pass").value;
    if (!user || !pass) {
      showLogin("请填写账号和密码", true);
      return;
    }
    var btn = document.getElementById("login-btn");
    btn.disabled = true;
    showLogin("登录中…", false);
    fetch(API_BASE.replace(/\/+$/, "") + "/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pass })
    }).then(function (r) {
      return r.json().then(function (d) { return { status: r.status, data: d }; });
    }).then(function (res) {
      btn.disabled = false;
      if (res.status === 200 && res.data.token) {
        setToken(res.data.token);
        window.BOARD_TOKEN = res.data.token;
        showChat();
        setChatMsg("登录成功，token 有效期 " + (res.data.ttl_s || 0) + " 秒", "ok");
        // T23：登录成功后刷新看板数据（app.js 的 cccRefreshBoard 已用新 token）
        if (window.cccRefreshBoard) window.cccRefreshBoard();
      } else {
        showLogin("登录失败：" + (res.data.error || res.status), true);
      }
    }).catch(function (e) {
      btn.disabled = false;
      showLogin("登录请求失败：" + e, true);
    });
  }

  // ── 退出登录 ──
  function doLogout() {
    clearToken();
    try { delete window.BOARD_TOKEN; } catch (e) { window.BOARD_TOKEN = null; }
    // 清空消息
    var inner = document.getElementById("chat-messages").querySelector(".chat-messages-inner");
    if (inner) inner.innerHTML = "";
    showLogin("", false);
  }

  // ── 对话：POST /conversation ──
  function doSend() {
    if (sending) return;
    var input = document.getElementById("chat-input");
    var text = input.value.trim();
    if (!text) return;
    var token = getToken();
    if (!token) {
      showLogin("token 已过期，请重新登录", true);
      return;
    }
    sending = true;
    setSendDisabled(true);
    renderMessage("user", text);
    // 清空输入 + 附件
    input.value = "";
    autoGrow(input);
    // 附件仅本地预览：发送时若有附件，提示不会上传
    if (attachments.length) {
      setChatMsg("附件仅本地预览，不会随消息发送（服务端 /conversation 暂仅文本）", "ok");
    } else {
      setChatMsg("生成中…", "");
    }
    // 思考占位
    var typing = renderMessage("assistant", "思考中", { typing: true });

    fetch(API_BASE.replace(/\/+$/, "") + "/conversation", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
      },
      body: JSON.stringify({ message: text })
    }).then(function (r) {
      return r.json().then(function (d) { return { status: r.status, data: d }; });
    }).then(function (res) {
      sending = false;
      setSendDisabled(false);
      removeNode(typing);
      if (res.status === 200 && res.data.reply) {
        renderMessage("assistant", res.data.reply);
        setChatMsg("");
      } else if (res.status === 401) {
        clearToken();
        showLogin("会话已过期（401），请重新登录", true);
      } else if (res.status === 503) {
        setChatMsg("服务端未配置对话上游（503）：" + (res.data.error || ""), "error");
      } else if (res.status === 502) {
        setChatMsg("上游调用失败（502）：" + (res.data.error || ""), "error");
      } else {
        setChatMsg("对话失败：" + (res.data.error || res.status), "error");
      }
    }).catch(function (e) {
      sending = false;
      setSendDisabled(false);
      removeNode(typing);
      setChatMsg("请求失败：" + e, "error");
    });
  }

  function setSendDisabled(flag) {
    var btn = document.getElementById("chat-send");
    if (!btn) return;
    // 空输入也禁用
    var input = document.getElementById("chat-input");
    var empty = input ? !input.value.trim() : true;
    btn.disabled = flag || empty;
  }

  // textarea 自适应高度
  function autoGrow(ta) {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }

  // ── 附件（仅本地预览） ──
  function renderAttachments() {
    var box = document.getElementById("chat-attachments");
    if (!box) return;
    box.innerHTML = "";
    attachments.forEach(function (f, idx) {
      var chip = el("span", "chat-attach-chip");
      chip.appendChild(document.createTextNode("📎 " + f.name));
      var rm = el("button", null, "×");
      rm.title = "移除";
      rm.addEventListener("click", function () {
        attachments.splice(idx, 1);
        renderAttachments();
      });
      chip.appendChild(rm);
      box.appendChild(chip);
    });
  }

  // ── 初始化 ──
  function initChat() {
    var loginBtn = document.getElementById("login-btn");
    var sendBtn = document.getElementById("chat-send");
    var input = document.getElementById("chat-input");
    var modelSel = document.getElementById("chat-model");
    var attachBtn = document.getElementById("chat-attach");
    var fileInput = document.getElementById("chat-file-input");

    if (loginBtn) loginBtn.addEventListener("click", doLogin);
    if (sendBtn) sendBtn.addEventListener("click", doSend);

    // 登录表单回车提交
    var passField = document.getElementById("login-pass");
    if (passField) {
      passField.addEventListener("keydown", function (e) {
        if (e.key === "Enter") doLogin();
      });
    }

    if (input) {
      // IME 组字中回车不上屏不发送
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          if (e.isComposing || e.keyCode === 229) return;
          if (e.shiftKey) return; // Shift+Enter 换行
          e.preventDefault();
          doSend();
        }
      });
      input.addEventListener("input", function () {
        autoGrow(input);
        if (!sending) setSendDisabled(false);
      });
    }

    if (modelSel) {
      modelSel.value = getModel();
      modelSel.addEventListener("change", function () {
        setModel(modelSel.value);
      });
    }

    if (attachBtn && fileInput) {
      attachBtn.addEventListener("click", function () { fileInput.click(); });
      fileInput.addEventListener("change", function () {
        for (var i = 0; i < (fileInput.files || []).length; i++) {
          attachments.push(fileInput.files[i]);
        }
        fileInput.value = "";
        renderAttachments();
        if (attachments.length) {
          setChatMsg("附件仅本地预览，不会随消息发送（服务端 /conversation 暂仅文本）", "ok");
        }
      });
    }

    // file:// 零 API 模式：隐藏登录区，提示需要 API
    var chatCard = document.getElementById("chat-card");
    if (!API_BASE) {
      if (chatCard) {
        chatCard.innerHTML =
          '<div class="chat-login"><div class="chat-login-card">' +
          '<h2 class="chat-title">CCC 对话</h2>' +
          '<p class="chat-login-sub">对话需要 HTTP API 模式：在 URL 加 ?api=http://host:port 参数，然后登录。</p>' +
          '</div></div>';
      }
      return;
    }

    // 已有 token → 直接进对话区
    if (getToken()) {
      showChat();
      setChatMsg("", "");
    } else {
      showLogin("", false);
    }
    if (sendBtn && input) setSendDisabled(true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChat);
  } else {
    initChat();
  }
})();
