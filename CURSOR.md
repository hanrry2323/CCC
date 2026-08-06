# CCC 项目背景介绍（给 Cursor 的入口 · 2026-08-06）

> 你在本项目里是**难度开发突击手**（qx-map W7）：有难度写码/修 bug、复杂排查收口、老板点名硬任务。日常开发默认 OpenCode / 注册表 CLI；你不抢日常队列。先读本文 + `.cursor/rules/loop-engineer-consensus.mdc` + `docs/INDEX.md` §0，再动手。

## 一、这是什么项目

**CCC = 自动化任务编排平台**：Markdown 任务卡 = 唯一事实源；薄驱动 Engine 按注册表派发执行体（Claude Code / OpenCode）；**人机实时面 = HTTP 看板/运维**（`:7788`）。自研期 Codex 出卡、验收。Cursor 在明确突击卡 / 老板点名时直接开发，终验仍归 Codex。

**主路径**：M1 上任意已注册能力的 IDE（Claude Code / OpenCode / Cursor 突击）= 开发中枢；打开 CCC 仓即可开发。**Desktop 暂缓**，功能以 HTTP 页为准。  
Claude Code / OpenCode 开仓双模式（中枢陪聊 vs Engine 执行体）SSOT：[`CLAUDE.md`](CLAUDE.md)「开仓作战卡片」；工作区必须是 `/Users/apple/program/CCC`。

## 二、当前架构（2026-08-06，v0.70.0）

```
M1（你所在的机器，192.168.3.140）
└── /Users/apple/program/CCC = 开发副本（git → GitHub main）
      ├── server/   新栈后端（engine/board/web/kb/config/deploy）
      ├── desktop/  macOS 壳（暂缓，非主路径）
      ├── docs/     权威文档 + dispatch/ 任务卡
      └── scripts/  少量工具（new-card.sh / verify-shell.sh 等；旧 scripts/ 已归档）

Mac2017（生产节点，192.168.3.116）
├── /Users/fan/program/CCC = 生产副本（只 pull，不手改）
├── 三 launchd 服务：web-server(:7788) + engine + board-scheduler
├── 中继：6100(Anthropic/flash) / 6102(OpenAI/code)
└── 执行体：Claude Code 与 OpenCode（注册表可后台 CLI，卡头绑定）
```

**关键差异**（和旧栈不同，别按旧文档办事）：
- 没有 Hub :7777、没有 Board :7775、没有 relay.m1/hub-tunnel、没有 6+1 列 jsonl 看板
- M1 是写源；2017 是生产（只 pull）；开发走「出卡 → Engine 派发 → worktree」
- OpenCode **可用**（与 Claude Code 并列；模型档 flash vs code）
- 免登录：`CCC_WEB_AUTH_REQUIRED=0`，全部端点免鉴权直连
- 看板实时进度看 HTTP，不依赖 Desktop

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
  → 2017 pull → Engine 按卡头绑定派发（Claude Code 或 OpenCode）
  → 独立 worktree ccc-dev-ws-tNN + 分支 codex/tNN-*
  → 分步 commit+push → Codex 独立验收
  → 合入 main → 2017 pull + 三服务重启 → 关卡
```

人看进度：浏览器打开 `http://192.168.3.116:7788` 看板（执行中卡可显示 worktree 未提交改动数）。

## 五、测试与验证

```bash
# 服务端
python -m pytest server/tests -q          # 全量回归
python -m server.board.validate docs/dispatch   # 卡头门禁
bash scripts/verify-shell.sh --skip-conversation  # 壳六场景 API 复验
ruff check server/
```

权威链：`docs/INDEX.md` §0 · `STARTUP-BRIEF.md` · `.cursor/rules/loop-engineer-consensus.mdc`。
