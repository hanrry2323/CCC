# 任务卡 ccc003 · E2E 派发收单防假成功与技术债收口（Claude Code 执行）

> 关联：E2E联调技术债 2026-08-06 · 执行体：Claude Code · 验收：Codex · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-06

## 目标

把 ccc001/ccc002 E2E 踩到的三处 Engine/出卡坑收成可验收修复：① OpenCode 派发模板与 example 注册表对齐（核对已部分落地的 `--auto --dir {worktree}` 模板并补防回归断言）；② Engine 收单不再只看 exit 0，防 sandbox 假成功（OpenCode exit 0 却无产物）；③ `new-card.sh` 出卡先刷新卡片索引再 validate，修复「索引缺失」误删新卡。

## 红线（先看）

1. 禁止改动 `desktop/`、`deploy/`、`server/tests/conftest.py` 与 2017 运行面（生产 `executors.json` / launchd / `:7788`）——运行面只核对登记，不落地改动。
2. 禁止改动 Engine 状态机五态与契约（只加收单核验门，不改「待分派 → 执行中 → 已回写/打回 → 已关闭」语义）。
3. 禁止改动其它任务卡；仅限白名单文件 + 本卡（卡头状态 + 回写区）。
4. 禁止把派生数据（`data/cards/cards.index.jsonl`、`docs/dispatch/cards.index.jsonl`、`web/data/board.js`）当硬依赖——它们是可重建的缓存，新增/刷新索引须走 `server.board` 逻辑，禁止手工改缓存内容。

## 范围

白名单式（只此几项可触碰）：

- `server/engine/main.py`：收单逻辑——`returncode == 0` 后追加产物核验，无产物 → 打回。
- `server/tests/`：新增 Engine 收单防假成功单测（mock Popen）；`test_skeleton.py` 增加 OpenCode 模板防回归断言。
- `scripts/new-card.sh`：写卡后、validate 前先刷新卡片索引（走 `server.board` 导出/加载逻辑），消除「索引缺失」误删。
- `server/config/executors.example.json`：仅在核对发现模板缺口时补齐（当前已含 `--auto --model loop/code --dir {worktree}`，一般只读核对）。
- 本卡 `docs/dispatch/ccc/ccc003-*.md`：仅卡头「状态」字段 + 「回写区」。

不在上列的任何改动 = 越界，验收打回。

## 步骤

1. 核对 `server/config/executors.example.json` 中「当前绑定 = OpenCode」的可后台 CLI 行：参数模板须同时含 `--auto` 与 `--dir {worktree}`；并在回写区登记 2017 生产 `executors.json` 同名行核对结果（一致 / 差异清单）。
2. 在 `server/tests/test_skeleton.py::TestExecutorsExample` 增加防回归断言：当前绑定=OpenCode 的可后台 CLI 行，参数模板必须同时含 `--auto` 与 `--dir {worktree}`，缺一即 fail。
3. 修改 `server/engine/main.py` 收单路径（当前 `returncode == 0` 直接置已回写）：exit 0 后追加产物核验——worktree 存在时 `git -C <worktree> log origin/main..HEAD --oneline` 至少 1 个新 commit，或卡头状态已为「已回写」；两者皆无 → 返回打回问题清单「exit 0 但无产物（疑似 sandbox 假成功）」，不回写。
4. 新增单测覆盖「returncode 0 + 无产物 → 打回」「returncode 0 + 有产物 → 已回写」两条路径（mock Popen / 临时 worktree）。
5. 修改 `scripts/new-card.sh`：validate 前先刷新卡片索引（等价调用 `server.board` 的 load/export 使新卡入索引），再跑 validate；保证已有索引时新增卡不再触发「索引缺失」误删。
6. 回归：`pytest server/tests/ -q`、`ruff check server/`、`python3 -m server.board.validate docs/dispatch` 全绿。

## 验收标准

1. **模板对齐**：example 中当前绑定=OpenCode 的可后台 CLI 行参数模板同时含 `--auto` 与 `--dir {worktree}`；防回归断言测试通过（`pytest server/tests/test_skeleton.py -q`）；回写区登记 2017 生产 `executors.json` 核对结果。
2. **收单防假成功**：`server/engine/main.py` exit 0 路径含产物核验；单测证明「0 退出码 + 无产物 → 打回」「0 退出码 + 有产物 → 已回写」。
3. **出卡先索引**：实测 `scripts/new-card.sh` 在有旧索引时出卡一次成功，validate 通过且新卡进入索引（不再「索引缺失」误删）。
4. **全量门禁绿**：`pytest server/tests/ -q`（新增用例 + 既有不回归）、`ruff check server/` 零告警、`python3 -m server.board.validate docs/dispatch` 通过。
5. **push 证据**：改动 commit+push 到 `codex/ccc003-<slug>` 分支（勿直推 main）；卡头「已回写」+ 回写区三要素（实现说明 / 测试结果 / push 证据）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据。

## 回写区

**执行体**：Claude Code · 日期：2026-08-06

### 实现说明

1. **模板对齐（步骤 1）**：`server/config/executors.example.json` 当前绑定=OpenCode 的可后台 CLI 行（第 27-33 行）参数模板已含 `--auto` 与 `--dir {worktree}`，无需改动。2017 生产 `executors.json`（`/Users/fan/program/CCC/server/config/executors.json`）同名 OpenCode 行模板一致：`run --auto --model loop/code --dir {worktree} "请严格按任务卡 …"` —— **一致，无差异**。
2. **防回归断言（步骤 2）**：`server/tests/test_skeleton.py::TestExecutorsExample` 新增 `test_opencode_cli_requires_auto_and_dir_worktree`：当前绑定=OpenCode 的可后台 CLI 行，参数模板必须同时含 `--auto` 与 `--dir {worktree}`，缺一即 fail。另修复同文件 `CONTRACT_ROLES`（开发执行体可后台 CLI 由 1 调整为 2 条，对齐 ccc002 加入 OpenCode 后的注册表）与 `test_engine_dispatch.py::test_example_registry_loads`（entry 数 5→6，补 OpenCode 模板断言）——两条均为既有存量断言，与 example JSON 现状不符，已一并收口走绿。
3. **收单防假成功（步骤 3/4）**：`server/engine/main.py` 收单路径 `returncode == 0` 后追加产物核验——仅 worktree 派发路径生效：`_worktree_has_new_commit()`（`git -C <worktree> log origin/main..HEAD --oneline` ≥1 新 commit）**或** `_card_is_written_back()`（卡头状态已「已回写」）；两者皆无 → 打回问题清单「exit 0 但无产物（疑似 sandbox 假成功）」，不回写。无 worktree 的简单执行体走旧行为（避免误伤 echo 等）。新增 `test_engine_main.py::TestRunOnceFakeSuccessGuard` 三条单测覆盖「0+无产物→打回」「0+新 commit→已回写」「0+卡头已回写→已回写」；同时把既有 `test_run_once_with_worktree_enabled` 改为在 worktree 内产出真实 commit（旧行为=无产物也回写，与收单防假成功契约冲突，已按新意图改）。红线 2：未动五态状态机，只加收单核验门。
4. **出卡先索引（步骤 5）**：`scripts/new-card.sh` 写卡后、validate 前先调 `server.board.loader.load_dispatch_cards($TARGET_DIR)` 刷新卡片索引（走 board 逻辑，未手改缓存），消除已有索引时新卡未入 index 触发「索引缺失」误删。实测：旧索引存在时出卡 `ccc101-anti-fake` 一次成功，validate 通过且进入索引；反向验证旧行为对账报「索引缺失」。

### 测试结果

- `pytest server/tests/test_skeleton.py -q`：28 passed
- `pytest server/tests/ -q`：唯一失败为**既有存量** `test_http_api.py::TestStaticHosting::test_board_page_still_accessible`（`/data/board.js` 401，本机缺 `web/data/board.js` 派生命成物；stash 验证改动前即失败，与 ccc003 无关且不在白名单，属超范围）——本卡改动引入回归 0，新增用例全绿。
- `ruff check server/`：本卡改动文件 0 告警；3 条既有 UP038（`kb/indexer.py`×2、`test_http_api.py`×1）为改动前存量，不在白名单。
- `python3 -m server.board.validate docs/dispatch`：通过（85 张卡，0 error，82 条旧卡迁移提示）。红线 4：索引经 `server.board` 刷新，未手改缓存内容。

### push 证据

- 分支：`codex/ccc003-engine-anti-fake-success-and-template-align`
- 改动文件：`server/engine/main.py`、`server/tests/test_skeleton.py`、`server/tests/test_engine_dispatch.py`、`server/tests/test_engine_main.py`、`scripts/new-card.sh`、本卡（卡头状态 + 回写区）
- commit：见本次 push 记录（后续补充 commit id）
