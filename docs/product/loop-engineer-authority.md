# Loop Engineer — 事实权威与人机共识（SSOT）

> **状态**：现行 · 2026-07-21  
> **谁读**：老板 / Desktop Agent / Hub·sidecar / Cursor 改平台。  
> **冲突时以本文为准。** 边界流程：[`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md)。  
> **规则**：你我共识 → **写入本文（或明确指向本文的一节）** → 再改代码/人格；禁止只留在聊天里。

---

## 一句话（开发路径）

**人定意图 → Hub 下达 → Engine 编排扇出 → 权威仓写码 → 验收纠错 → 回流飞轮；全程只认一个权威仓。**

（叙事：[`../VISION.md`](../VISION.md)。）

---

## 闭环七词

| 词 | 含义 |
|----|------|
| **意图** | 人在 Desktop 聊透目标与验收 |
| **下达** | 定稿 transfer；进队后不逐步人批 |
| **编排** | Engine 扇出 work、调度阶段 |
| **写码** | 只在 2017 权威仓；plan 白名单 |
| **纠错** | verdict 落盘；abnormal 止损 |
| **飞轮** | 归档 / 回测 / 再定意图 |
| **权威** | 代码与看板只在 register 仓；透镜 live |

---

## 行业共识（我们认可）

| 判断 | 结论 |
|------|------|
| Demo ≠ 上线 ≠ 稳定符合意图 | **行业共性**，非个人特例 |
| AI 擅 happy path；缺边界/验收/纠偏环 | 高级/低级模型都快到「能跑」，后半段才是鸿沟 |
| 接手老仓难于从零 | 隐性规则在人脑；须先对齐再交给 agent |
| 路线曲折、模型误解 | **默认**；产品要做闭环，不幻想一次聊完 |

CCC 卖的不是「更快写出第一版」，而是把后半段**工程化**。

---

## 价值立场（2026-07-21 评估）

| 项 | 口径 |
|----|------|
| 加权约 **7.2/10** | **值得继续做**，只压「闭环工程」 |
| 值钱 | 意图门 · 对话/编排分离 · 权威仓+透镜 · verdict/旁路收死 |
| 不值钱 | 复刻 IDE · 堆角色 · 堆文档 · 「接很多模型」当卖点 |
| 下一程证明 | 已对齐业务仓连续 **3 次**「定稿→在飞→verdict」可复述可纠；达不到就收范围 |

评分画布（讨论产物）：Cursor canvases `ccc-value-scorecard` / `ccc-pain-loop-stages`。

---

## 三阶段（都能接，门禁不同）

| 阶段 | 适配 | 交给 CCC 前须齐 |
|------|------|-----------------|
| 从零新建 | 强 | 意图 + 验收标准 |
| 接手老项目 | 中→强 | **全面对齐硬门** |
| 日常维护 | 强 | 小目标 + 白名单 + verdict |

**已注册 ≠ 可正式开发。** 正式交给 CCC 前须**全面对齐**：baseline + live 透镜 + risks + 可下达边界。

---

## 四权威（只认这张表）

| 权威 | 落点 | 谁可写 |
|------|------|--------|
| 意图 / 会话 | M1 Desktop `sessions/` | 人 + 讨论 Agent（聊） |
| 编排看板 | 2017 `apps/<id>/.ccc/board` | Hub transfer + Engine |
| **代码 SSOT** | 2017 已 register 的 `apps/<name>` | **仅** Engine 阶段执行器 |
| 远端备份 | GitHub | 人 / Cursor 同步；**不是**对话或 Engine cwd |

M1：**无**业务源码第二树；`localWorkspaceMap` 仅可选 `ccc` → 本机 CCC。

---

## 讨论 Agent 事实源

| 来源 | 用途 |
|------|------|
| Hub baseline | 开场（点时快照 + live board） |
| Hub **只读透镜** `/api/desktop/lens/{id}/…` | live 看板 / 文件 / grep / git |
| 本机会话 | 已聊目标与约束 |
| 本机 Read/git | **仅** `ccc` |

CLI：`python3 scripts/ccc-hub-lens.py board|tree|file|grep|git <project_id> …`  
禁止 sidecar `ssh mac2017` 探业务仓。问看板/文件 → **先透镜**；Hub 断 → 明说，禁止瞎编。

---

## 工程师模式

| 项目 | 规则 |
|------|------|
| 业务仓 | **拒绝** engineer |
| 平台仓 `ccc` | 可本机改 CCC |

业务改码：**定稿 → transfer → Engine**。

---

## 扇出角色（讨论面须知 · 勿扮演）

| 角色 | 可写 | 硬规则 |
|------|------|--------|
| product | plan/phases/扇出；不写源码 | cwd=2017 apps |
| dev | 仅 plan 白名单 | 红线 3 |
| reviewer/tester | verdict/report | Verdict 落盘才算 |
| 讨论 Agent | 无业务写 | 透镜只读 + `ccc-transfer` |

---

## 共识如何落盘（强制应用）

以后你我达成共识，执行顺序：

1. **改本文**（或在本文增加一节并改「状态」日期）——权威。  
2. **改入口**：`STARTUP-BRIEF.md` / `CLAUDE.md` / `.cursor/rules/loop-engineer-consensus.mdc` / 必要时 `hub_voice.py`——应用。  
3. **不要**另起平行「现行真理」长文；史实类标「史」并指回本文。  
4. 讨论画布可留作评分/梳理附件，**不**替代本文。

---

## 从零测 ccc-demo

1. 对齐基线 → 空板 + live `as_of`。  
2. 定稿转任务 →「刷新看板」见在飞 work。  
3. Hub 断 → 明说不可达。  
4. 业务仓工程师模式 → 拒。

板面重置归档：`apps/ccc-demo/.ccc/archive/reset-2026-07-21/`。

---

## 文档怎么读

| 优先级 | 文档 | 管什么 |
|--------|------|--------|
| **1** | **本文** | 路径 / 权威 / 共识 / 价值立场 |
| 2 | [`dialogue-orchestration-boundary.md`](dialogue-orchestration-boundary.md) | 过桥 |
| 3 | [`desktop-agent-handoff.md`](desktop-agent-handoff.md) | 接入 |
| 4 | [`desktop-agent-identity.md`](desktop-agent-identity.md) | 口吻 |
| 史 | [`m1-no-second-tree-closeout.md`](m1-no-second-tree-closeout.md) | 清扫记录 |

总索引：[`../INDEX.md`](../INDEX.md)。

---

## 禁止

- M1 业务第二树当权威  
- 讨论 Agent SSH 写 2017 / 扮演 product·dev  
- 过期 baseline 否定 live 看板  
- 业务仓工程师旁路  
- 共识只留在聊天、不落本文  

## API

`GET /api/desktop/lens/{id}/board|tree|file|grep|git/summary`
