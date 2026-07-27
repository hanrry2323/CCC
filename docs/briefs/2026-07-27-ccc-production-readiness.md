# CCC 生产级完善路线（2026-07-27）

> **战略**：先把 CCC 做成生产级工具，再用 CCC 做业务生产。半成品上产线 = 空转。  
> **协作**：个人 Claude Code CLI（Relay `flash`）= 草稿工；Cursor = 指令 + 审合入 + 权威/双机。  
> SSOT：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「个人 Claude Code 草稿工」· [`docs/product/dev-channel.md`](../product/dev-channel.md)  
> 指令包：[`docs/dev-packets/`](../dev-packets/README.md)  
> 冲突以 authority 为准；本 brief 是路线与出门清单，不是第二套真理。  
> **更新（2026-07-27）**：三层出门 + 协作评估 + 效率仪表；主路径从 Ops 抛光切到金路径证据。

---

## 结论（先说清）

当前「Claude 草稿工 + Cursor 合入」**适合平台抛光与 UI/文档**，**不适合当作已达生产级的证据**。  
Demo 感来自：壳齐全（Desktop / Hub / Engine / 对话都能动）但缺**可复放的意图闭环证据**。  
**低 Token ≠ 有问题**；病是算力花在壳上、没花在真跑一笔业务意图上。  
**高 Token ≠ 接近生产**；刷运维 UI 烧再多也过不了「意图开发」门。

```text
Layer0 表面完备 ──G1–G6 + 金路径──► Layer1 平台生产级 ──LPSN + 域 KPI──► Layer2 业务意图生产级
```

粗估（诚实）：壳抛光 ~80%；平台生产证据 ~20–40%；意图飞轮自动化与业务 KPI 大多未证。再堆 UI packet 几乎不抬 Layer1。

---

## 三层出门（必须分开勾）

对齐下方 G1–G6 与 [`lpsn-ship-gate.md`](../product/lpsn-ship-gate.md)。**禁止**用 Layer0 冒充 Layer1；**禁止**用 `released` 冒充业务完成。

### Layer 0 — 表面完备

Desktop / sidecar / Hub / Ops 灯 / 文档口径一致。  
**不够开门**：只能说「壳在」。  
**当前**：Ops P0–P2、网页 `#/board`/`#/ops` 停更、App 重打包 — **大体已到**。

### Layer 1 — 平台生产级（敢承诺「用 CCC 跑业务开发」）

G1–G6 **全部绿**，且下列金路径证据缺一不可：

| ID | 指标 | 证据形态 | 状态 |
|----|------|----------|------|
| P-A | 对话不断 | M1 Desktop 连续对话 ≥30min 无假死；鉴权默认不挡 | 待证 |
| P-B | 写码通道 | 一笔 OpenCode `code` 任务真实落地 commit（非 mock） | 待证 |
| P-C | 编排不假绿 | 同一业务小 epic：backlog→planned→testing→**hollow+verdict 文件**→released | 待证 |
| P-D | 失败可收 | 人为造一笔 FAIL：进 failures、可 reopen/quarantine，槽位释放 | 待证 |
| P-E | 双机净 | `:17777` 隧道 + fleet/patrol 绿；无 M1 业务第二树 | 待证 |
| P-F | 运维敢下任务 | Ops 总灯绿时可下发；红灯可一键复制交 Agent | 接近（P0–P2 已合入） |

**Layer 1 出门句**：用户定一个**小而硬**的意图 → 后台自动开发/验收/修一轮 → 人只确认，不手工 SSH 救火。  
**未出门前**：业务仓可烟测 / demo，**不以** CCC 闭环当产能承诺。

#### G1–G6（拓扑与通道底盘）

| # | 门 | 验收 |
|---|----|------|
| G1 | **对话稳** | M1 Desktop / Claude Code / `:7788` 经 2017 relay `flash` 连续可用；鉴权默认关不挡内网 |
| G2 | **写码通道** | OpenCode `code` 经 Zen 免费池（big-pickle + flash-free）+ 双出口；限流可轮换；xfyun 退役 |
| G3 | **运维敢开发** | Desktop Ops 四域灯：绿敢下任务；红一键交 Agent；P0–P2 已合入并发布二进制 |
| G4 | **编排不假绿** | Engine 消费业务仓；hollow/verdict 真门；hang 收尸让下一卡；invent 硬关 |
| G5 | **双机拓扑净** | Hub 隧道 `:17777`；Hub 环回绑；sidecar Hub 反代；fleet 绿；无 M1 第二树 |
| G6 | **权威与巡查** | authority/patrol 绿；无「用 Claude Code 当合入 IDE」教法 |

### Layer 2 — 业务意图生产级（qb 类）

CCC 只保证到 **L（`code_landed`）+ P（探针可重放）+ S（`intent_stable`）**。  
**盈利、风控、实盘 SLA 是业务域 KPI**，不能用 `released` / VERSION 冒充。  
样板清单：[`2026-07-27-qb-domain-ship-gate.md`](./2026-07-27-qb-domain-ship-gate.md)。

| 层 | CCC 负责 | 业务仓（如 qb）必须另立 |
|----|----------|-------------------------|
| 意图门 | transfer 强制探针白名单 | 探针 = 可重放策略/风控/回测门槛脚本，不是散文 |
| 闭环 | Engine 扇出→verdict→regress | 回归失败自动建回归 epic |
| 稳定符合意图 | 人点 `intent_stable` / 探针窗口 | 纸面/实盘 SLA、最大回撤、成交与风控熔断、进程保活 |
| 完成定义 | 禁止 `released` = 完成 | 禁止「策略代码合入」=「能盈利」 |

生产级 qb = **Layer1 绿且业务 KPI 绿**，两套勾选。

---

## 协作效率评估（草稿工 001–008）

| 维度 | 实测 | 判断 |
|------|------|------|
| 吞吐 | ~8 包合入；大包后 Cursor 回合下降 | **有效**：适合白名单、可编译验收的切片 |
| 质量 | UI/文案/停更页大多一次过；偶发语义错（隧道口径、severity 严重度）需 Cursor 打回 | **中上偏壳**：边界清则稳；契约/拓扑语义须审 |
| 不适合 | 权威、双机热更、密钥、Engine 真跑、hang/verdict 门禁 | **禁止放大**到这些域 |
| 人的成本 | 转发仍是瓶颈；大包方向对 | 继续大包；**主题必须换成金路径断点修复** |

草稿工产出 =「按说明书改文件」合格 ≠「系统能替用户完成意图」。审合入通过 ≠ 生产级。

---

## 效率仪表（每周看一次 · 不追虚荣）

| 指标 | 健康信号 | 危险信号 |
|------|----------|----------|
| Cursor↔Claude 转发回合 / 合入包 | 大包 ≤2 回合合入 | 碎包、反复打回语义 |
| 草稿打回率（语义/契约） | &lt;20% | &gt;40% → packet 写糊或越权 |
| **平台金路径烟测** | 每周 ≥1 次绿（P-B/P-C 有 tid） | 只合 UI、零 Engine 真跑 |
| Relay/OpenCode 实耗 | 金路径上有真实 `code`/`flash` 消耗 | 仅文档包零编排流量 |

**该变大的流量**：Engine 真路径、失败学习、业务探针 regress — **不是**更多 Desktop Ops chip。

---

## 分程（谁做）

### 程 0 — 协作底座（Cursor · 已完成）

- [x] authority / consensus / dev-channel 草稿工例外  
- [x] 本 brief + `docs/dev-packets/` 模板与首包  
- [x] 试跑 packet 链（P1 四张 + P2 + 008 polish）

### 程 1–2 — Desktop Ops（已收束）

- [x] P1 001–004 · P2 005–007 · 008 Hub/Desktop polish · App 重打包  
- [ ] 009 文档/SPA 清理（可收尾；**不算 Layer1 进度**）  
- **此后**：停止 Ops 抛光作主路径；草稿工仅接「金路径打回的白名单缺陷」包。

### 程 3 — 金路径证据（Cursor / 2017 · **现行主路径**）

- [ ] G1–G6 逐项留日志 / 板面 tid  
- [ ] P-A…P-F 证据（优先一笔已 register 业务仓小 epic → released + verdict → regress）  
- [ ] code 池限流观察与钥扩容（配置，不进 git）  
- [ ] HK 隧道 KeepAlive / fleet 探活  
- 断点记录：[`2026-07-27-golden-path-evidence.md`](./2026-07-27-golden-path-evidence.md)

### 程 4 — 产品飞轮（单开 · 勿与 Ops 混）

- LPSN / `intent_stable` / next_goal（见 [`lpsn-ship-gate.md`](../product/lpsn-ship-gate.md)）  
- **仅当 Layer1 出门后再放大**

### 程 5 — 业务域 KPI（qb 样板）

- 见 [`2026-07-27-qb-domain-ship-gate.md`](./2026-07-27-qb-domain-ship-gate.md)  
- 与 CCC `intent_stable` **分离勾选**

---

## 还要多少步（依赖序 · 不虚报日历）

1. 收束壳工作（009 可完即停 Ops 大包主路径）  
2. Cursor 主导跑 Layer1 证据（程 3）  
3. 金路径哪里断修哪里（此处才加大编排模型流量）  
4. LPSN 门禁绿 + 人工样板  
5. 才开「用 CCC 做业务生产」；qb 再挂业务 KPI

---

## 效率纪律

1. **优先大包长任务**（多 Phase、一次回报）；主题优先金路径断点，不优先壳抛光。  
2. Claude Code **不 push main**；分支名 `draft/<packet-id>`；可多 commit。  
3. **禁止** `git add -A`；只 add 白名单。  
4. Cursor 合入前跑验收；失败则改 packet 再发。  
5. 权威/探针生产态/鉴权密钥 **不进**草稿包。  
6. Desktop Agent **永不**当草稿工改 CCC。  
7. **Layer1 证据只认 Cursor/2017 真跑**；草稿合入 UI **不计入** P-B/P-C。

---

## 当前状态（2026-07-27）

| 项 | 状态 |
|----|------|
| Relay flash / code 免费池 | 已部署；持续观察限流 |
| Agent Token 默认关 + Hub 反代列项目 | 已落地 |
| Desktop Ops P0–P2 + 008 polish | 已合入；App 已重打包 |
| Layer 0 表面完备 | **大体已到** |
| Layer 1 金路径 P-A…P-F | **未出门**（证据见 golden-path brief） |
| Layer 2 / qb 域 KPI | 清单已立；**未勾** |
| 业务生产主路径 | **未开门** |
| 草稿工主路径 | Ops 抛光 **收束** → 仅金路径白名单缺陷 |
