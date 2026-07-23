# {{PROJECT_NAME}}

> Hub / Desktop 项目 Agent 注入本文件摘要（另叠平台 `hub_voice`）。  
> 由 `ccc init` 生成于 {{DATE}} — 请改成**本项目**真实约束，勿照抄 CCC 编排仓叙事。

## 项目脑索引（CCC · 必填）

| 层 | 路径 |
|----|------|
| 规划 / 未来待办 | {{PLAN_DOC_PATH}} |
| 当前产品意图 | `.ccc/agent-mind/decided.json` |
| 开发过程 | `.ccc/board/`（看板；**不是**目标清单） |

> 规划文用仓内已有文档（如 `docs/DEV_PLAN*.md` / `ROADMAP.md`），**禁止**另造根级 `TODO.md` 主路径。  
> 舰队标准：CCC 仓 `docs/product/project-agent-brain.md`。

## 项目

- **路径**: `{{PROJECT_PATH}}`
- **主语言**: {{PRIMARY_LANGUAGE}}
- **CCC**: 任务进本仓 `.ccc/board/`；Engine 只调度本仓 work 卡（须登记 `~/.ccc/workspaces.json`）

## CCC 流程

```text
Desktop 点本项目卡 → 定稿 → 转任务 → Engine 扇出 work
板堵 → 交接编排运维（ccc），业务 Agent 不自清全球板
```

- 启动必读：本文件索引 → `.ccc/profile.md` → **`.ccc/state.md`**（可能滞后，交叉 live board）
- **空板 + invent 硬关 = Engine 闲置正常**（勿建议降控制面）
- **一项目一对话**；M1 无业务第二树；事实信 Hub baseline / lens / 脑包

## 给 Agent 的硬规则

1. 所有改动与 `git commit` 必须在本仓库内完成（勿串写其它仓，尤其勿写入 CCC 编排仓）
2. 超出当前 plan/scope 的文件不要动
3. 验收要可执行；需要 verdict 时落 `.ccc/verdicts/`
4. 业务改码走 Hub「定稿 → 转任务」（用户显式触发，红线 12）

## 架构备忘

（模块入口、关键命令、禁止区…）

```bash
# 常用命令示例
# pytest -q
```
