# CCC 生产级完善路线（2026-07-27）

> **战略**：先把 CCC 做成生产级工具，再用 CCC 做业务生产。半成品上产线 = 空转。  
> **协作**：个人 Claude Code CLI（Relay `flash`）= 草稿工；Cursor = 指令 + 审合入 + 权威/双机。  
> SSOT：[`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)「个人 Claude Code 草稿工」· [`docs/product/dev-channel.md`](../product/dev-channel.md)  
> 指令包：[`docs/dev-packets/`](../dev-packets/README.md)  
> 冲突以 authority 为准；本 brief 是路线与出门清单，不是第二套真理。

---

## 出门门禁（生产级 = 可敢用 CCC 跑业务）

全部勾上才开「用 CCC 做业务生产」主路径：

| # | 门 | 验收 |
|---|----|------|
| G1 | **对话稳** | M1 Desktop / Claude Code / `:7788` 经 2017 relay `flash` 连续可用；鉴权默认关不挡内网 |
| G2 | **写码通道** | OpenCode `code` 经 Zen 免费池（big-pickle + flash-free）+ 双出口；限流可轮换；xfyun 退役 |
| G3 | **运维敢开发** | Desktop Ops 四域灯：绿敢下任务；红一键交 Agent；P0 已落地，**P1 合入**，P2 二进制发布 |
| G4 | **编排不假绿** | Engine 消费业务仓；hollow/verdict 真门；hang 收尸让下一卡；invent 硬关 |
| G5 | **双机拓扑净** | Hub 隧道 `:17777`；Hub 环回绑；sidecar Hub 反代；fleet 绿；无 M1 第二树 |
| G6 | **权威与巡查** | authority/patrol 绿；无「用 Claude Code 当合入 IDE」教法 |

**未出门前**：业务仓可烟测 / demo，**不以** CCC 闭环当产能承诺。

---

## 分程（谁做）

### 程 0 — 协作底座（Cursor · 本部署）

- [x] authority / consensus / dev-channel 草稿工例外  
- [x] 本 brief + `docs/dev-packets/` 模板与首包  
- [x] 试跑 packet 链（P1 四张 + P2 agent-minds/patrol/web-ops）已跑通

### 程 1 — Desktop Ops P1（草稿工为主 · Cursor 审）

见 [`2026-07-27-desktop-ops-refactor.md`](./2026-07-27-desktop-ops-refactor.md) P1：

| Packet | 内容 | 建议执行者 |
|--------|------|------------|
| `ops-p1-copy-vs-handoff` | 告警「仅复制」vs「交给 Agent」 | Claude Code 草稿 |
| `ops-p1-tunnel-row` | 显式 Hub `:17777` + launchd 行 | Claude Code 草稿 |
| `ops-p1-domain-chips` | chip 绿/橙/红；fail-open=橙 | Claude Code 草稿 → Cursor 审灯色 |
| `ops-p1-upstream-panel` | 折叠模型通道接 upstream-daily | Claude Code 草稿 |

### 程 2 — Desktop Ops P2 + 发布（Cursor 为主）

- 巡查 alerts 进红条、agent_minds、`#/ops` 降级  
- **重建 App 二进制**（三档 picker + 运维 UI）  
- 正式打生产可用版本说明（VERSION/CHANGELOG 按需）

### 程 3 — 编排与写码稳态（Cursor / 2017）

- code 池限流观察与钥扩容（配置，不进 git）  
- HK 隧道 KeepAlive / fleet 探活  
- Engine 烟测：一笔业务仓小卡真跑通 verdict  

### 程 4 — 产品飞轮（单开 · 勿与 Ops 混）

- LPSN / `intent_stable` / next_goal（见既有 lpsn briefs）  
- **仅当 G1–G6 出门后再放大**

---

## 效率纪律

1. **一张 packet 一事**；白名单路径；禁止 `git add -A`。  
2. Claude Code **不 push main**；分支名 `draft/<packet-id>`。  
3. Cursor 合入前必跑 packet「验收」；失败则改 packet 再发，不口头扯皮。  
4. 权威/探针/隧道/鉴权 **不进**草稿包。  
5. Desktop Agent **永不**当草稿工改 CCC。

---

## 当前状态（部署日）

| 项 | 状态 |
|----|------|
| Relay flash / code 免费池 | 已部署；持续观察限流 |
| Agent Token 默认关 + Hub 反代列项目 | 已落地 |
| Desktop Ops P0 | 已合入 |
| Desktop Ops P1 | 已合入（001–004） |
| Desktop Ops P2 | agent-minds / 本地巡查红灯 / 网页 #/ops 停更 / App 已重打包 |
| 业务生产主路径 | **未开门**（G1–G6 持续验收） |
