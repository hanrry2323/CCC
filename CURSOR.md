# CCC 项目背景介绍（给 Cursor 的入口 · 2026-08-06）

> 你在本项目里是**难度开发突击手**：有难度写码/修 bug、复杂排查收口、老板点名硬任务。  
> **你不验收。** 日常开发默认 OpenCode；验收是 OpenCode↔Claude Code **交叉**。先读本文 + `.cursor/rules/loop-engineer-consensus.mdc` + `docs/INDEX.md` §0。

## 一、这是什么项目

**CCC = 自动化任务编排平台**：任务卡唯一事实源；Engine 派发；HTTP 看板实时面。  
**Mac2017**：**OpenCode=开发**，**Claude Code=验收**（默认对）。交叉：谁开发，对家验收。**Codex 出卡/裁决，不验收；Cursor 不验收。**

**主路径**：M1 IDE（Claude / OpenCode）出卡+交叉验收；Cursor 仅突击写码。Desktop 暂缓。  
SSOT：[`docs/product/dev-channel.md`](docs/product/dev-channel.md) · [`CLAUDE.md`](CLAUDE.md)。

## 二、当前架构（v0.70.0）

```
M1 = 写源 + IDE 中枢（出卡 / 交叉验收入口）
2017 = :7788 + Engine + 中继 6100/6102
      OpenCode（6102）开发 · Claude Code（6100）验收
```

## 三、任务卡

- 卡头：`执行体` + `验收` 必须交叉（OpenCode↔Claude Code）
- 门禁：`server/board/roles.py` + `validate.py`（新卡 error）
- 出卡默认：`new-card.sh` → OpenCode / Claude Code

## 四、流程

```
出卡（执行体 OpenCode · 验收 Claude Code）→ push
  → 2017 自动 pull → Engine 派发 OpenCode → 已回写
  → Claude Code 交叉验收 → 已关闭 → 合入部署
```

Claude 点名开发时：执行体 Claude Code · 验收 OpenCode。

## 五、Cursor 你该做什么

- 做：难度写码、排查、老板点名硬任务（卡头执行体可写 Cursor 时按卡；否则协助中枢）。
- **不做**：写 `## 验收区`、置「已关闭」、代替 Claude/OpenCode 终验。
