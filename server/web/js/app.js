/* CCC 看板 —— 静态渲染 window.BOARD_DATA（零 fetch / 零 API）。 */
(function () {
  "use strict";

  var DATA = window.BOARD_DATA || { states: {}, views: {}, roadmap: [] };
  var TONES = { 待分派: "amber", 执行中: "cyan", 已回写: "violet", 已关闭: "emerald", 打回: "rose" };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function chip(text, tone) {
    return el("span", "chip " + (tone || "faint"), text);
  }

  function itemCard(item) {
    var card = el("div", "card");
    var h = el("h3", null, item.id + " · " + (item.title || "—"));
    var meta = el("p", "meta");
    meta.appendChild(chip("状态 " + item.state, TONES[item.state]));
    meta.appendChild(document.createTextNode(" 项目 " + item.project + " · 执行体 " + item.executor));
    if (item.dispatched_at && item.dispatched_at !== "未知") {
      meta.appendChild(document.createTextNode(" · 分派 " + item.dispatched_at));
    }
    if (item.written_at && item.written_at !== "未知") {
      meta.appendChild(document.createTextNode(" · 回写 " + item.written_at));
    }
    if (item.reject_count > 0) {
      meta.appendChild(chip("打回 " + item.reject_count, "rose"));
    }
    card.appendChild(h);
    card.appendChild(meta);
    return card;
  }

  function renderBadge() {
    var box = document.getElementById("status-badge");
    if (!box) return;
    var states = DATA.states || {};
    var names = ["待分派", "执行中", "已回写", "已关闭", "打回"];
    names.forEach(function (name) {
      var n = states[name] || 0;
      var c = el("span", "chip " + (TONES[name] || "faint"));
      c.appendChild(el("strong", null, n));
      c.appendChild(document.createTextNode(name));
      box.appendChild(c);
    });
  }

  function renderRealtime() {
    var box = document.getElementById("view-realtime");
    if (!box) return;
    var views = DATA.views.realtime || {};
    var keys = Object.keys(views);
    if (!keys.length) {
      box.appendChild(el("div", "empty", "暂无任务卡数据"));
      return;
    }
    keys.forEach(function (state) {
      var items = views[state] || [];
      var card = el("div", "card");
      var h = el("h3", null, state + "（" + items.length + "）");
      var rows = el("div", "grid");
      items.forEach(function (it) { rows.appendChild(itemCard(it)); });
      card.appendChild(h);
      card.appendChild(rows);
      box.appendChild(card);
    });
  }

  function renderRecent() {
    var box = document.getElementById("view-recent");
    if (!box) return;
    var list = DATA.views.recent || [];
    if (!list.length) {
      box.appendChild(el("div", "empty", "近 7 天无回写记录"));
      return;
    }
    var card = el("div", "card");
    card.appendChild(el("h3", null, "近 7 天回写（" + list.length + "）"));
    var rows = el("div", "grid");
    list.forEach(function (it) { rows.appendChild(itemCard(it)); });
    card.appendChild(rows);
    box.appendChild(card);
  }

  function renderProject() {
    var box = document.getElementById("view-project");
    if (!box) return;
    var rows = DATA.views.by_project || [];
    if (!rows.length) {
      box.appendChild(el("div", "empty", "暂无项目数据"));
      return;
    }
    rows.forEach(function (row) {
      var card = el("div", "card");
      card.appendChild(el("h3", null, row.project + "（" + row.count + "）"));
      var chips = el("div", "chip-row");
      Object.keys(row.states || {}).forEach(function (name) {
        var n = row.states[name];
        if (n > 0) chips.appendChild(chip(name + " " + n, TONES[name]));
      });
      card.appendChild(chips);
      box.appendChild(card);
    });
  }

  function renderRoadmap() {
    var box = document.getElementById("view-roadmap");
    if (!box) return;
    var steps = DATA.roadmap || [];
    var grid = el("div", "roadmap");
    steps.forEach(function (step) {
      var node = el("div", "step");
      node.appendChild(el("div", "num", String(step.count)));
      node.appendChild(el("div", "name", step.bucket));
      grid.appendChild(node);
    });
    var card = el("div", "card");
    card.appendChild(el("h3", null, "线路图状态聚合（P3 占位）"));
    card.appendChild(grid);
    box.appendChild(card);
  }

  function initTabs() {
    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
        document.querySelectorAll(".view").forEach(function (v) { v.classList.remove("active"); });
        tab.classList.add("active");
        var view = document.getElementById("view-" + tab.dataset.view);
        if (view) view.classList.add("active");
      });
    });
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("ccc-board-theme"); } catch (e) { /* file:// 可能禁用 */ }
    if (saved === "light" || saved === "dark") {
      document.documentElement.dataset.theme = saved;
    }
    var toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem("ccc-board-theme", next); } catch (e) { /* 忽略 */ }
      });
    }
  }

  renderBadge();
  renderRealtime();
  renderRecent();
  renderProject();
  renderRoadmap();
  initTabs();
  initTheme();
})();
