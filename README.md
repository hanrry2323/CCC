# CCC — Connect–Claude Code

> **One skill, every IDE, every model.** A skill that turns any coding agent
> into a Plan → Execute → Verify pipeline.

---

## 含义

**C**onnect — **C**laude **C**ode

把 Claude Code 的执行能力**连接到任何 IDE 工具**：
- Trae / Cursor / Zed / VS Code / OpenCode — 都能用同一份 SKILL
- SKILL 一次性注入 prompt，不污染 agent 上下文
- 中转站路由（`ANTHROPIC_BASE_URL`）— 任务类型自动选模型

## 核心

```
CCC = 1 个 SKILL.md
      + 11 条红线
      + 4 文件契约
      + IDE 定时任务（可选）
      + 知识飞轮（可选）
```

CCC 不是 framework 代码库，**是一个 prompt 资产 + 工程纪律沉淀**。

## 30 秒上手

```
1. 把 ~/program/CCC/ 作为 skill 加载到 IDE
2. 在项目目录下开新对话
3. 用户说："按 ccc full 跑 X 任务"
4. agent 加载 4 文件契约 + 红线，跑 Planner/Executor/Verifier
```

## 三角色

| 角色 | 谁 | 产出 |
|------|----|------|
| **Planner** | 你 + agent 对话 | `.ccc/plans/<task>.plan.md` + `phases/<task>.phases.json` |
| **Executor** | agent 自主 | `.ccc/reports/<task>.report.md` |
| **Verifier** | 独立 session | `.ccc/verdicts/<task>.verdict.md`（≥3 probes） |

严格分离：**Planner 不写 verdict，Verifier 不写 plan**。

## 关键纪律（详见 `references/red-lines.md`）

- **红线 11**: Verifier 必须写 verdict 文件（口头 PASS 不算）
- **红线 12**: 禁止 agent 自主启用 CCC（必须用户显式触发）
- **Lesson 27**: `claude -p` 是 print 模式，prompt 必须走 stdin
- **Lesson 28**: Verdict 强证据红线 11 的来历

## 路由决策（用户拍板）

| 任务 | 谁处理 |
|------|-------|
| 单文件 / 调试 / 查信息 | agent 直接处理（**不**走 CCC） |
| 多文件 / 跨模块 | CCC 启用 1-2 phase |
| 多阶段 / 跨会话 | CCC 强制 + 完整 4 文件 |

## 配套

- **知识飞轮**：`quality_flywheel.py` 自动沉淀失败模式 → 丰富红线
- **IDE 定时**：cron / launchd 自动唤起 CCC
- **跨设备**：CCC 调度器 / ssh 集群扩展（v1.0 路线）
- **跨模型**：`ANTHROPIC_BASE_URL=http://127.0.0.1:4000` 走中转站路由

## 链接

- 唯一 SKILL 资产：`~/program/CCC/SKILL.md`
- 红线清单：`~/program/CCC/references/red-lines.md`
- 发展路线：`~/program/CCC/docs/roadmap.md`
- 框架说明书：`~/program/CCC/docs/architecture.md`
- 教训沉淀：`~/program/CCC/docs/lessons.md`
- 模板库：`~/program/CCC/templates/`
- 当前版本：`1.1.0`（v1.1：工程化 + 自动化底座就绪）
