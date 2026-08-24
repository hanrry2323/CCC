# 运维页用户化改造 · 决策探查报告

> 探查日期：2026-08-11 · 探查范围：CCC `server/web/` 前端 + `server/engine/observer.py` 后端 + 可复用资产

---

## A. 运维页前端现状

### A1. opsPage.js 渲染结构（6 区块）

| 区块 | 行号 | 渲染内容 | 用户可读性 |
|------|------|----------|------------|
| 提示横幅 | 36 | `.orch-hint`：提示后端协议/端口 | 纯技术提示，用户不需要 |
| 工具栏 | 37-42 | 标题"运维" + 副标题"集群节点 + 服务概览" + 刷新按钮 | 勉强可读 |
| 状态概览 | 44-47 | `severity` 色块 + `human_line` 文本 + 可达节点数 + 中文状态（绿/琥珀/红） | **已有用户化雏形** |
| 集群节点 | 49-52 | 机器名/IP/角色/可达性 pill/端口数 | 机器视角，非用户视角 |
| Loop 巡查 | 54-57 | 报告名、发现数、转卡命令数、发现表格（权重/项目/标题/文件）、命令块 | 最接近"待办清单"，但用语偏技术 |
| 说明区 | 59-67 | 只读说明、后端集成、命令行操作指引 | 开发者文档，用户不需要 |

**关键发现**：`summarizeFinding()`（160-174 行）已做初步人话转换——把"项目 x 缺席 roadmap.md 的业务线路段落"转成"x 项目缺少路线图段落"。但转换不彻底（硬截断 40 字符）。

### A2. shell.css ops-* 样式族

| 类别 | 关键类名 | 行号 | 视觉 | 可复用 |
|------|----------|------|------|--------|
| 布局 | `.ops-grid-2` | 1049 | 双列响应式网格 |   |
| 卡片 | `.ops-card` | 1080 | 圆角、表面色背景 |   |
| 机器卡 | `.ops-machine` / `.up` / `.down` | 1065-1074 | 左边框色条（绿/红） |   |
| 徽标 | `.ops-pill` / `.ok` / `.bad` | 1146-1164 | 圆角 pill（绿/红） |   |
| 表格 | `.ops-table` | 1087 | 标准折叠表 |   |
| 命令块 | `.ops-cmd` | 1121 | 等宽可滚动终端块 |  需要改 |
| 空态 | `.ops-empty` | 1134 | 虚线边框占位 |   |
| 警告 | `.ops-attn` | 1227 | 橙色注意提示 |   |
| 折叠 | `.ops-fold` | 1246 | `<details>` 原生折叠 |   |
| 标签 | `.ops-red-tag` | 1015 | 圆角分类标签 |   |
| 芯片 | `.ops-chip` | 1237 | 等宽端口号标签 |   |

**结论**：CSS 基础设施充足，卡片/徽标/色块/折叠都有现成类，视觉重构不需要新写 CSS 框架。

### A3. 路由与导航（app.js 234-239 行）

- 路由 `#/ops` → 挂载到 `#view-ops`，与其他页面互斥（切换时 unmount 其他页）
- 导航栏 5 个入口：chat / board / plans / roadmap / ops
- 切换到 ops 页**不中断**后台 AI 流（T46 A1 合约）
- 15 秒自动轮询（`opsPage.js` 212 行）

### A4. 与其他页面差距分析

| 页面 | 用户化程度 | 核心模式 | 运维页差距 |
|------|-----------|----------|------------|
| Board | 高 | 看板列 + 状态徽标 + Toast 通知 | 有"去收卡"等行动号召 |
| Plans | 高 | 5 列管道 + 进度条 + Markdown 渲染 | 有验收进度可视化 |
| Roadmap | 中 | 画廊 + iframe 架构图 | 有时间线色标 |
| **Ops** | 低 | 静态 KV 行 + 表格 + 命令块 | 纯技术日志，无行动引导 |

**差距根因**：
1. 运维页定位为"只读诊断面板"，禁止写操作，缺乏交互动力
2. 目标用户是基础设施工程师而非项目管理者
3. 功能上只是 Observer 守护进程的输出展示器

### A5. opsRed.js 聚合逻辑

纯函数模块，无 DOM 依赖。按域聚合告警：
- **端口域**：7788/6100/6102 为关键端口，down 则 high
- **机器域**：不可达 → high
- **部署域**：目标不可达 → high，端口检查失败 → warn
- **工作区域**：异常计数 > 0 → high
- **引擎/Relay 域**：引擎停 → high，relay 不可达 → warn（fail-open）

**已有用户可读输出**：`push('ports', 'high', `端口 ${p.port} 未响应`, ...)` 等。可直接用于告警摘要卡。

---

## B. 运维数据源

### B1. GET /ops/summary（server.py 623-740 行）

```json
{
  "overview": { "machines": [...], "alert_count": 0, "down_ports": [], "generated_at": "..." },
  "severity": "green",          // ← 用户结论（现成）
  "human_line": "集群全活（1/1 节点可达） · 服务 1/1 运行",  // ← 用户结论（现成）
  "pipeline": { "git_sync_ok": true, "probe_skips": 0, ... },
  "risks": null, "workspaces": null, ...  // 兼容保留字段，全为 null
}
```

**字段分类**：
- **用户结论**：`severity`（绿/琥珀/红）、`human_line`（一句话摘要）
- **机器明细**：`overview.machines`（节点列表）、`overview.down_ports`（不可达端口）
- **引擎元数据**：`pipeline`（git 同步、探测跳过）
- **兼容占位**：`risks` ~ `agent_minds` 共 20 个 null 字段

### B2. GET /loop/findings（server.py 2024-2077 行）

```json
{
  "loop_reports": [{
    "name": "2026-08-11-ccc-patrol",
    "findings": [{
      "weight": "4.00",           // → 优先级标签
      "title": "项目 qa 缺席...",  // → 发现描述
      "project": "qa",            // → 涉及项目
      "acting_on": "docs/roadmap.md",  // → 涉及文件
      "evidence": "docs/roadmap.md:1"  // → 技术证据（折叠）
    }],
    "commands": ["scripts/new-card.sh ..."]  // → 转卡命令
  }]
}
```

**字段 → 用户视角映射**：
| 机器字段 | 用户含义 | 呈现方式 |
|----------|----------|----------|
| `weight` | 优先级 | 标签：P1(≥4) / P2(2-3) / P3(<2) |
| `title` | 问题描述 | 人话摘要（已有 summarizeFinding） |
| `project` | 涉及项目 | 项目徽标 |
| `acting_on` | 涉及文件 | 可点击路径 |
| `evidence` | 技术证据 | 折叠详情 |
| `commands` | 修复命令 | 按钮"一键转卡"（替代复制粘贴） |

### B3. observer.py scan_findings 4 类发现（168-324 行）

| 类型 | 当前机器输出 | 用户人话 |
|------|-------------|----------|
| `missing_section` | "项目 {prefix} 缺席 roadmap.md 的业务线路段落" | "{prefix} 项目还没写路线图" |
| `drift` | "任务卡 {card_id} 状态漂移：roadmap.md 标注「X」，但看板/卡文件实际状态为「Y」" | "{card_id} 路线图状态和实际看板不一致" |
| `broken_link` | "方案 {plan_id} 已完成，但其关联卡未全部关闭" / "关联了不存在的任务卡" | "方案 {plan_id} 关联卡异常" |
| `missing_four_questions` | "已关闭任务卡 {card_id} 缺失或未完成维护区四问" | "{card_id} 维护区四问未填写" |

**后端已自带人话方向**：`summarizeFinding()` 在前端做了初步转换，但更彻底的做法是在 observer.py 生成 `title` 时就输出人话版本（或加 `human_title` 字段）。

### B4. 角色分类：明确的两层

```
┌────────────────────────────────────────────┐
│  Zone A: 健康仪表盘（/ops/summary）          │
│  severity: green · 3/3 节点 · 4/4 服务      │
│  实时状态，只读，系统级监控                    │
├────────────────────────────────────────────┤
│  Zone B: 待办清单（/loop/findings）           │
│  [P1] qa 项目缺少路线图段落                  │
│  [P2] ccc032 维护区四问未填写                │
│  可操作，需人工决策（adopt/reject）           │
├────────────────────────────────────────────┤
│  Zone C: 技术详情（折叠）                     │
│  机器列表 / 端口状态 / 原始命令 / 证据路径     │
└────────────────────────────────────────────┘
```

**结论**：数据天然支持三层架构，不需要后端改动。

---

## C. 现有可复用资产

### C1. CSS 组件库（直接复用）

| 组件 | 现成类 | 用途 |
|------|--------|------|
| 状态卡片 | `.ops-card` | 健康仪表盘容器 |
| 节点卡片 | `.ops-machine` + `.up`/`.down` | 集群节点（折叠区） |
| 状态 Pill | `.ops-pill` + `.ok`/`.bad` | 在线/离线/绿/琥珀/红 |
| 分类标签 | `.ops-red-tag` | 发现类型分类 |
| 端口芯片 | `.ops-chip` | 等宽端口号 |
| 折叠区 | `.ops-fold` | 技术详情 |
| 空态 | `.ops-empty` | 无发现/无报告 |
| 警告条 | `.ops-attn` | 异常提示 |
| 双列网格 | `.ops-grid-2` | 仪表盘 + 待办并排 |
| 按钮 | `.hub-btn` + `.primary` | 刷新/转卡 |
| 脉冲动画 | `.board-card.running` | 活跃脚本指示器 |

### C2. 可借鉴的文案模式

| 来源 | 模式 | 示例 |
|------|------|------|
| BoardPage | 状态→中文映射 | `classifyWsStatus()`：打回→"需人工介入"、执行中→"执行中" |
| PlansPage | 管道色标 | 草案灰/已确认绿/部分执行金/已完成蓝/作废红 |
| PlansPage | 进度条 | 验收进度 `done/total` + 百分比填充 |
| RoadmapPage | 状态色 | active 绿 / frozen 蓝 / retired 灰 |
| opsRed.js | 告警摘要 | `端口 7788 未响应 (主 Hub)` — 直接可用 |

### C3. 共享组件函数

| 文件 | 函数 | 用途 |
|------|------|------|
| `js/components/taskCard.js` | `renderTaskCard()` | 任务卡渲染（状态徽标/计时器） |
| `js/utils.js` | `escapeHtml()` | 安全注入 |
| `js/utils.js` | `relativeTime()` | 人性化时间（"今天 14:32"） |
| `js/utils.js` | `debounce()` | 搜索防抖 |

---

## D. 决策路径

### D1. 信息架构：三层改造方案（推荐）

```
┌──────────────────────────────────────────────┐
│  运维概览                                      │
│  ┌─────────────────────────────────────────┐  │
│  │  健康仪表盘                               │  │
│  │   集群全活  ·  服务正常  ·  昨日同步 OK    │  │
│  │  [3 节点在线] [4 服务运行] [Git 同步正常]   │  │
│  └─────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────┐  │
│  │  待办清单（3 项待处理）                     │  │
│  │  [P1] qa 项目还没写路线图        [转卡]    │  │
│  │  [P2] ccc032 维护区四问未填写    [转卡]    │  │
│  │  [P3] relay 节点偶尔不可达      [忽略]    │  │
│  └─────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────┐  │
│  │  技术详情 ▸                               │  │
│  │  （折叠：机器列表 / 端口 / 原始命令 / 证据） │  │
│  └─────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

**可行性**：数据源完全够。`severity` + `human_line` → 仪表盘，`findings` → 待办清单，`overview.machines` + `pipeline` → 折叠详情。

### D2. 机器字段 → 用户字段映射表

| 源字段 | 源位置 | 用户字段 | 呈现组件 | 优先级规则 |
|--------|--------|----------|----------|------------|
| `severity` | /ops/summary | 健康状态 | 大色块 pill | green=绿, amber=琥珀, red=红 |
| `human_line` | /ops/summary | 一句话摘要 | 副标题文本 | 直接展示 |
| `overview.machines[].reachable` | /ops/summary | 节点在线/离线 | `.ops-machine.up`/`.down` | 折叠区 |
| `overview.alert_count` | /ops/summary | 告警数 | 红色角标 | >0 显示 |
| `pipeline.git_sync_ok` | /ops/summary | Git 同步 | 图标 + "正常"/"异常" | 折叠区 |
| `findings[].weight` | /loop/findings | 优先级标签 | 色标 pill | ≥4=P1(红), 2-3=P2(橙), <2=P3(蓝) |
| `findings[].title` | /loop/findings | 问题描述 | 人话摘要 | summarizeFinding() |
| `findings[].project` | /loop/findings | 涉及项目 | 项目徽标 | — |
| `findings[].acting_on` | /loop/findings | 涉及文件 | 可点击路径 | — |
| `findings[].evidence` | /loop/findings | 技术证据 | 折叠行 | 折叠区 |
| `findings[].commands` | /loop/findings | 操作按钮 | `.hub-btn.primary` "转卡" | — |

### D3. 新页面组件清单

| 组件 | 用现成类 | 需新写 | 说明 |
|------|----------|--------|------|
| 健康仪表盘卡片 | `.ops-card` | — | 直接复用 |
| 健康状态 Pill | `.ops-pill.ok` | — | 改色变量 |
| 待办清单列表 | — | `.ops-todo-list` | 新写，约 20 行 CSS |
| 待办项行 | — | `.ops-todo-item` | 新写，左色条 + 项目徽标 + 标题 + 按钮 |
| 优先级标签 | — | `.ops-priority.p1/.p2/.p3` | 新写，三色变体 |
| 操作按钮 | `.hub-btn.primary` | — | 直接复用 |
| 折叠详情 | `.ops-fold` | — | 直接复用 |
| 节点卡片 | `.ops-machine.up/.down` | — | 直接复用 |
| 空态 | `.ops-empty` | — | 直接复用 |

**新写量估算**：约 50-80 行 CSS + 重构 `opsPage.js` 渲染函数（约 200 行 JS）。

### D4. 后端要补什么

| 需求 | 当前状态 | 建议 |
|------|----------|------|
| 用户结论 | `severity` + `human_line` 已有 | **不需要改** |
| 发现人话标题 | `summarizeFinding()` 前端转换 | 短期：前端继续做；长期：observer.py 加 `human_title` 字段 |
| 发现归纳（如"共 3 类问题"） | 前端可算 | **不需要后端改**，前端聚合 |
| 转卡一键触发 | 当前只返回命令文本 | 前端做成按钮，调用 `POST /loop/adopt`（已有端点） |
| 健康趋势（历史对比） | 无 | 可选：后续版本加 `/ops/summary?history=7d` |

**结论**：纯前端重构即可完成三层改造，后端零改动。

### D5. 改动范围评估

| 方案 | 改动文件 | 风险 | 工期 |
|------|----------|------|------|
| **纯前端重构（推荐）** | `opsPage.js`（重写渲染）+ `shell.css`（加 50-80 行） | 低：只改前端渲染，不影响数据流 | 半天 |
| 前端 + 后端优化 | 上述 + `observer.py`（加 `human_title`）+ `server.py`（加归纳字段） | 中：observer 是核心引擎 | 1-2 天 |

**推荐纯前端重构**：
- 数据源字段已足够
- `summarizeFinding()` 在前端做人话转换即可
- `/loop/adopt` 端点已存在，前端加按钮调用即可
- 风险最低：不改后端核心引擎，只改展示层

---

## 附录：关键文件索引

| 文件 | 行号 | 内容 |
|------|------|------|
| `server/web/legacy-chat/js/pages/opsPage.js` | 1-218 | 运维页全量渲染 |
| `server/web/legacy-chat/js/pages/opsPage.js` | 160-174 | summarizeFinding 人话转换 |
| `server/web/legacy-chat/js/opsRed.js` | 1-85 | 告警聚合逻辑 |
| `server/web/legacy-chat/css/shell.css` | 933-1252 | ops-* 样式族 |
| `server/web/legacy-chat/js/app.js` | 234-239 | #/ops 路由 |
| `server/web/server.py` | 623-740 | _build_ops_summary |
| `server/web/server.py` | 1964-1982 | _handle_ops_summary |
| `server/web/server.py` | 2024-2077 | _handle_loop_findings |
| `server/web/server.py` | 2079-2123 | _handle_loop_adopt |
| `server/engine/observer.py` | 168-324 | scan_findings 4 类发现 |
| `server/web/legacy-chat/js/pages/boardPage.js` | 264-284 | classifyWsStatus 状态→人话 |
| `server/web/legacy-chat/js/pages/plansPage.js` | 18-43 | 管道色标系统 |
| `server/web/legacy-chat/js/pages/roadmapPage.js` | 15-19 | 状态色标 |
| `server/web/legacy-chat/js/components/taskCard.js` | 1-31 | STATE_COLORS 状态映射 |
| `server/web/legacy-chat/js/utils.js` | 1-82 | escapeHtml / relativeTime / debounce |