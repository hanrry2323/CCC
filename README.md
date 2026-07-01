# CCC — Codex Claude Collaboration

> AI Agent 协作框架 · 三角色 (Planner/Executor/Verifier) · 自然语言契约 · 文件级持久化
> 当前版本: v0.3.0-dev (2026-07-01)

## 框架定位

CCC 是一个**编程框架**（不是脚本集），用于让多个 LLM agent 角色协作完成复杂任务：
- **Planner**：用户意图 → 写 plan.md + phases.json + 启 Executor/Verifier
- **Executor**：按 plan 自主执行 + 写 report + 1 phase 1 commit
- **Verifier**：独立验收 + ≥3 adversarial probes + 写 verdict

三角色严格分离，任何角色越界都是 Critical 违规。

## 快速上手

1. **启动 Planner**：用任何能调起 LLM 的 agent 读 CCC CLAUDE.md，按 plan 模板写 `.ccc/plans/<task>.plan.md`
2. **启 Executor**：用 `claude -p "$(cat plan+phases)" --permission-mode bypassPermissions --max-budget-usd 200` 后台跑
3. **启 Verifier**：同 Executor 命令，prompt 要求 ≥3 adversarial probes + VERDICT 三选一
4. **自动监控**：每启 Executor 必建 `mavis cron self qxo-<task> --every 5m`

## 核心红线

红线 1-9 详见 `~/program/CCC/CLAUDE.md` 顶部"近期实战更新"段。最关键：
- **红线 8**：Planner 越界 = Critical（C1 Edit 源码 / C2 commit-push / C3 ssh / C4 rsync / C5 sed 盲改 / **C6 mavis session new**）
- **红线 9**：Executor/Verifier 必须用 `claude -p`，禁止用 `mavis session new <agent>`（会 fallback minimax/MiniMax-M3 = 三角色失效）

## 链接

- 总纲: `~/program/CCC/CLAUDE.md`
- 架构文档: `~/program/CCC/docs/architecture.md`
- 协议决策: `~/program/CCC/docs/adr/`
- 实战案例: `~/program/CCC/examples/`
- 项目模板: `~/program/CCC/templates/`
- 框架技能: `~/program/CCC/skills/`

## 版本

```
cat ~/program/CCC/VERSION
# 0.3.0-dev
```

详细历史见 `~/program/CCC/CHANGELOG.md`.
