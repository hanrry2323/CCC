# 开发通道 — 谁改 CCC（2026-08-06 交叉验收）

> **老板面**：M1 IDE 聊意图 + 看板/中继/Δ；中间自动。  
> **Mac2017 区分**：**OpenCode = 开发**；**Claude Code = 验收**（默认对）。  
> **交叉验收**：谁开发，对家验收（OpenCode↔Claude Code）。**Codex / Cursor 取消验收资格。**

## 席位

| 席位 | 绑定 | 做什么 |
|------|------|--------|
| **OpenCode** | 2017 默认可后台开发（6102） | 按卡写码 → 已回写；**不自验** |
| **Claude Code** | 2017 默认验收席（6100）；亦可点名开发 | OpenCode 卡 → Claude 验收；Claude 开发卡 → OpenCode 验收 |
| **Codex** | 管理席 | 出卡 / 裁决 / 仲裁；**不验收** |
| **Cursor** | 难度突击写码 | 硬骨头开发；**不验收** |
| **M1 IDE** | 开发中枢 + 交叉验收入口 | 聊意图出卡；已回写后由**对家**写 `## 验收区` |

## 交叉规则（硬）

```text
执行体 OpenCode  → 验收必须 Claude Code
执行体 Claude Code → 验收必须 OpenCode
禁止：自验、Codex 验收、Cursor 验收
```

机器门禁：`server/board/roles.py` + `validate.py`（新卡 error）。出卡默认：`scripts/new-card.sh` → OpenCode / Claude Code。

## 主路径

```text
M1 IDE 出卡（执行体 OpenCode · 验收 Claude Code）→ push
  → 2017 自动 pull → Engine 派发 OpenCode → worktree → 已回写
  → M1 上 Claude Code 交叉验收（写验收区 + 已关闭）→ 合入部署
```

点名 Claude 开发时：卡头 `执行体：Claude Code · 验收：OpenCode`，由 OpenCode 验收。

## 红线

1. 执行体禁止写验收区 / 置已关闭。  
2. 验收席独立取证，不采信执行摘要。  
3. Codex 可出卡不可终验；Cursor 可突击写码不可终验。
