# CCC Vision — Connect–Claude Code · Loop Engineer

> **产品叙事 SSOT（对外/对内统一）**。README、Release、SKOT、Hub 文案冲突时以本文为准。  
> 版本对齐：`VERSION` · 更新日期：2026-07-19 · **Desktop 主产品**（见 `docs/product/ccc-desktop-architecture.md`）

---

## 一句话

**CCC（Connect–Claude Code）是一台 Loop Engineer：人用最短路径定意图，系统自动编排、自主执行、验收纠错，并持续进化。**

---

## 名字

| 字母 | 含义 |
|------|------|
| **C** | Connect |
| **C** | Claude |
| **C** | Code |

把 Claude Code 的能力接到**可编排的自主执行环**上——不是接到「又一个 IDE」。

---

## 产品形态（三层）

| 层 | 组件 | 用户感知 |
|----|------|----------|
| **对话面** | **CCC Desktop**（SwiftUI）+ 本机 Sidecar/loop-code（现网 **M1**） | 聊透、意图、定稿 → **仅产出 epic 大卡** |
| **编排面** | Hub + Board + Engine（现网 **Mac2017**） | 收大卡 → 扇出 → **远端开发/验收**；右栏只看状态 |
| **执行面** | 可插拔 Executors（默认 OpenCode；python / ollama / cli…） | 用户不选「用哪个 IDE」 |

**硬边界**：对话与编排开发分开；中间只交**结构化信息流**（transfer + flow 事件）。基线契约：[`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md)。

网页 Hub：**运维与兼容入口**，不是主聊天窗口。架构 SSOT：[`product/ccc-desktop-architecture.md`](product/ccc-desktop-architecture.md)。

### 已过时的说法（勿再对外使用）

- 「Hub 网页是主入口 / 双对话分屏 / Hub·Claude 双源历史」
- 「7 角色超市，用户先选角色」
- 「又一个 Claude 前端」
- 「不绑定单一 IDE / 接入 Trae、Zed…」作为产品主叙事

### 应坚持说的

- Connect Claude Code · **Loop Engineer**
- **Desktop 是主入口**（三栏：项目 · 方案对话 · 编排流程）
- **自由编排 + 多执行面**；Skill + Prompt = 本次角色（无穷角色）
- **方案 Agent（本机）只写待办大卡**；Engine（中心机）负责扇出与远端执行
- **对话面 / 编排面分离**；中间只交信息流（见边界契约）
- **Server / Client 分离**；改 `CCC_SERVER` 即可切局域网自托管 → 云 SaaS

---

## 部署形态（产品级）

| 层 | 放哪 | 说明 |
|----|------|------|
| **对话面** | 用户本机（现网：M1） | Desktop + Sidecar + loop-code；会话本机落盘 |
| **编排面** | 固定机（现网：Mac2017） | Hub `:7777` + Board + Engine + 中转 + **业务仓** |
| 过桥 | LAN/API | 仅 transfer（epic）与 flow 状态；非闲聊全文 |

拓扑与目录：[`deploy/topology.md`](deploy/topology.md) · [`deploy/desktop.md`](deploy/desktop.md) · [`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md)。  
默认注册（demo-only）：[`product/reset-demo-fleet.md`](product/reset-demo-fleet.md)。

---

## 与同类产品的边界

| 类型 | 典型 | CCC 关系 |
|------|------|----------|
| 执行器 CLI | OpenCode、部分 agent CLI | **执行面插件**；不是产品入口 |
| 固定角色工坊 | ECC 等「角色一大堆」 | CCC **不做角色超市**；角色由任务即时生成 |
| 纯对话 | ChatGPT / Claude.ai | 缺编排与验收闭环 |
| 第三方 Agent IDE 壳 | zcode、Qoder 等 | 曾考虑作编排器；**现由 Desktop + Engine 替代** |

一句话对照：

> OpenCode 等是执行器；ECC 等是固定角色工坊；Chat 是对话。  
> **CCC 是 Loop Engineer**：Desktop 定意图，自由编排扇出，多执行面跑闭环。

---

## 「无穷角色」机制（核心差异）

```text
任务意图
  → 路由工具（谁执行：Claude / OpenCode / …）
  → 注入 Skill + Prompt（这次怎么干）
  = 本次「角色」
```

- 仓库里的 `skills/ccc-*` **不是**给用户点选的菜单，而是**流水线阶段的默认能力包**（拆解 / 写码 / 审查 / 测试 / 归档…）
- Desktop / 转任务上的 Skill 提示是**软偏好**，不改变「用户无需记住 Skill」的原则
- 行业与场景差异落在 **Skill / Prompt / 工具路由**，不落在「再做一个新角色产品」
- 因此可覆盖任意行业复杂工作：**用户始终只面对意图**

红线 6「角色不互串」仍成立——指的是**同一次任务实例内**，编排阶段的职责边界（例如拆解包不写业务代码），不是「用户必须先选角色」。

---

## 能力闭环（对外讲述顺序）

1. **迅速对齐** — 基线 / 仓库上下文一次拉齐  
2. **迅速定任务** — 定稿方案 → 转任务（plan/phases 挂载）  
3. **自动编排** — backlog(epic) 扇出 work → … → released（小卡不可跳列；大卡常驻待办）  
4. **自动开发与验收** — 写码、测试、审查；失败可回灌重试  
5. **自动进化与纠错** — 教训、门禁、重开、quarantine  
6. **Token / 工具治理** — 不同任务走不同模型与执行器  

Hub 快捷栏（对齐基线 · 下一步 · 定稿 · 转任务 · …）是把上述闭环压成肌肉记忆的入口。

---

## 技术骨架（实现层，非卖点层）

```text
Hub (对话/看板/控制台)
  → Board API（任务 JSONL）
  → Engine（串行 Loop）
       → 阶段能力包（product/dev/reviewer/… = Skill+Prompt）
       → 执行器（OpenCode / Claude / …）
```

控制面：`~/.ccc/control.json` → `disabled` | `ui` | `enabled` | `invent`  
详见 [`CONTROL.md`](CONTROL.md)。

---

## 商用竖切

CCC 是**通用 Loop 底座**，不是单一行业 SaaS。垂直行业配方：

```text
CCC（Hub + Engine + 通用阶段包）
  + 行业资产（爬虫 / DB / worker）
  + Domain Skill + 自定义快捷键
  = 垂直 AI 工具
```

完整介绍与 QX 首样板：[`INTRO.md`](INTRO.md) · [`vertical-qx.md`](vertical-qx.md)。

---

## 开源立场

- License：**MIT**  
- 默认控制面 **disabled**：不偷偷常驻、不自造任务  
- 红线 12：agent **不得**擅自启用 CCC；须用户显式触发  

---

## 文档地图

| 文档 | 用途 |
|------|------|
| 本文 `VISION.md` | 产品叙事 SSOT |
| [`INTRO.md`](INTRO.md) | **对外完整介绍** |
| [`INTRO-WALKTHROUGH.md`](INTRO-WALKTHROUGH.md) | 截图分镜 |
| [`vertical-qx.md`](vertical-qx.md) | QX 竖切蓝图 |
| [`../README.md`](../README.md) | 对外首页 |
| [`GETTING-STARTED.md`](GETTING-STARTED.md) | 陌生人 10 分钟跑通 |
| [`../STARTUP-BRIEF.md`](../STARTUP-BRIEF.md) | Agent / 维护者启动（省 token） |
| [`USAGE.md`](USAGE.md) | 三类用户用法 |
| [`STRATEGY-MAP.md`](STRATEGY-MAP.md) | 架构与演进全景 |
| [`CONTROL.md`](CONTROL.md) | 运行控制面 |
| [`ccc-hub-ports.md`](ccc-hub-ports.md) | Hub 端口与账密 |
| [`deploy/topology.md`](deploy/topology.md) | Server/Client 拓扑 |
| [`deploy/server-layout.md`](deploy/server-layout.md) | 服务端目录规范 |
| [`deploy/migration-m1-to-2017.md`](deploy/migration-m1-to-2017.md) | M1→2017 迁移清单 |
| [`product/reset-demo-fleet.md`](product/reset-demo-fleet.md) | 产品默认注册（demo-only） |
| [`../CHANGELOG.md`](../CHANGELOG.md) | 版本历史 |
| [`roadmap.md`](roadmap.md) | 历史路线 + 当前方向索引 |
