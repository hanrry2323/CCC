/* CCC 看板 —— 渲染数据（支持本地 board.js / HTTP API 两种来源，API 不可用时回退本地数据）。 */
(function () {
  "use strict";

  var DATA = window.BOARD_DATA || { states: {}, views: {}, roadmap: [] };
  var CLUSTER = window.CLUSTER_DATA || { nodes: [], services: [], collected_at: "" };
  var API_BASE = window.API_BASE_URL || null;
  // T16 起 board 接口需 Bearer token：由 URL `?token=` 参数注入，无则 401 回退本地
  var API_HEADERS = {};
  if (window.BOARD_TOKEN) {
    API_HEADERS["Authorization"] = "Bearer " + window.BOARD_TOKEN;
  }
  var TONES = { 待分派: "amber", 执行中: "cyan", 已回写: "violet", 已关闭: "emerald", 打回: "rose" };
  var STATUS_TONES = { 正常: "emerald", 异常: "rose", 未知: "faint" };

  // HTTP API 模式：构造 BOARD_DATA 结构
  function fetchApiData() {
    if (!API_BASE) return Promise.resolve(null);
    var base = API_BASE.replace(/\/+$/, "");
    return Promise.all([
      fetch(base + "/board/realtime", { headers: API_HEADERS }).then(function (r) { return r.ok ? r.json() : null; }),
      fetch(base + "/board/recent", { headers: API_HEADERS }).then(function (r) { return r.ok ? r.json() : null; }),
      fetch(base + "/board/by_project", { headers: API_HEADERS }).then(function (r) { return r.ok ? r.json() : null; }),
      fetch(base + "/board/roadmap", { headers: API_HEADERS }).then(function (r) { return r.ok ? r.json() : null; }),
      fetch(base + "/board/states", { headers: API_HEADERS }).then(function (r) { return r.ok ? r.json() : null; }),
    ]).then(function (results) {
      return {
        source: "HTTP API",
        views: {
          realtime: results[0] || {},
          recent: results[1] || [],
          by_project: results[2] || [],
        },
        roadmap: results[3] || { overview: [], by_project: [] },
        states: results[4] || {},
      };
    }).catch(function () {
      console.warn("[web] HTTP API 不可用，回退本地数据");
      return null;
    });
  }

  // 数据就绪后渲染
  function render(data) {
    if (!data) return;
    DATA = data;
    renderBadge();
    renderRealtime();
    renderRecent();
    renderByProject();
    renderRoadmap();
    renderCluster();
  }

  // 入口：API 模式优先，回退本地
  if (API_BASE) {
    var ds = document.getElementById("data-source");
    if (ds) ds.textContent = "HTTP API: " + API_BASE;
    fetchApiData().then(function (apiData) {
      render(apiData || DATA);
    });
  }

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

  /* ── 线路图三层派生视图 ── */

  var ROADMAP = DATA.roadmap || { overview: [], by_project: [], project_detail: {} };
  var BUCKET_TONES = { 未开发: "faint", 开发中: "cyan", 已开发待验收: "violet", 已验收待确认: "faint", 确认可用: "emerald", 有问题: "rose" };

  function renderBucketGrid(buckets, onClick) {
    var grid = el("div", "roadmap");
    buckets.forEach(function (b) {
      var node = el("div", "step");
      if (onClick) {
        node.style.cursor = "pointer";
        node.addEventListener("click", function () { onClick(b); });
      }
      node.appendChild(el("div", "num", String(b.count)));
      node.appendChild(el("div", "name", b.bucket));
      grid.appendChild(node);
    });
    return grid;
  }

  function renderRoadmapL1() {
    var box = document.getElementById("view-roadmap");
    if (!box) return;

    // 总览桶
    var overview = ROADMAP.overview || [];
    var card1 = el("div", "card");
    card1.appendChild(el("h3", null, "线路图总览"));
    card1.appendChild(renderBucketGrid(overview));
    box.appendChild(card1);

    // 项目列表
    var projects = ROADMAP.by_project || [];
    if (!projects.length) {
      box.appendChild(el("div", "empty", "暂无项目数据"));
      return;
    }
    var card2 = el("div", "card");
    card2.appendChild(el("h3", null, "项目"));
    projects.forEach(function (row) {
      var projCard = el("div", "project-card");
      projCard.style.cursor = "pointer";
      projCard.addEventListener("click", function () { showRoadmapL2(row.project); });
      projCard.appendChild(el("div", "project-name", row.project + "（" + row.count + "）"));
      var chips = el("div", "chip-row");
      (row.buckets || []).forEach(function (b) {
        if (b.count > 0) chips.appendChild(chip(b.bucket + " " + b.count, BUCKET_TONES[b.bucket]));
      });
      projCard.appendChild(chips);
      card2.appendChild(projCard);
    });
    box.appendChild(card2);
  }

  function showRoadmapL2(project) {
    var box = document.getElementById("view-roadmap");
    if (!box) return;
    box.innerHTML = "";

    var nav = el("div", "roadmap-nav");
    var backBtn = el("button", "hub-btn", "← 总览");
    backBtn.addEventListener("click", function () { box.innerHTML = ""; renderRoadmapL1(); });
    nav.appendChild(backBtn);
    nav.appendChild(el("span", "roadmap-title", project));
    box.appendChild(nav);

    var projData = null;
    (ROADMAP.by_project || []).forEach(function (r) {
      if (r.project === project) projData = r;
    });
    if (!projData) {
      box.appendChild(el("div", "empty", "项目数据不存在"));
      return;
    }

    var card = el("div", "card");
    card.appendChild(el("h3", null, "线路图 · " + project));
    card.appendChild(renderBucketGrid(projData.buckets, function (bucket) {
      showRoadmapL3(project, bucket.bucket);
    }));
    box.appendChild(card);
  }

  function showRoadmapL3(project, bucketName) {
    var box = document.getElementById("view-roadmap");
    if (!box) return;
    box.innerHTML = "";

    var nav = el("div", "roadmap-nav");
    var backBtn = el("button", "hub-btn", "← 项目");
    backBtn.addEventListener("click", function () { box.innerHTML = ""; showRoadmapL2(project); });
    nav.appendChild(backBtn);
    nav.appendChild(el("span", "roadmap-title", project + " · " + bucketName));
    box.appendChild(nav);

    var detail = (ROADMAP.project_detail || {})[project] || [];
    var bucketData = null;
    detail.forEach(function (b) {
      if (b.bucket === bucketName) bucketData = b;
    });
    if (!bucketData || !bucketData.items.length) {
      box.appendChild(el("div", "empty", bucketName + "桶为空"));
      return;
    }

    var card = el("div", "card");
    card.appendChild(el("h3", null, bucketName + "（" + bucketData.items.length + "）"));
    var rows = el("div", "grid");
    bucketData.items.forEach(function (it) {
      var itemCard = el("div", "card");
      itemCard.appendChild(el("h3", null, it.id + " · " + (it.title || "—")));
      var meta = el("p", "meta");
      meta.appendChild(chip("状态 " + it.state, TONES[it.state]));
      meta.appendChild(document.createTextNode(" 执行体 " + it.executor));
      if (it.written_at && it.written_at !== "未知") {
        meta.appendChild(document.createTextNode(" · 回写 " + it.written_at));
      }
      if (it.reject_count > 0) {
        meta.appendChild(chip("打回 " + it.reject_count, "rose"));
      }
      itemCard.appendChild(meta);
      // 「确认可用」唯一人工动作占位
      if (bucketName === "确认可用") {
        var btn = el("button", "hub-btn confirm-btn", "确认可用");
        btn.disabled = true;
        btn.title = "预留——确认可用为唯一人工动作";
        itemCard.appendChild(btn);
      }
      rows.appendChild(itemCard);
    });
    card.appendChild(rows);
    box.appendChild(card);
  }

  function renderRoadmap() {
    renderRoadmapL1();
  }

  function renderCluster() {
    var box = document.getElementById("view-cluster");
    if (!box) return;
    var data = CLUSTER;
    if (!data.nodes || !data.services) {
      box.appendChild(el("div", "empty", "暂无集群数据（运行 scheduler 采集后生成）"));
      return;
    }
    // 采集时间
    var info = el("div", "card");
    info.appendChild(el("h3", null, "集群状态概览"));
    var meta = el("p", "meta");
    meta.appendChild(document.createTextNode("采集时间: " + (data.collected_at || "—")));
    meta.appendChild(document.createTextNode(" · 节点 " + (data.nodes.length || 0) + " · 服务 " + (data.services.length || 0)));
    info.appendChild(meta);
    box.appendChild(info);

    // 节点状态
    if (data.nodes.length) {
      var nodeCard = el("div", "card");
      nodeCard.appendChild(el("h3", null, "节点可达性"));
      var grid = el("div", "grid-3");
      data.nodes.forEach(function (n) {
        var item = el("div", "step");
        var status = n.reachable ? "正常" : "异常";
        var tone = STATUS_TONES[status] || "faint";
        item.appendChild(el("div", "chip " + tone, status));
        item.appendChild(el("div", "name", n.host + ":" + n.port));
        if (n.latency_ms !== null && n.latency_ms !== undefined) {
          item.appendChild(el("div", "meta", n.latency_ms + "ms"));
        }
        if (n.error) {
          item.appendChild(el("div", "meta", n.error));
        }
        grid.appendChild(item);
      });
      nodeCard.appendChild(grid);
      box.appendChild(nodeCard);
    }

    // 服务状态
    if (data.services.length) {
      var svcCard = el("div", "card");
      svcCard.appendChild(el("h3", null, "服务进程状态"));
      var svg = el("div", "grid-3");
      data.services.forEach(function (s) {
        var item = el("div", "step");
        var status = s.running ? "正常" : "异常";
        var tone = STATUS_TONES[status] || "faint";
        item.appendChild(el("div", "chip " + tone, status));
        item.appendChild(el("div", "name", s.name));
        if (s.pid) {
          item.appendChild(el("div", "meta", "PID " + s.pid));
        }
        if (s.error) {
          item.appendChild(el("div", "meta", s.error));
        }
        svg.appendChild(item);
      });
      svcCard.appendChild(svg);
      box.appendChild(svcCard);
    }
  }

  function renderOps() {
    var box = document.getElementById("view-ops");
    if (!box) return;
    var data = CLUSTER;

    // 运维概览
    var card = el("div", "card");
    card.appendChild(el("h3", null, "运维概览"));
    var meta = el("p", "meta");
    var reachable = 0;
    if (data.nodes) {
      data.nodes.forEach(function (n) { if (n.reachable) reachable++; });
    }
    var running = 0;
    if (data.services) {
      data.services.forEach(function (s) { if (s.running) running++; });
    }
    meta.appendChild(document.createTextNode("节点可达: " + reachable + "/" + (data.nodes ? data.nodes.length : 0)));
    meta.appendChild(document.createTextNode(" · 服务运行: " + running + "/" + (data.services ? data.services.length : 0)));
    meta.appendChild(document.createTextNode(" · 采集: " + (data.collected_at || "—")));
    card.appendChild(meta);
    box.appendChild(card);

    // 定时任务状态
    var cfg = data.config || {};
    var taskCard = el("div", "card");
    taskCard.appendChild(el("h3", null, "定时任务"));
    taskCard.appendChild(el("p", "meta", "集群采集（readonly）: 每 " + (cfg.scheduler_interval || "60") + " 秒执行一次"));
    taskCard.appendChild(el("p", "meta", "变更类: " + (cfg.scheduler_dispatch_dir ? "已启用" : "未配置（SCHEDULER_DISPATCH_DIR 为空）")));
    box.appendChild(taskCard);

    // 系统信息
    var sysCard = el("div", "card");
    sysCard.appendChild(el("h3", null, "系统信息"));
    sysCard.appendChild(el("p", "meta", "数据目录: " + (cfg.data_dir || "—")));
    sysCard.appendChild(el("p", "meta", "看板服务端口: " + (cfg.board_port || "—")));
    sysCard.appendChild(el("p", "meta", "Web 服务端口: " + (cfg.web_port || "—")));
    box.appendChild(sysCard);
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

  // 本地模式（无 API_BASE）：直接渲染 window.BOARD_DATA
  if (!API_BASE) {
    renderBadge();
    renderRealtime();
    renderRecent();
    renderProject();
    renderRoadmap();
    renderCluster();
    renderOps();
  }
  initTabs();
  initTheme();
})();
