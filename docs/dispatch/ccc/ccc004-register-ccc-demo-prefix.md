# 任务卡 ccc004 · register ccc-demo prefix cd（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-06

## 目标

在 CCC 新卡前缀体系注册 ccc-demo 项目，新增前缀 `cd`（映射 ccc-demo），使后续 `--project cd` 出的卡能通过命名门禁。

## 红线（先看）

1. 只改下述**两个**白名单文件，不碰其它文件（含不迁移/不重命名任何历史卡）。
2. 不直推 `main`；只 push 到分支 `codex/ccc004-register-ccc-demo-prefix`。
3. 禁止写 `## 机审区` / `## 验收区` / 置「已关闭」；不手改 2017 运行面。
4. 探针用 `server.board.validate` + `new-card.sh --dry-run`，不代跑全量业务 pytest。

## 范围

- `server/board/models.py`：`PREFIXES` 增加一行 `"cd": "ccc-demo"`（2 位小写字母，与现前缀同风格）。
- `docs/dispatch/T-mapping.md`：前缀表增加一行 `cd | ccc-demo | ccc-demo 项目（对应 ~/program/apps/ccc-demo）`。
- 禁止改动其它任何文件 / 模块 / 运行配置。

## 步骤

1. 先 Read 本卡全文与 `docs/dispatch/T-mapping.md`、`server/board/models.py` 相关段落，确认当前前缀表。
2. 在 worktree 内修改上述两个白名单文件（`cd` → ccc-demo）。
3. 验证（探针，非阻塞门禁自证）：
   - `python3 -m server.board.validate docs/dispatch` → 无新增 error（`cd` 前缀被认可）。
   - `bash scripts/new-card.sh --project cd --title probe --slug probe --dry-run` → 能生成卡（dry-run 即可，勿真写）。
4. commit + push 到 `codex/ccc004-register-ccc-demo-prefix`（勿直推 main）；卡头状态改「已回写」并填回写区（实现说明 / 测试结果 / push 证据 commit hash）。
5. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「验收看板」终验。

## 验收标准

1. `server/board/models.py` `PREFIXES` 含 `"cd": "ccc-demo"`。
2. `docs/dispatch/T-mapping.md` 前缀表含 `cd` 行。
3. `python3 -m server.board.validate docs/dispatch` 无 error。
4. `bash scripts/new-card.sh --project cd --slug probe --dry-run` 出卡成功。
5. `git diff origin/main...HEAD` 仅含上述两个白名单文件。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人工终验听「验收看板」后写 `## 验收区`+已关闭。

## 回写区

**执行体**：OpenCode · 日期：
