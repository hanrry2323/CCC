# CCC Vision — Connect–Claude Code · Loop Engineer

> **产品叙事 SSOT（对外/对内统一）**。README、Release、SKOT、Hub 文案冲突时以本文为准。  
> 版本对齐：`VERSION` · 更新日期：2026-07-18 · **多仓生产就绪 v0.50**（见 `docs/milestones/m1-ten-workspaces.md`）

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
| **对话面** | **CCC Hub**（自研 UI） | 对齐 → 定稿 → 转任务；几个快捷动作完成意图交接 |
| **编排面** | Engine + Board（看板） | Loop：拆解、调度、重试、重开、进化；人盯结果 |
| **执行面** | 工具路由（Claude / OpenCode / …） | 按任务选执行器；用户不选「用哪个 IDE」 |

### 已过时的说法（勿再对外使用）

- 「不绑定单一 IDE / 接入 Trae、Zed、Qoder…」——第三方编排壳曾是过渡方案；**Hub 已替代入口**
- 「7 角色超市，用户先选角色」——易被理解成 ECC 类产品
- 「又一个 Claude 前端」

### 应坚持说的

- Connect Claude Code  
- **Loop Engineer**：自动编排 · 自主执行  
- **Hub 是入口**（对话 + 看板 + 控制台一体）  
- **任务路由工具**；**Skill + Prompt = 本次角色**（无穷角色）  
- 用户**不选角色、不背 Skill**；只定意图  

---

## 与同类产品的边界

| 类型 | 典型 | CCC 关系 |
|------|------|----------|
| 执行器 CLI | OpenCode、部分 agent CLI | **执行面插件**；不是产品入口 |
| 固定角色工坊 | ECC 等「角色一大堆」 | CCC **不做角色超市**；角色由任务即时生成 |
| 纯对话 | ChatGPT / Claude.ai | 缺编排与验收闭环 |
| 第三方 Agent IDE 壳 | zcode、Qoder 等 | 曾考虑作编排器；**现由 Hub 完全替代** |

一句话对照：

> OpenCode 等是执行器；ECC 等是固定角色工坊；Chat 是对话。  
> **CCC 是 Loop Engineer**：对话定意图，看板跑闭环，工具按任务路由，角色由 Skill+Prompt 即时生成。

---

## 「无穷角色」机制（核心差异）

```text
任务意图
  → 路由工具（谁执行：Claude / OpenCode / …）
  → 注入 Skill + Prompt（这次怎么干）
  = 本次「角色」
```

- 仓库里的 `skills/ccc-*` **不是**给用户点选的菜单，而是**流水线阶段的默认能力包**（拆解 / 写码 / 审查 / 测试 / 归档…）
- Hub「转任务」上的 Skill chips 是**软偏好**，不改变「用户无需记住 Skill」的原则
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
| [`../CHANGELOG.md`](../CHANGELOG.md) | 版本历史 |
| [`roadmap.md`](roadmap.md) | 历史路线 + 当前方向索引 |
