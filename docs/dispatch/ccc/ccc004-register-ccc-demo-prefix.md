# 任务卡 ccc004 · register ccc-demo prefix cd（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-06

## 目标

在 CCC 新卡前缀体系注册 ccc-demo 项目，新增前缀 `cd`（映射 ccc-demo），使后续 `--project cd` 出的卡能通过命名门禁。

## 红线（先看）

1. 只改下述**两个**白名单文件，不碰其它文件（含不迁移/不重命名任何历史卡）。
2. 不直推 `main`；只 push 到分支 `codex/ccc004-register-ccc-demo-prefix`。
3. 禁止写 `## 机审区` / `## 验收区

**合入批准** · 日期：2026-08-07
- 判定：通过
` / 置「已关闭」；不手改 2017 运行面。
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

## 机审区

**机审：通过** · Claude Code（2017 机审席）· 2026-08-06

独立取证（不采信回写区摘要），证据如下：
- 分支 `codex/ccc004-register-ccc-demo-prefix`，`git log origin/main..HEAD` 恰 2 commit（`7ae942b1` feat + `4b26f0c3` 回写补记）。
- `git diff origin/main...HEAD --stat` 仅 3 文件：两个白名单文件 + 本卡自身（状态/回写区）；无越界改动（符合范围/红线）。
- `server/board/models.py` `PREFIXES` 含 `"cd": "ccc-demo"` ✔（验收 1）
- `docs/dispatch/T-mapping.md` 含 `cd | ccc-demo | ccc-demo 项目（对应 ~/program/apps/ccc-demo）` ✔（验收 2）
- `python3 -m server.board.validate docs/dispatch` 复跑无 error，仅既有 T 前缀提示 ✔（验收 3）
- `bash scripts/new-card.sh --project cd --title probe --slug probe --dry-run` 复跑 exit 0，生成 `docs/dispatch/cd/cd001-probe.md`，命名门禁认可 `cd` ✔（验收 4）

备注（不阻塞本卡）：`/Users/fan/program/CCC` 主仓工作树遗留未跟踪 `server/config/executors.json.bak-two-tier`（2547B，21:39），为部署配置备份、与本卡无关，请中枢另行清理。
