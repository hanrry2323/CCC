# CCC — Connect–Claude Code (v0.38.0)

> **One skill, every IDE, every model.** A skill that turns any coding agent
> into a 7-role automated development system with kanban board.
>
> **启动必读（SSOT）**：[`STARTUP-BRIEF.md`](STARTUP-BRIEF.md)。CLAUDE.md / SKILL.md 与本 README 冲突时以 STARTUP-BRIEF + `VERSION` 为准。

---

## 含义

**C**onnect — **C**laude **C**ode

把 Claude Code 的执行能力**连接到任何 IDE 工具**：
- Trae / Cursor / Zed / VS Code / OpenCode — 都能用同一套 SKILL
- 7 个角色独立 skill（`skills/ccc-<role>/SKILL.md`），各司其职
- CCC Engine 串行驱动看板（非 7 角色定时轮询）
- **Claude** 做 product/reviewer；**OpenCode** 做 dev 写代码

## 核心

```
CCC = 1 个 SKILL.md（总纲）
      + 7 个角色 SKILL.md（skills/）
      + 12 条红线 + X 系列参考
      + 看板（.ccc/board/）
      + 2 plist：com.ccc.engine + com.ccc.board-server
```

CCC 是 **prompt 资产 + Engine 运行时**。运行时 SSOT 在 `scripts/`（`ccc-engine.py` / `ccc-board.py`）。

### 任务闭环（v0.38）

```
backlog → product(claude) → planned → dev(opencode) → testing
       → reviewer+tester → verified → kb → released
```

空看板默认**不**自动 evolve/补任务（`CCC_AUTO_REPLENISH=0`），避免后台内存爆掉。

## 关键资产清单

| 路径 | 角色 |
|------|------|
| `STARTUP-BRIEF.md` | **启动 SSOT**（必读） |
| `SKILL.md` | 注入 prompt 总纲 |
| `skills/ccc-<role>/SKILL.md` × 7 | 各角色 skill 定义 |
| `references/red-lines.md` | 12+ 红线强约束 |
| `scripts/ccc-engine.py` | CCC Engine 主循环 |
| `scripts/ccc-board.py` | 7 角色看板核心 |
| `scripts/ccc-board-server.py` | 看板 HTTP |
| `scripts/opencode-exec.py` | OpenCode CLI 执行器 |
| `templates/` | plan/phases/report/verdict 模板 |
| `tests/scripts/` | pytest 核心测试 |

## 30 秒上手

```
1. 装 Engine + board-server：bash scripts/install-ccc-roles.sh
2. 写 task 到 .ccc/board/backlog/（或说「按 CCC 跑 X」）
3. Engine 串行：product → planned → dev → testing → reviewer+tester → kb → released
4. regress 23:30（或空闲段）回测；回归 bug 回 backlog
```

## 7 角色（Engine 串行驱动，X6 定时已废止）

| 角色 | Engine 触发 | 看板列 | 职责 |
|------|-------------|--------|------|
| **product** | backlog 非空 / `--promote` | backlog → planned | 拆任务、写 plan、SPEC 门禁 |
| **dev** | planned 有 task | → in_progress → testing | 调 opencode 写代码 |
| **reviewer** | testing 门禁 | → verified | LLM 语义审查（small 可跳过） |
| **tester** | testing 门禁 | → verified | pytest + 验收清单（small 可跳过） |
| **ops** | 空闲轻度检查 | 不动 board | 健康检查 + 告警 |
| **kb** | verified 通过后 | → released | git tag + changelog |
| **regress** | 23:30 / 空闲 | released → backlog | 每日回测 |

各角色 skill 定义见 `skills/ccc-<role>/SKILL.md`。

## 关键纪律

- **红线 6**: 角色不互串（product 不写代码，reviewer 不写 plan）
- **红线 11**: 验收必须写 verdict 文件（口头 PASS 不算）
- **红线 12**: 禁止 agent 自主启用 CCC（必须用户显式触发）

详见 `references/red-lines.md`。

## 链接

- 启动简报：`STARTUP-BRIEF.md`
- 注入 prompt 总纲：`SKILL.md`
- 红线清单：`references/red-lines.md`
- 当前版本：见仓库根目录 `VERSION`（权威源）
