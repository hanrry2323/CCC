# {{PROJECT_NAME}}

> Hub 对话在本仓库启动时注入本文件（另叠全局 `~/.claude/CLAUDE.md`）。  
> 由 `ccc init` 生成于 {{DATE}} — 请改成**本项目**真实约束，勿照抄 CCC 编排仓叙事。

## 项目

- **路径**: `{{PROJECT_PATH}}`
- **主语言**: {{PRIMARY_LANGUAGE}}
- **CCC**: 任务进本仓 `.ccc/board/`；Engine 只调度本仓 work 卡（须登记 `~/.ccc/workspaces.json`）

## CCC 流程

```text
Desktop 点本项目卡 → 对齐基线 → 定稿 → 转任务 → Engine 扇出 work
```

- 启动必读：`.ccc/profile.md` → `.ccc/state.md`（`state` 可能滞后，交叉 `git log -5`）
- **空板 + invent 硬关 = Engine 闲置正常**（勿建议降控制面）
- 热路径在**本仓**业务代码；勿把 `~/program/CCC` 的 `scripts/board` 当成业务架构
- **一项目一对话** `{本项目 id}::main`；迁移/注册/本机映射见 CCC 仓  
  `docs/product/desktop-agent-handoff.md` 与 `docs/runbooks/app-migrate-register-desktop.md`

## 给 Agent 的硬规则

1. 所有改动与 `git commit` 必须在本仓库内完成（勿串写其它仓，尤其勿写入 CCC 编排仓）
2. 超出当前 plan/scope 的文件不要动
3. 验收要可执行；需要 verdict 时落 `.ccc/verdicts/`
4. 小改可直接做；大规模多阶段走 Hub「定稿 → 转任务」（用户显式触发，红线 12）

## 架构备忘

（在此写模块入口、关键命令、禁止区…）

```bash
# 常用命令示例
# pytest -q
# npm test
```
