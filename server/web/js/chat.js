/* CCC 看板 · 对话视图 —— 登录（账号密码换 token）+ 对话（POST /conversation）。
 * 仅在 HTTP API 模式（?api=...）下生效；file:// 零 API 模式不显示对话。 */
(function () {
  "use strict";

  var API_BASE = window.API_BASE_URL || null;
  // token 来源优先级：localStorage > URL ?token=
  function getToken() {
    try {
      var t = localStorage.getItem("ccc-chat-token");
      if (t) return t;
    } catch (e) { /* file:// 可能禁用 localStorage */ }
    return window.BOARD_TOKEN || null;
  }
  function setToken(t) {
    try { localStorage.setItem("ccc-chat-token", t); } catch (e) {}
  }
  function clearToken() {
    try { localStorage.removeItem("ccc-chat-token"); } catch (e) {}
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  function showLogin(msg) {
    document.getElementById("login-area").style.display = "";
    document.getElementById("chat-area").style.display = "none";
    if (msg) {
      var m = document.getElementById("login-msg");
      m.textContent = msg;
    }
  }
  function showChat() {
    document.getElementById("login-area").style.display = "none";
    document.getElementById("chat-area").style.display = "";
  }

  function renderMessage(role, text) {
    var box = document.getElementById("chat-messages");
    var row = el("div", "chat-msg chat-msg-" + role);
    row.appendChild(el("span", "chat-role", role === "user" ? "我" : "Agent"));
    row.appendChild(el("div", "chat-text", text));
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
  }

  function setChatMsg(text) {
    document.getElementById("chat-msg").textContent = text || "";
  }

  // 登录：POST /session
  function doLogin() {
    if (!API_BASE) {
      showLogin("对话需要 HTTP API 模式：在 URL 加 ?api=http://host:port");
      return;
    }
    var user = document.getElementById("login-user").value.trim();
    var pass = document.getElementById("login-pass").value;
    if (!user || !pass) {
      showLogin("请填写账号和密码");
      return;
    }
    setChatMsg("登录中…");
    fetch(API_BASE.replace(/\/+$/, "") + "/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pass })
    }).then(function (r) {
      return r.json().then(function (d) { return { status: r.status, data: d }; });
    }).then(function (res) {
      if (res.status === 200 && res.data.token) {
        setToken(res.data.token);
        showChat();
        setChatMsg("登录成功，token 有效期 " + (res.data.ttl_s || 0) + " 秒");
        // 刷新看板数据用 token
        window.BOARD_TOKEN = res.data.token;
      } else {
        showLogin("登录失败：" + (res.data.error || res.status));
      }
    }).catch(function (e) {
      showLogin("登录请求失败：" + e);
    });
  }

  // 对话：POST /conversation
  function doSend() {
    var input = document.getElementById("chat-input");
    var text = input.value.trim();
    if (!text) return;
    var token = getToken();
    if (!token) {
      showLogin("token 已过期，请重新登录");
      return;
    }
    renderMessage("user", text);
    input.value = "";
    setChatMsg("生成中…");
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
      if (res.status === 200 && res.data.reply) {
        renderMessage("assistant", res.data.reply);
        setChatMsg("");
      } else if (res.status === 401) {
        clearToken();
        showLogin("会话已过期（401），请重新登录");
      } else if (res.status === 503) {
        setChatMsg("服务端未配置对话上游（503）：" + (res.data.error || ""));
      } else if (res.status === 502) {
        setChatMsg("上游调用失败（502）：" + (res.data.error || ""));
      } else {
        setChatMsg("对话失败：" + (res.data.error || res.status));
      }
    }).catch(function (e) {
      setChatMsg("请求失败：" + e);
    });
  }

  // 初始化（仅 HTTP API 模式）
  function initChat() {
    var loginBtn = document.getElementById("login-btn");
    var sendBtn = document.getElementById("chat-send");
    var input = document.getElementById("chat-input");
    if (loginBtn) loginBtn.addEventListener("click", doLogin);
    if (sendBtn) sendBtn.addEventListener("click", doSend);
    if (input) {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") doSend();
      });
    }
    // file:// 零 API 模式：隐藏登录区，提示需要 API
    var chatCard = document.getElementById("chat-card");
    if (!API_BASE) {
      if (chatCard) {
        chatCard.innerHTML = '<h3>对话</h3><p class="meta">对话需要 HTTP API 模式：在 URL 加 ?api=http://host:port 参数，然后登录。</p>';
      }
      return;
    }
    // 已有 token → 直接进对话区
    if (getToken()) {
      showChat();
    } else {
      showLogin("");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initChat);
  } else {
    initChat();
  }
})();
