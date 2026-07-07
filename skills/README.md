# CCC Skills 索引

6 角色定时开发系统，v0.18 唯一范式。

## 6 角色

| 角色 | 技能目录 | 看板列 | 频率 | 职责 |
|------|---------|--------|------|------|
| product | `skills/ccc-product/SKILL.md` | backlog → planned | 4h | 拆任务、写 plan、SPEC 门禁 |
| dev | `skills/ccc-dev/SKILL.md` | planned → in_progress → testing | 30min | 调 opencode 写代码 |
| reviewer | `skills/ccc-reviewer/SKILL.md` | testing → verified | 2h | py_compile + 静态检查 + 范围核对 |
| tester | `skills/ccc-tester/SKILL.md` | testing → verified | 4h | pytest + plan 验收项逐条验证 |
| ops | `skills/ccc-ops/SKILL.md` | 不动 board | 30min | 健康检查 + 告警 |
| kb | `skills/ccc-kb/SKILL.md` | verified → released | 每天 23:00 | git tag + push + changelog |

## 使用方式

每个 role 的 launchd plist 调 `scripts/roles/<role>.sh`，该脚本自动：
1. `export CCC_ROLE=<role>`
2. `export CCC_ROLE_SKILL=skills/ccc-<role>/SKILL.md`
3. log 加载的 skill 内容
4. 调 `scripts/ccc-board.py <role>`

## 共同规范

所有 skill 遵守：
- **红线 10**：读 `.ccc/state.md` 接力，不依赖会话级记忆
- **AGENTS.md 沉淀**：只写建议，不绕过人类审批
- **SPEC 门禁**（product 特有，但所有人应意识）
- **只读不写**（dev 除外）

## regress（新增，第 7 角色）

| 角色 | 技能目录 | 频率 | 职责 |
|------|---------|------|------|
| regress | `skills/ccc-regress/SKILL.md` | 每天 23:30 | 扫 released 重新验收，发现回归→建 bug |

