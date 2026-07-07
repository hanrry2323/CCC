# CCC — Connect–Claude Code

> **One skill, every IDE, every model.** A skill that turns any coding agent
> into a 6-role automated development system with kanban board.

---

## 含义

**C**onnect — **C**laude **C**ode

把 Claude Code 的执行能力**连接到任何 IDE 工具**：
- Trae / Cursor / Zed / VS Code / OpenCode — 都能用同一套 SKILL
- 6 个角色独立 skill（`skills/ccc-<role>/SKILL.md`），各司其职
- 中转站路由（`ANTHROPIC_BASE_URL`）— 任务类型自动选模型

## 核心

```
CCC = 1 个 SKILL.md（总纲）
      + 6 个角色 SKILL.md（skill/）
      + 12 条红线 + X6
      + 看板（board/）
      + 6 launchd plist 周期跑
```

CCC 不是 framework 代码库，**是一个 prompt 资产套件 + 工程纪律沉淀**。

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `SKILL.md` | 注入 prompt 总纲（agent 启动时自动加载） |
| `skills/ccc-<role>/SKILL.md` × 6 | 各角色 skill 定义 |
| `skills/README.md` | 6 角色 skill 索引 |
| `references/red-lines.md` | 12+X6 红线强约束 |
| `scripts/ccc-board.py` | 6 角色看板核心 |
| `scripts/roles/<role>.sh` × 6 | 各角色 launchd 入口 |
| `scripts/opencode-exec.py` | OpenCode CLI 执行器 |
| `scripts/opencode-pool.py` | 进程池（max 3 并发） |
| `scripts/opencode-watchdog.sh` | 残留扫描 |
| `scripts/ccc-notify.sh` | macOS 桌面通知 |
| `scripts/ccc-exec-launcher.sh` | 单 phase 启动入口 |
| `scripts/ccc-exec-commit.sh` | 单 phase 单 commit |
| `templates/` | plan/phases/report/verdict/AGENTS 模板 |
| `tests/scripts/` | pytest 核心测试 |

## 30 秒上手

```
1. 装 6 plist：bash scripts/install-ccc-roles.sh
2. 老板写 task 到 .ccc/board/backlog/（或说"按 CCC 跑 X"）
3. 产品经理（product）4小时一轮：拆 task → 写 plan → 挪 planned
4. 开发（dev）30分钟一轮：按 plan 写代码 → 挪 testing
5. 审查（reviewer）2小时 / 测试（tester）4小时：验收 → 挪 verified
6. 知识管理（kb）23:00：打 tag + push → 挪 released
```

## 6 角色

| 角色 | 频率 | 看板列 | 职责 |
|------|------|--------|------|
| **product** | 4h | backlog → planned | 拆任务、写 plan、SPEC 门禁 |
| **dev** | 30min | planned → in_progress → testing | 调 opencode 写代码 |
| **reviewer** | 2h | testing → verified | 只读静态检查 + 范围核对 |
| **tester** | 4h | testing → verified | pytest + plan 逐条验收 |
| **ops** | 30min | 所有列 | 健康检查 + 告警 |
| **kb** | 23:00 | verified → released | git tag + push + changelog |

各角色 skill 定义见 `skills/ccc-<role>/SKILL.md`。

## 关键纪律

- **红线 6**: 角色不互串（product 不写代码，reviewer 不写 plan）
- **红线 11**: 验收必须写 verdict 文件（口头 PASS 不算）
- **红线 12**: 禁止 agent 自主启用 CCC（必须用户显式触发）
- **红线 X1-X6**: OpenCode 进程管理 + 看板流转 + plist

详见 `references/red-lines.md`。

## 链接

- 注入 prompt 总纲：`~/program/CCC/SKILL.md`
- 6 角色 skill 索引：`~/program/CCC/skills/README.md`
- 红线清单：`~/program/CCC/references/red-lines.md`
- 教训沉淀：`~/program/CCC/docs/lessons.md`
- 模板库：`~/program/CCC/templates/`
- 当前版本：`0.18.0`
