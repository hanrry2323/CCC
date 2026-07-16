# CCC 完整介绍 — Connect–Claude Code · Loop Engineer

> **对外完整介绍稿**（比 README 更全面）。定位 SSOT 仍是 [`VISION.md`](VISION.md)。  
> 操作分镜：[`INTRO-WALKTHROUGH.md`](INTRO-WALKTHROUGH.md) · 视频脚本：[`releases/intro-video-script.md`](releases/intro-video-script.md)  
> 竖切样板：[`vertical-qx.md`](vertical-qx.md)

---

## English (short)

**CCC (Connect–Claude Code)** is a **Loop Engineer**: set intent in the self-built **Hub**, then the system orchestrates, executes, verifies, retries, and can evolve.  
Roles are not a fixed menu — **task → tool routing → Skill + Prompt = role** (unlimited).  
Vertical industries plug in domain assets (crawlers, DB, workers, domain skills) + custom quick actions on the same base.

---

## 1. 一句话与痛点

**CCC 是一台 Loop Engineer：人用最短路径定意图，系统自动编排、自主执行、验收纠错，并持续进化。**

常见现实：

- 有大模型、有脚本、有数据库、有 worker —— **缺一个可靠的调度与人机交接层**  
- 用第三方 Agent IDE /「角色超市」编排：用户要选角色、背 Skill，管理成本爆炸  
- 纯聊天能讨论方案，但**方案变不成可验收、可重试的闭环任务**

CCC 补上的正是这一层：**调度器 + 意图入口 + 验收门禁**。

---

## 2. 三层产品形态

| 层 | 组件 | 用户感知 |
|----|------|----------|
| **对话面** | **CCC Hub**（自研） | 对齐 → 定稿 → 转任务；快捷键完成交接 |
| **编排面** | Engine + Board | 看板 Loop：拆解、开发、验收、重试、重开、进化 |
| **执行面** | 工具路由 | Claude / OpenCode 等按任务选用；Token 可治理 |

第三方 Agent IDE 壳（zcode、Qoder 等）曾是过渡方案；**Hub 已替代入口**。  
OpenCode 等是**执行器**，不是产品首页。

---

## 3. 闭环（人怎么用）

```text
对齐基线 → 下一步 → 定稿方案 → 转任务 → 下达并开工
  → Engine 自动编排 → 开发 → 验收
  →（失败则重试 / 重开）→ 归档 → 可进化
```

看板列（不可跳列）：

```text
backlog → planned → in_progress → testing → verified → released
```

控制面默认 **disabled**（不偷偷常驻）；要自动跑队列时显式 `enable`。见 [`CONTROL.md`](CONTROL.md)。

截图逐步说明见 [`INTRO-WALKTHROUGH.md`](INTRO-WALKTHROUGH.md)。

---

## 4. 无穷角色（不是角色超市）

```text
任务意图 → 路由工具 → Skill + Prompt = 本次角色
```

| 误解 | 实情 |
|------|------|
| 「CCC = 7 个固定工种，用户先选」 | `skills/ccc-*` 是 **Engine 阶段默认能力包**，用户不选 |
| 「要背很多 Skill」 | Skill 由系统按任务注入；Hub 仅可选**软偏好** |
| 「再做一个垂直行业就要再造一套角色产品」 | 换领域资产与 Domain Skill，**不换 Hub** |

与 ECC 类「角色一大堆」的差别：CCC 用**任务生成行为契约**，而不是让用户管理角色目录。

---

## 5. 垂直行业配方（商用核心）

任意垂直行业可以长成「专用 AI 工具」，而不必重写编排器：

```text
CCC 底座（Hub + Engine + Board + 通用阶段包）
  + 行业资产（爬虫 / DB / worker / API / 规则）
  + 领域 Skill（qx-* / 医疗-* / …）
  + 快捷键与自定义快捷键（一键下达模板任务）
  = 垂直行业 AI 工具
```

| CCC 提供 | 行业自带 |
|----------|----------|
| 意图入口与快捷动作 | 业务话术与一键场景（「跑四川价」「对账」…） |
| 编排、重试、verdict | 任务类型（crawl / ETL / report） |
| 执行器路由 | 具体脚本与 worker |
| 通用阶段包 | Domain Skill（质检、采价规则…） |
| 不替代业务库 | 既有 PostgreSQL / 对象存储等 |

首个竖切样板：**QX 分布式爬虫调度平台** — 详见 [`vertical-qx.md`](vertical-qx.md)。

---

## 6. QX 样板（一句话）

QX 已有爬虫、数据库、worker；长期缺的是 **Loop 级调度与人机快捷交接**。  
以 CCC 为底座挂载 QX 资产与自定义快捷键，即可把「脚本集合」升级为**可编排的垂直工具**；Dashboard 保留业务可视化，编排状态以 Hub 看板为准。

---

## 7. 安全与许可

- 控制面默认 `disabled`；`invent`（自造任务）必须显式打开  
- 红线 12：agent 不得擅自启用 CCC  
- 红线 11：验收必须落 verdict 文件  
- License：**MIT**

---

## 8. 从这里继续

| 想… | 读 |
|-----|-----|
| 安装跑通 | [`GETTING-STARTED.md`](GETTING-STARTED.md) |
| 定位一页纸 | [`VISION.md`](VISION.md) |
| 截图分镜 | [`INTRO-WALKTHROUGH.md`](INTRO-WALKTHROUGH.md) |
| 视频口播 | [`releases/intro-video-script.md`](releases/intro-video-script.md) |
| QX 竖切蓝图 | [`vertical-qx.md`](vertical-qx.md) |
| 仓库首页 | [`../README.md`](../README.md) |
