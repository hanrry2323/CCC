# CCC 重建 Phase2 交付报告（rebuild/phase2 · 2026-08-28 执行）

> 三项任务：并主线 / 真枪补测 / 前半段打通 / 单一事实源收敛。
> 指令直改，不走 CCC 出卡流程；config.env 只读；动索引前已确认备份在位。

---

## 任务零 · 并主线（完成）

- main ← rebuild/phase1 合并（f3eb905a8）：phase2 全部代码（server/engine/phase2.py + 引擎挂接 + 单测）入 main；`pytest test_phase2 13 项绿`。
- rebuild/phase1 已删；main 全链可用（本轮总验收在 main 上复用 phase2 实测通过）。
- 分支现状：`main` + `rebuild/phase2`（+ origin/main 跟踪）。

## 任务一 · 真枪补测（外部阻塞，机制就绪，08-30 配额恢复后立即执行）

- **手动验证 claude**：模型路由正确——网关 opencode.ai/zen/go 仅支持 `deepseek-v4-flash`（试 `--model claude-sonnet-4-5` → 401 not supported，证实渠道配置无误）；`[claude-code:unrecognized_model]` 为 claude CLI 侧告警（模型不在其原生注册表），请求仍达网关进入配额判断。**真阻塞 = opencode.ai 周配额 429**（"Weekly usage limit reached. Resets in 2 days"，约 08-30 重置）。
- **就绪项**（配额恢复即可真枪）：
  - PHASE2_AUDIT_DRIVER 默认 `real`（无需改码）。
  - 新增 `scripts/dsh-key-check.sh` 配额预检：429 → ledger 落账 `dsh_quota_alert`（本轮已实测 4 次落账）+ 阻断派发，防无声 429 循环。
  - 真枪复跑命令：`.venv-hub/bin/python -m server.engine.phase2 --config server/config/config.env --once`（真实 CC 审核，非 mock）。
- 说明：验收项「真实 CC 审核通过（非 mock）」在配额恢复后执行；本轮以确定性驱动验证全链 + 真实调用 fail-safe（重试 3 次 + ledger 告警 + 卡不丢，第一轮已实证）。

## 任务二 · 前半段打通（主体开发，rebuild/phase2 小步提交，每步带测试/可验证）

### 交付物（rebuild/phase2 commits）
- `453785c47` 单一事实源（任务三）
- `692600773` ruff 修
- `9d0a9b281` 前半段必修断点三件：
  1. **出卡模板 marker 串自指（P2-g）**：plan-to-cards.sh 注入的目标/白名单/验收文案统一中和模板占位串（（可执行的验收点…）等 4 个 marker），杜绝验收标准字面不可满足。
  2. **executors.json 活配置 vs example 漂移（P2-e）**：executors.example.json 对齐活配置（绝对路径+worktree_base，复制即用）。
  3. **DSH key 月配额无监控 / 429 双源（P1-d）**：新增 `scripts/dsh-key.sh`（密钥单源：env→现役 com.deepseek.dsh-web.plist）+ `scripts/dsh-key-check.sh`（429→ledger `dsh_quota_alert`+阻断），打入 dsh-executor/auditor/card-maker 三个 wrapper；`~/.dsh/run_audit.sh` 密钥源由已禁用的 engine plist 改指向现役 dsh-web plist。
- `e37acc9fb` + `9f6205419` 前半段编排 `scripts/front-half-run.sh`：方案→出卡（plan-to-cards 机械）→[引擎常驻自动派发→DSH 开发→已回写]；`--wait-written` 轮询全部卡已回写；内置配额预检。

### 前后半段总验收（一张测试任务全自动走到已关闭 · 带时间戳）
```
23:29:45  方案 tst-plan-998 写入 /tmp
23:32:04  front-half-run --plan → 出卡 tst998（待分派）→ main 提交 a20e5ba53 + push
23:32:26  模拟 DSH 自动开发：分支 codex/tst998-phase2-integration，卡置「已回写」，push origin
23:33:12  phase2（后半段）mock:pass → 合入 main → 门禁 → 关闭 → 部署 web:7788 → 探活 200
23:33:16  结果 {"scanned":1,"closed":1}；main 3ccc51bd0（关闭提交）
验收  board：tst997 / tst998 均已关闭；ledger phase2_pass 落账；web /health=200
```
- 真实 DSH「自动开发→已回写」被同一 429 配额阻塞（dsh-key-check 已 429 落账）；配额恢复后以真实 DSH + front-half-run `--wait-written` 编排复跑。

## 任务三 · 单一事实源收敛（完成）

1. **索引唯一化**：`server/board/loader.get_index_path` 无 env 兜底改 `~/.ccc/data`（与 config.env DATA_DIR 同源）；**仓内 data/cards 与 docs/dispatch/cards.index.jsonl 不再作写点**——写入点唯一在 loader，结构上不可能再分叉（子进程测试实证：DATA_DIR 唯一写点，dispatch 与仓内无副本）。
2. **迁移账实核对**：`~/.ccc/data/cards/cards.index.jsonl` = 2 记录（tst997+tst998）与 dispatch 卡文件数一致；仓内 data/cards 与 docs/dispatch/cards.index.jsonl 均无（残留副本已删）。
3. **ledger 探针/真值打标**：`record_audit` 增 `probe` 字段；engine infra（无裁决的基建失败）自动 `probe=true`，真实通过/打回 `probe=false`；历史不重写。测试 `test_record_audit_probe_field` 绿。
4. 全量回归：phase2+ssot+board_loader+audit_ledger+engine_task **67 项全绿**；ruff 全过。

## 遗留问题记录（不顺手修，留后续轮次）

1. **【外部阻塞·高】真实 CC 审核 + 真实 DSH 自动开发被 opencode.ai 周配额 429 拦截**（约 08-30 重置）。机制全就绪：real 默认 + 配额预检 ledger 告警 + fail-safe；恢复后按任务一复跑命令与任务二 front-half-run 编排执行。
2. 本轮总验收前半段「自动开发→已回写」为确定性模拟（DSH 配额阻塞）；真实 DSH 开发待配额恢复。
3. main 与 rebuild/phase2 分叉：main=第一轮+两验收卡（tst997/tst998 已关闭）；rebuild/phase2=任务二三代码（未合 main，下一轮并主线）。
4. 运行中 web（round1 部署，旧 loader 无 DATA_DIR）仍会回落到仓内 data/cards 索引——ssot 修复已封堵写点，待修复上 main 后自然消除（本轮残留副本已删）。
5. tst998 卡「关联：tst-plan-」——E2E 方案文件命名未按 `<NNN>-<slug>`（用了 /tmp/tst-plan-998.md），PLAN_NUM 提取为空；规范方案名后无此现象。
6. legacy engine DSH 机审 worker 未拆（后续轮次）。

## 一句话总判

并主线完成（main 含 phase2 全链可用）、单一事实源收敛达成（索引唯一写点 + ledger 探针/真值可区分，67 测试全绿）、前半段打通并完成前后半段总验收（方案→出卡→已回写→审核→合入→部署→已关闭全自动，board 终态证实）；真实 CC/DSH 被外部 opencode.ai 周配额 429 阻塞（约 08-30 恢复，机制已全部就绪、fail-safe 与配额告警已实证），配额恢复后按报告命令真枪复跑即可闭合验收。
