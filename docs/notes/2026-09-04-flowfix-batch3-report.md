# 2026-09-04 Flowfix Batch 3 报告

## 结论

批次三 7 项修复已落地，分 4 笔语义化提交逐笔推送 `origin/main`。最终代码验证：

- `python3 -m pytest server/tests/ -q`：全量通过（末次运行通过）。
- 测试前后 `git status --porcelain` 快照一致：测试运行期间无新增工作区写入。
- `.venv-hub/bin/ruff check`：所有本批次修改的 Python 文件通过。
- `bash -n scripts/plan-to-cards.sh`、`bash -n scripts/new-card.sh`：通过。
- `scripts/plan-to-cards.sh docs/projects/clw/plans/002-clwarp-v020-rebuild.md --dry-run`：输出 `project=clw slices=5` 及完整计划卡清单。
- 最终 `HEAD` 与 `origin/main` 一致；两者均为 `80a7a1aae272868f9a1d634a679560f8b2f0e790`。

## 逐项证据

### 1. 测试隔离加固

涉及 `server/tests/conftest.py` 及目标测试/HTTP 测试：

- `conftest.py` 的 autouse fixture 对真实 `docs/dispatch` 的 `Path.open` 写模式、`write_text`、`write_bytes`、`unlink`、`mkdir`、`replace`、`rename` 统一抛错。
- `test_board_scheduler.py` 将 dispatch 复制到 `tmp_path`；HTTP API 测试将 dispatch 复制到临时 Git 仓库，并将 `_DISPATCH_DIR`、仓根指向临时仓；PromptInjection 测试改用非禁前缀临时卡。
- 其余目标测试均以 `tmp_path`/临时 Git 仓为写入环境；真实路径仅用于读取脚本/模板或只读断言。
- 复现命令：`python3 -m pytest server/tests/ -q`。
- 独立快照验证：测试前后 `git status --porcelain` 排序 diff 为空。

### 2. A4 docgate 空格勾选

- `server/board/docgate.py:258` 合法集合删除独立空格，并与 `server/engine/observer.py:1213` 对齐为 `是/否/有/无/x/X/✓/√`。
- `server/tests/test_docgate_q1.py` 新增 `test_blank_checkbox_choice_is_rejected`，验证 `[ ]` 被拒。

### 3. A5 禁卡过滤

- `server/engine/card_gate.py:114-122` 的 `validate_card` 复用 `server.board.registry.forbidden_prefixes()`；`enforce_card_gate` 在 DSH/状态判断前拒绝禁前缀并写 ledger/alert/作废状态。
- `server/engine/store.py:183-214` 的 `FileBoardStore.list_work` 同步过滤 forbidden 前缀。
- `server/tests/test_card_gate.py` 新增手工 `ccc` 卡被拒、store 不入池定向测试。

### 4. A1 真实批注落实

- `server/engine/main.py:2697` 起删除默认 `annotation_body="无批注，无需落实。"`。
- 使用 `server.board.annotation.classify_annotation` 判定 REAL；REAL 批注而结果缺 `批注落实` 段时返回失败原因 `批注未落实`，不代写占位内容。
- `server/tests/test_writeback_gate.py` 覆盖 NONE 不补占位句、REAL 缺段打回、REAL 有段成功三条路径。

### 5. C-7 origin 判定与补推

- `server/engine/phase2.py:98-106` `_branch_in_main` 默认以 `origin/main` 为基准。
- `merge_branch_to_main` 合入本地 main 后立即 `git push origin main`；push 失败返回 `PUSH_NEEDS_RETRY`，调用方保留已回写并进入 infra 冷却，后续轮次重试。
- `server/tests/test_phase2.py` 覆盖 origin/main 判定及 push 失败可重试标记。

### 6. C-5 冲突熔断

- `server/engine/phase2.py:750-808` 增加同卡 `conflict_strikes` sidecar 计数；冲突文件摘要留在原因中；第二次冲突返回 `CONFLICT_CIRCUIT_OPEN`，调用方自动打回且不再重跑 LLM 机审。
- `server/engine/runtime_state.py:85-106` 支持写入 `conflict_strikes`。
- `server/tests/test_phase2.py` 覆盖连续两次冲突熔断。

### 7. A2 骨架竞态

- `scripts/plan-to-cards.sh:111-133` 增加批量失败显式作废+commit+push；`135-207` 通过 `CCC_SKIP_GIT=1` 先完成全部本地生成与内容注入，后续再统一校验/提交/推送。
- 失败路径不再 `rm -f` 假回滚已推送卡。
- 增加并验证 `--dry-run` 计划卡清单模式。
- `scripts/new-card.sh` 支持 `CCC_SKIP_GIT=1`，供批量链跳过单卡原子提交。

## 提交记录

1. `d721933d5 fix(test): isolate dispatch fixtures and harden doc gate`
2. `445952a84 fix(gate): block forbidden prefix cards and require real annotation`
3. `0773dbe7f fix(phase2): retry pushes and circuit-break merge conflicts`
4. `32b6f3954 fix(script): generate all plan cards locally before commit/push`

## 运行面收口

代码和报告提交推送完成后，最后执行引擎重启：

```sh
launchctl kickstart -k gui/$(id -u)/com.ccc.engine
```

重启后核验新 PID 与心跳；核验结果追加在本报告末尾。

## 复核备注

批次三续跑开始时工作区已有上述范围内的半成品改动；本次先核对后修正，并未 checkout 丢弃。前次半成品曾使 PromptInjection 测试使用禁用 `ccc` 前缀而被新 A5 门禁拒绝，也使 API 测试直接触碰真实 dispatch；两处均已改为临时/非禁前缀夹具。