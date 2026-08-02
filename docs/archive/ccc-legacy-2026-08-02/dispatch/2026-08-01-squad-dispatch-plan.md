# CCC 四窗口并行优化 · 调度总案（2026-08-01）

> 模式：Codex 调度 / 4 个 Claude Code 窗口并行 / 老板手动搬运  
> 覆盖：前端、后端、桌面端、中转站迁移 四条线

## 一句话结论

可行。前提是四个窗口各用独立工作区 + 独立分支，目录级隔离，谁都不碰别人的范围。

## 分工表

| 窗口 | 工作区目录 | 分支 | 任务书 |
|------|-----------|------|--------|
| A 前端 | `/Users/apple/program/ccc-ws-1-web` | `codex/ws-1-web` | `task-A-web-frontend.md` |
| B 后端 | `/Users/apple/program/ccc-ws-2-backend` | `codex/ws-2-backend` | `task-B-backend-engine.md` |
| C 桌面端 | `/Users/apple/program/ccc-ws-3-desktop` | `codex/ws-3-desktop` | `task-C-desktop-app.md` |
| D 中转站 | `/Users/apple/program/ccc-ws-4-relay` | `codex/ws-4-relay` | `task-D-relay-looprouter.md` |

> 第二波任务池：窗口 A 第一波验收通过后接 `task-A2-web-frontend-round2.md`（测试固化 + 看板/聊天体验 + 契约核对）。A/B/C 第一波完成报告回来后按需补第二波。

> **第四轮起（老板拍板）：四窗口 → 两窗口并行。** 第一~三轮（D/C/A/B/A2/B2/A3）全部闭环归档，工作区保留。

| 窗口 | 工作区目录 | 分支 | 任务书 |
|------|-----------|------|--------|
| 窗口 1 鉴权收口 | `/Users/apple/program/ccc-ws-5-auth` | `codex/ws-5-auth-close` | `task-E-auth-close-round4.md` |
| 窗口 2 桌面端测试 | `/Users/apple/program/ccc-ws-6-desktop-tests` | `codex/ws-6-desktop-tests` | `task-F-desktop-tests-round4.md` |

> **第五轮起：Basic 调用方迁移（开 on 前的最后一步）。** 第四轮已闭环（E 开关合入、F 桌面测试合入）。

| 窗口 | 工作区目录 | 分支 | 任务书 |
|------|-----------|------|--------|
| 窗口 1 脚本侧迁移 | `/Users/apple/program/ccc-ws-5-auth` | `codex/ws-5-auth-migrate` | `task-G-basic-migrate-scripts-round5.md` |
| 窗口 2 桌面端迁移 | `/Users/apple/program/ccc-ws-6-desktop-tests` | `codex/ws-6-desktop-bearer` | `task-H-basic-migrate-desktop-round5.md` |

> **第六轮起：7788 HTTP 对话页优化（老板拍板：页面与 App 同等重要）。** 评估见 `2026-08-01-http-chat-optimization-review.md`；第五轮已闭环（G/H Basic 迁移全部合入）。

| 窗口 | 工作区目录 | 分支 | 任务书 |
|------|-----------|------|--------|
| 窗口 1 对话壳体验 | `/Users/apple/program/ccc-ws-7-chat` | `codex/ws-7-chat-ux` | `task-I-http-chat-ux-round6.md` |
| 窗口 2 看板运维交互 | `/Users/apple/program/ccc-ws-8-boardops` | `codex/ws-8-board-ops` | `task-J-http-board-ops-round6.md` |

> 第二批（安全收口）：7788 对话口鉴权统一（核对 launchd → 开 token → Desktop 联动），第一批验收后单列。

## 每轮工作流

1. Codex 写/更新任务书（本目录）
2. 老板把任务书内容复制给对应 Claude 窗口（或让 Claude 直接读文件）
3. Claude：先读文档 → `/plan` 出方案 → 等确认 → 实现 → `/review` → `/test` → 提交到自己的分支
4. 老板把 Claude 的最终输出贴回 Codex
5. Codex 对抗性审查（红旗扫 → 范围 → 测试 → 质量 → 结论）
6. 通过：Codex 合入 main；不通过：Codex 出修订单，重复 2–5

## 硬规则（所有窗口通用）

1. 开工先读 CLAUDE.md + 相关 docs；不读不干活
2. 只在自己允许的目录里改；越界算失败
3. 不碰密钥/凭据/生产配置；不启动产线；不动 Hub/Board/Engine 运行态
4. 不删文件（除非任务书要求并说明理由）
5. 改完必须跑测试 + /review，证据不齐不算完成
6. 只提交自己的分支，禁止直接碰 main
7. ai-loop-router 是独立仓，不在本批任何窗口范围内（发现其问题只记录，不在这改）

## 合入

- 全部由 Codex 收口：审查通过后按 D → B → A → C 顺序合入，冲突由 Codex 处理
- 每个窗口合入前，Codex 先把最新 main 合并回该分支，避免最后集中爆炸

## 风险（一句）

四线并行最大的风险是范围越界和测试互踩；用目录隔离 + 合入前同步 main 兜住，代价是每轮多一次人工搬运。
