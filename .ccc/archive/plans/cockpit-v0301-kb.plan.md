# Plan: cockpit-v0301-kb — Cockpit v0.30.1 知识库整合 + 服务告警

> 撰写：ccc-product | 执行：ccc-dev（manual）

---

## 当前代码状态

项目为单一 Python 文件 `scripts/ccc-cockpit.py`（~418 行）构成的 HTTP 服务器，零外部依赖。

- **入口/核心文件**：`scripts/ccc-cockpit.py` — 包含 HTTP 服务器、路由、HTML 模板、端口探测、`infrastructure.md` 解析
- **当前结构要点**：
  - 单页静态仪表盘，4 区：机器芯片 / 快速跳转 / 端口&服务表 / 项目表
  - **无 JavaScript**（全服务端渲染 HTML，页面刷新才更新数据）
  - 已有 `/api/alive` JSON 端点，但**前端未消费**（仅外部工具可用）
  - 项目状态仅从 `infrastructure.md` 静态表读取，**无实时探测**
  - 代码库中**无任何 HP 知识库调用**（`/memories` 仅出现在 plan/roadmap 文档）

- **待改动点**（全在 `ccc-cockpit.py` 一个文件内）：
  - P1: 新增 KB 搜索 UI 区域 + `/api/kb/search` 代理端点（→ `:8082/memories`）
  - P2: 前端新增 JS 轮询 `/api/alive` + 告警横幅渲染
  - P3: 项目表扩展为含动态关键指标列

---

## 范围

- **目标**：在 CCC Cockpit 中接入 HP 知识库搜索、服务自告警、项目关键指标
- **只改文件**：
  - `scripts/ccc-cockpit.py`（所有改动集中于此单文件）
- **不改文件**：
  - `.ccc/infrastructure.md`
  - `.ccc/state.md`、`.ccc/profile.md`
  - 其他任何脚本或模板文件
- **执行方式**：`manual`
- **Phase 数**：3

---

## 改动 1：P1 — HP 知识库搜索

### 做什么
在 Cockpit 页面新增「知识库搜索」区域，提供输入框和搜索结果列表。用户输入关键词后，前端向后端 `/api/kb/search?q=<关键词>` 发起请求，后端代理到 `http://127.0.0.1:8082/memories?query=<关键词>`，返回结果渲染为列表。

### 怎么做

**后端 — CockpitHandler 新增路由**：
- 在 `do_GET()`（约第 376 行附近）新增 `self.path == "/api/kb/search"` 处理：
  - `urllib.parse` 解析 `q` 参数
  - 向 `http://127.0.0.1:8082/memories?query=<关键词>` 发起 HTTP GET（3 秒超时）
  - 转发响应 JSON 到客户端（`Content-Type: application/json` + CORS header）
  - 超时/异常返回 `{"error": "KB search failed", "detail": "..."}`
  - 空 q 参数返回 `{"results": []}`

**前端 — `render_html()` 新增 KB 搜索区域**：
- 在 foot 区上方新增（约第 355 行）：
  - `sec-title` "知识库搜索"
  - 搜索输入框 `<input type="text" id="kb-query" placeholder="搜索关键词…">` + `<button onclick="kbSearch()">搜索</button>`
  - 搜索结果容器 `<div id="kb-results"></div>`
- 内联 JS 函数 `kbSearch()`：
  - `fetch(/api/kb/search?q=${encodeURIComponent(q)})` → 解析 JSON
  - 遍历 `results` 数组渲染列表项（标题 + 摘要 snippet + 链接）
  - 空结果 → 显示"未找到相关结果"
  - 错误 → 显示"搜索失败，请稍后重试"
  - 搜索中 → 显示"搜索中…"加载提示

### 验收清单

- [ ] 输入关键词后搜索结果以列表展示
- [ ] 无结果时显示"未找到相关结果"
- [ ] 后端超时/异常时显示"搜索失败"提示
- [ ] 搜索中显示加载提示
- [ ] `/api/kb/search` 返回正确 JSON 格式（含 `results` 或 `error` 字段）
- [ ] 代理到 `:8082/memories` 的请求携带正确的 `query` 参数

### 验收

- [输入关键词 → 结果列表]（参考：打开 cockpit，输入"CCC"，点搜索，观察结果区）
- [无结果提示]（参考：输入不存在关键词，看到"未找到相关结果"）
- [错误处理]（参考：停 `:8082` 后搜索，看到"搜索失败"）

---

## 改动 2：P2 — 服务告警横幅

### 做什么
Cockpit 页面顶部增加告警横幅区域，通过 JS 每 15 秒轮询 `/api/alive`，检测到有端口离线时显示红色横幅，标注离线服务和数量。服务恢复后横幅自动消失。点击横幅可折叠/展开详情。

### 怎么做

**前端 — `render_html()` 告警横幅**（在 `<div class="wrap">` 内部开头，约第 325 行）：
- `<div id="alert-banner" style="display:none">` — 初始隐藏
- 红色背景、白色文字、 图标
- 折叠态：一行文案 " N 个服务离线 — 点击查看详情"
- 展开态：详细列表（端口、服务名、主机、所属机器）

**前端 — 内联 JS 轮询**：
- `checkAlerts()`：fetch `/api/alive` → 遍历 `ports` 收集 `alive == false` 的端口
- 有离线 → 显示横幅；全部在线 → 隐藏横幅
- `setInterval(checkAlerts, 15000)`；首次加载立即执行一次
- 网络错误 → 保持上次状态，不抛错误

**交互逻辑**：
- 横幅绑定 `onclick` 切换折叠/展开状态
- 详情包含清晰表格视图

### 验收清单

- [ ] 所有端口在线时横幅不可见
- [ ] 有端口离线时顶部出现红色横幅
- [ ] 横幅显示离线数量和服务名
- [ ] 点击横幅可折叠/展开详情
- [ ] 离线服务恢复后横幅自动消失（下次轮询 15s 内）
- [ ] 轮询间隔 15s，不频繁

### 验收

- [离线告警]（参考：停一个端口服务 → cockpit 顶部出现红色横幅）
- [自动恢复]（参考：重启服务 → 横幅在下一轮轮询后消失）
- [折叠展开]（参考：点击横幅 → 折叠/展开详情）

---

## 改动 3：P3 — 项目关键指标

### 做什么
项目表格从静态三列（项目/版本/状态）扩展为包含动态关键指标。qb 实时 TCP 探活 `:8096`，medio-0 实时探活 `feiniu:3000`，xianyu 显示 pipeline 状态或"等待开发"。

### 怎么做

**后端 — `build_cockpit_data()` 追加项目探活**（约第 170-200 行）：
- 在并行探测端口后，增加一组项目探活探测（同样走 thread，2 秒超时）：
  - qb：TCP 探测 `192.168.3.140:8096` → 结果写入 project dict 的 `metric`
  - medio-0：HTTP 探测 `192.168.3.131:3000` → 200 为"运行中"，否则"离线"
  - xianyu：从 `infrastructure.md` 读取状态，当前无运行服务 → 显示"等待开发"
- 将探活结果挂在 project 的 `metric` 字段

**前端 — 项目表扩展**（`render_html()` 约第 264-280 行）：
- 表头新增「关键指标」列
- 每行第四列：
  - qb：探活结果（绿灯 + "运行中" / 红灯 + "离线"）
  - medio-0：探活结果（绿灯 + "已部署 / 运行中" / 红灯 + "离线"）
  - xianyu：静态 "等待开发"
  - 其他：`—`

**并行线程说明**：
- 使用已有线程池模式（参考 `build_cockpit_data()` 第 185-191 行），追加 2-3 个项目线程
- 线程超时 2 秒，不阻塞页面整体渲染

### 验收清单

- [ ] 项目表新增「关键指标」列
- [ ] qb 显示实时探活状态（对 `:8096` TCP 探测）
- [ ] medio-0 显示探活状态（对 `feiniu:3000` HTTP 探测）
- [ ] 离线时显示红色"离线"状态
- [ ] 线程超时 2s，不阻塞其他探测

### 验收

- [探活项目]（参考：观察 qb 和 medio-0 的关键指标是否实时更新，刷新页面后对比）
- [离线状态]（参考：停对应服务后刷新，指标变红）

---

## Commit 计划

| Phase | 改动 | Commit message 草稿 |
|-------|------|---------------------|
| 1 | P1 — 知识库搜索 | `feat(cockpit): HP 知识库搜索接入 (phase 1/3)` |
| 2 | P2 — 服务告警横幅 | `feat(cockpit): 服务告警横幅 + 自动轮询 (phase 2/3)` |
| 3 | P3 — 项目关键指标 | `feat(cockpit): 项目关键指标扩展 (phase 3/3)` |

规则：每个 phase 一个独立 commit，message 含 phase 编号。

---

## 全局验收清单

- [ ] Python 语法检查通过（参考：`python3 -m py_compile scripts/ccc-cockpit.py`）
- [ ] 重启 Cockpit 后页面正常展示，无 500 错误
- [ ] diff 范围仅限 `scripts/ccc-cockpit.py`
- [ ] 每个 phase 对应一个独立 commit
- [ ] phases.json 与 plan phase 数一致（3 个）
- [ ] Plan 中所有验收意图全部达成
- [ ] P1 不依赖 P2/P3，P2 不依赖 P3；可独立回退

---

## 后续步骤

P1-P3 完成后，Cockpit 从"静态仪表盘"进化为"半动态监控面板"。后续方向：

| 方向 | 说明 | 优先级 |
|------|------|--------|
| P4: 实时日志流 | WebSocket 订阅各服务日志 | 中 |
| P5: 历史趋势 | 端口在线率 / 响应时间曲线 | 低 |
| P6: 一键操作 | 从 Cockpit 重启离线服务 | 低 |