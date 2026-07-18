# 全局卫生计划模板（Cursor 通道 · 非 Engine）

> 在 **Cursor 打开 CCC 仓** 执行。**不要**生成 CCC backlog epic 让 Engine 自消费。  
> 目的：让 CCC 流程更顺（入口对齐、断链清理、舰队压量），不是在业务仓 fork 平台逻辑。

## 元信息

| 字段 | 填 |
|------|----|
| 日期 | YYYY-MM-DD |
| 触发原因 | （如：skill 断链 / ghost worktree / 串台 / doctor WARN） |
| 负责人 | |
| 报告落点 | `docs/ops/hygiene-YYYYMMDD.md`（或本目录旁报告） |

## 允许触碰

- **CCC 仓**：脚本、Hub、Skill、文档、registry 工具
- **业务仓（仅入口/登记类）**：`CLAUDE.md` / `.ccc/state.md` / `.ccc/profile.md` / doctor register·unregister
- **禁止**：在业务仓复制/修补 `_workspace_isolation`、Engine、commit-gate 等平台逻辑

## 清单（勾选）

- [ ] `python3 scripts/ccc-workspace-doctor.py migrate` — CCC = orch
- [ ] `python3 scripts/ccc-workspace-doctor.py` — ERROR=0；apps≤10
- [ ] prune 死路径 / ephemeral：`… prune --apply`
- [ ] Hub / OpenCode / Copilot skill 断链清理
- [ ] ghost worktree / 残留 agent worktree
- [ ] 各仓 Agent 入口（CLAUDE.md / AGENTS）与 state 对齐
- [ ] invent 硬关；控制面 `enabled` 合理
- [ ] CCC 看板历史积压：人工归档或 `ui_hidden`（**不**让 Engine 消费 orch）

## 执行记录

| # | 动作 | 仓 | 结果 |
|---|------|----|------|
| 1 | | | |

## 收尾

- [ ] 报告写入 `docs/ops/` 或 hygiene 报告
- [ ] 若改了 CCC 代码：单仓 commit；**不**经 Hub 下达到 CCC
- [ ] 更新 CCC `.ccc/state.md` 近 HEAD 备忘（可选）
