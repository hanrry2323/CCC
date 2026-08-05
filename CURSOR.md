# CCC 项目背景介绍（给 Cursor 的入口 · 2026-08-05）

> 你在本项目里是**了解/讨论/排查**角色，不是主线开发合入体。先读本文 + `.cursor/rules/loop-engineer-consensus.mdc` + `docs/INDEX.md` §0，再动手。

## 一、这是什么项目

**CCC = 自动化任务编排平台**：用 Markdown 任务卡作为唯一事实源，薄驱动 Engine 自动派发执行体（2017 上的 Claude Code）开发，看板/HTTP 网页/桌面壳作为人机界面。当前处于「自研期」：由 Codex 出卡驱动、验收、放行，目标是把整个「出卡 → 执行 → 验收 → 部署」链路自动化。

## 二、当前架构（2026-08-05，v0.70.0）

```
M1（你所在的机器，192.168.3.140）
└── /Users/apple/program/CCC = 开发副本（git → GitHub main）
      ├── server/   新栈后端（engine/board/web/kb/config/deploy）
      ├── desktop/  macOS Swift 桌面壳（CCCDesktop）
      ├── docs/     权威文档 + dispatch/ 任务卡
      └── scripts/  少量工具（new-card.sh / verify-shell.sh 等；旧 scripts/ 已归档）

Mac2017（生产节点，192.168.3.116）
├── /Users/fan/program/CCC = 生产副本（只 pull，不手改）
├── 三 launchd 服务：web-server(:7788) + engine + board-scheduler
├── 中继：6100(Anthropic) / 6102(OpenAI)，模型出口 flash/code
└── 执行体：Claude Code（Engine 自动拉起，走中继 6100）
```

**关键差异**（和旧栈不同，别按旧文档办事）：
- 没有 Hub :7777、没有 Board :7775、没有 relay.m1/hub-tunnel、没有 6+1 列 jsonl 看板
- M1 是写源；2017 是生产（只 pull）；开发走「Codex 出卡 → Engine 派发 → 2017 worktree 开发」
- OpenCode 已禁用（老板 2026-08-05）；执行体只有 2017 Claude Code
- 免登录：`CCC_WEB_AUTH_REQUIRED=0`，全部端点免鉴权直连

## 三、任务卡体系（核心概念）

- **任务卡 = 唯一事实源**：`docs/dispatch/TNN-slug.md`（如 `T67-deploy-race-guard.md`）
- 卡头元数据行：`> 关联：… · 执行体：… · 验收：… · 状态：… · 派发：… · 项目：… · 日期：…`
- **五态**：待分派 → 执行中 → 已回写 → 已关闭（失败打回 → 待分派重派）
- 看板是**派生视图**：`server/board/loader.py` 扫描卡 → `/board/*` API，不存数据不做决策
- **门禁**（`server/board/validate.py`，CI + pre-commit 双闸）：卡头字段齐全、状态合法、已验收卡（## 验收区 + ✅）必须已关闭（T67）
- 出卡模板：`scripts/new-card.sh`；索引：`data/cards/cards.index.jsonl`（运行时生成，勿提交）

## 四、开发流程（自研期标准链路）

```
Codex 出卡（含目标/红线/验收标准）→ push main
  → 2017 pull → Engine 自动派发（探活中继 → 拉起 Claude Code）
  → Claude Code 在独立 worktree ccc-dev-ws-tNN + 分支 codex/tNN-* 开发
  → 分步 commit+push → Codex 独立验收（pytest/swift/无头走查）
  → 合入 main → 2017 pull + 三服务重启 → 关卡
```

## 五、测试与验证

```bash
# 服务端
python -m pytest server/tests -q          # 全量回归
python -m server.board.validate docs/dispatch   # 卡头门禁
bash scripts/verify-shell.sh --skip-conversation  # 壳六场景 API 复验
ruff check server/

# 桌面
cd desktop && swift build && swift test

# 放行（在 2017 生产执行）
bash deploy/release.sh <commit> --card TNN
```

## 六、当前状态（2026-08-05）

- **已闭环上线**：T54~T67（命名规则/索引层/卡片组件/看板重构/对话即工作/异步派发/控制台/卡流/归档/自动 worktree/双壳对齐/历史卡规范化/误派防线）
- **待办（转整体联调）**：P0 静态资源并发加载 ERR_CONNECTION_RESET（M1→2017 41% 实测，SPA 白屏根因）；Nginx 实际安装；T50 全链路联调 + 稳定性压测 + 老板实测
- **看板**：72 已关闭 / 0 待分派 / 0 执行中 / 4 历史打回
- **完整路线**：`docs/roadmap.md` + qx-map `__archive__/decisions/ccc-前端四板块架构-定稿-2026-08-04.md`

## 七、硬红线（Cursor 必须遵守）

1. 不写 QuantHive 业务代码；不混双轨
2. 2017 生产副本只 pull 不手改；远程 worktree 不随意删
3. 不碰旧栈（scripts/ 归档、Hub :7777、6+1 列 jsonl、能力包）
4. 不代替 2017 Claude Code 做主线开发合入（你是了解/讨论/排查角色）
5. 无授权不删改归档目录（docs/archive/）
