# 开发通道 — 谁改 CCC（2026-08-07 北星）

> **老板面**：主 IDE 谈意图 → 确认 `ccc-plan` → 盯看板；中间自动。  
> **Mac2017**：**OpenCode = 开发**；回写后 **Claude（或交叉对家）= 机审**（质量门）。  
> **人侧**：**「合入批准」** = 审 diff 后 ff-merge+关卡（旧称「验收看板」）。  
> 竖切：[`north-star-slice.md`](north-star-slice.md)

## 席位

| 席位 | 绑定 | 做什么 |
|------|------|--------|
| **OpenCode** | 2017 默认开发（6102） | 写码 → 已回写；不自验、不写机审/验收区 |
| **Claude Code** | 2017 默认机审（6100）；可点名开发 | 机审写 `## 机审区` |
| **Codex** | 管理席 | 出卡/裁决 |
| **Cursor** | 难度突击 | 写码；不代关卡 |
| **主 IDE** | 中枢 | `plan-to-cards`；说「合入批准」 |

## 主路径

```text
确认 ccc-plan → plan-to-cards（一次多卡 push）
  → 2017 自动 pull → Engine 派发 OpenCode → worktree
  → 机械门禁（新 commit + 非空 diff）→ 已回写
  → Engine 拉 Claude 机审 → ## 机审区 通过 → ready_for_merge
  → 老板审 diff →「合入批准」→ approve-merge.sh → 已关闭
```

质量过不过看机审/门禁 exit code，不看口头流程。「验收看板」及旧同义句 = **合入批准** 别名。

Claude 点名开发时：机审为 OpenCode（交叉）。

## 红线

1. 开发禁止写机审区/验收区/已关闭。  
2. 机审禁止改业务码、禁止已关闭。  
3. 合入前取证认 `origin/codex/<stem>`（`card-evidence.sh`）；进度认 2017 API。  
4. 禁止新增验收同义句/席位 SOP（INDEX §0 反目标）。
