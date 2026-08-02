# 窗口 B · 后端与引擎修复 — 完成报告

> 日期：2026-08-01 · 分支：`codex/ws-2-backend`（12 commits，基于 main d94796b）  
> 任务书：[`docs/dispatch/task-B-backend-engine.md`](task-B-backend-engine.md)  
> 格式：发现 → 动作 → 证据 → 风险

---

## 基线

- 工作区 `ccc-ws-2-backend`（git worktree，`codex/ws-2-backend`，与 main 同 HEAD，干净）
- 测试基线：`tests/scripts/` **14 红** · `scripts/tests/` 363 绿 · ruff 基线存量 37（UP045 等，本地 ruff 比 CI 钉版 0.8.6 新，非 CI 阻断）
- 文档基线：`loop-engineer-authority.md`（2026-07-31 最小可跑通 v1.2）为 SSOT；**released=自动（LPSN L）**，人工确认在 `intent_stable`（S）

---

## A. 过期测试（修 · 契约已变，测试未同步）

### A1 `test_acceptance_gate.py::test_salvage_refuses_without_acceptance`
- **发现**：断言 `try_complete_if_gates_satisfied() is None`；v0.66.0 起验收失败返回 `{status:"acceptance_failed", reason}` 上抛 Engine `acceptance_fail_budget`（防 salvage 拒绝空转）。
- **动作**：断言更新为新契约（`acceptance_failed` + `missing_acceptance`）。
- **证据**：`39ba916`；测试绿。

### A2–A5 transfer_gate skill_ref/prompt_ref 硬切换（8 用例）
- **发现**：`c54e1f2` 硬切换后 gate 必填 `skill_ref`/`prompt_ref`；测试载荷仍用旧 `executor_intent` → 被拒（`missing_skill_ref`）。`test_intent_probe_lpsn`×5、`test_hygiene_transfer_acceptance`、`test_gate_rule_fitness`、`test_script_seed` 共 8 条。
- **动作**：载荷按卡型补 `skill_ref`/`prompt_ref`（dev→write-code、探针→script-seed、ops→ops）；executor 断言同步新架构（ops 卡 → `cli`，探针卡 → `python`）。
- **证据**：`9007aaf`；相关测试全绿。

### A6 `test_executor.py::test_long_prompt_uses_temp_file`
- **发现**：断言 `--file in cmd`；R-14（`e6bb3cd`）已删 `--file`，prompt 走 stdin，临时文件用后即删。
- **动作**：断言改为「命令无 `--file` + 执行期间确实写入 `prompt-*.md`」。
- **证据**：`87fde3b`；测试绿。遗留：`_executor.py` 长 prompt 写临时文件但命令未引用（prompt 丢失），该路径仅死代码 `opencode-pool` 使用，**暂缓**（见风险）。

### A7 `test_hang.py` retry counter ×3
- **发现**：v0.66 计数器实现拆至 `engine.hang_support`；测试 monkeypatch `engine.hang._HANG_COUNTER_FILE`/字典 对委托路径无效，且 corrupt-file 用例会读到真实 `~/.ccc/engine-hang-retries.json` 残留。
- **动作**：monkeypatch 目标改为 `engine.hang_support`。
- **证据**：`2de9f62`、`ea6e77a`、`f380dc2`；测试全绿。

---

## B. 过期规则（修）

### B1 `references/authority-patrol.jsonl` `hub-voice-smoke-rules`
- **发现**：卡要求 hub_voice.py 含旧标记 `executor_intent: python`；v0.66 已改 `skill_ref` → 假红（`test_patrol_green_on_clean_tree` / `archives_stale_alerts` 连带红）。
- **动作**：`must_contain` 改 `skill_ref`。
- **证据**：`fac40b2`；2 个 patrol 测试转绿。

---

## C. 状态机/验收门缺口（修 · 用户拍板方案 B）

### C1 reviewer/tester 直接挪 verified 的崩溃窗口
- **发现**：`reviewer.py`(305/1663/1695/1798) + `tester.py`(504/610) 写 PASS verdict 后直接 `move_task(testing→verified)`；正常流程被 `_ensure_task_in_testing` 拉回，但 **Engine 在拉回前死亡 → 重启后 kb 门自动 released，绕过 tester+pytest**。违反「verify 一扇门 · 唯一移动权归 gates」（审计 2026-07-24 类别④ #8）。
- **动作（方案 B）**：删 5 处角色直接 move；`gates.py` testing→verified 为唯一移动方（verdict + tester + pytest 后）；`_ensure_task_in_testing` 降级为防御兜底；docstring 同步。CLI 单独 reviewer/tester 不再挪列（更符合副闸语义）。
- **证据**：`6db8980`；`test_gates/test_engine_kb_gate/test_reviewer_*` 等 77 个 gate 相关测试全绿。**人工确认门口径**：released=自动 与 docs 一致（authority / CONTROL / GO-LIVE / golden-path 均证），人工确认在 S（`ccc-mind-update --stable`）已在位。

---

## D. 模块级状态 / 错误边界（修）

### D1 `chat_server/auth.py` `_auth_failures` 无界 defaultdict
- **发现**：滑动窗口只修剪当前 IP 桶，轮换 IP 攻击者让字典无界增长（审计 类别② M3）。
- **动作**：每 100 次 `check_auth` 全局清扫窗口外的桶。
- **证据**：`23b1889` + 新测试 `test_chat_server_auth.py`（4 例）。

### D2 `transfer_gate.py` 误导性向后兼容死代码
- **发现**：194-198 注释声称 executor_intent→skill_ref 映射，实为 `pass`；validation 在映射前已硬拒旧格式。
- **动作**：删死代码，留硬切换口径注释（迁移映射归 `resolve_skill_ref`，epic 写路径）。
- **证据**：`baea8be`；测试绿。

### D3 裸异常盘点（结论：不是问题）
- **发现**：全库裸 `except`/`pass` 多为**有意兜底**（有注释：`_product_fanout` JSON 兜底、`_cost_telemetry` 遥测不阻塞、`opencode-exec` warmup 失败继续、`transfer_gate` 可选垃圾分类器）。
- **动作**：无。仅报告。

### D4 `_product_fanout.py` 未 import `sys`（新发现 · 修）
- **发现**：ruff F821 → `_epic_default_executor` 内 `sys.path.insert` 抛 NameError → except 吞掉 → **恒返回 opencode**，script-seed/ops skill 声明在 fanout 上失效（机械探针卡仍 opencode 易 hang）。这直接抵消 D2/C1 的 executor 链修复。
- **动作**：补 `import sys` + 回归测试。
- **证据**：`28d8888`；`_epic_default_executor` 实测 script-seed→python、ops→cli。

---

## E. 千行级大模块安全拆分候选（结论：全部暂缓）

| 模块 | 行数 | 候选 | 结论 |
|------|------|------|------|
| reviewer.py | 1835 | verdict I/O 抽 `_verdict_io.py` | 暂缓（收益<风险） |
| _board_store.py | 1507 | JSONL 序列化抽离 | 暂缓（原子写已加固：mkstemp+fsync+dir-fsync） |
| gates.py | 1000 | pytest/fail-handling 抽离 | 暂缓 |
| dev.py / hang.py / active_tasks.py | — | 已拆 dev_salvage / hang_support | 无需 |

engine/ 已重度拆分（`ccc-engine.py` 373 行）；剩余拆分风险>收益，符合任务书「能不动就不动」。

---

## 验证

| 项 | 结果 |
|----|------|
| `pytest tests/scripts/`（CI job 1） | **全绿**（原 14 红已清） |
| `pytest scripts/tests/`（CI job 3） | **363 绿** |
| `ruff check scripts/ tests/` | 我的改动文件全过；存量 37 为本地 ruff 版本漂移（UP045）非 CI 阻断 |
| `bash scripts/ccc-self-check.sh` | **自检全部通过** |
| 改动相关测试（11 文件） | 104 例全绿 |

## 风险 / 遗留

1. **C1 行为变更**：CLI 单独 `ccc-board.py reviewer/tester` 不再挪列（留 testing）。Engine 主路径不受影响（gate 是唯一移动方）。e2e（`test_green_pipeline_e2e` 等）未在本地跑（需 live LLM 环境），断言均以 gate 产出 verified 为准，理论兼容。
2. **`_executor.py` 长 prompt 丢失（legacy）**：`OpenCodeExecutor.execute` 写临时文件但 `build_opencode_run_cmd` 未引用（R-14 后）。该路径仅死代码 `opencode-pool` 使用，**暂缓**；产线走 `opencode-runner.sh → opencode-exec.py`（stdin 正确）。
3. **`hygiene-python` patrol 卡语义漂移**：`must_contain` 仍查 `resolve_executor_intent`+`python`（探针仍绿），但卫生卡实际走向 ops→cli / script-seed→python。未改（避免 patrol churn）；建议后续把该卡标记改为 `resolve_executor_from_skill`+`python`。
4. **`CONTROL.md` 已同步**（`467433c`）闭环步骤为 verify 一扇门；`authority-patrol.jsonl` 之外的文档未逐篇核对。

## 提交清单（12 commits，仅本分支）

```
39ba916 test(acceptance)   A1
9007aaf fix(transfer)      A2-A5 + resolve_executor_from_skill 解析修复
87fde3b test(executor)     A6
2de9f62 / ea6e77a / f380dc2  A7
fac40b2 fix(patrol)        B1
6db8980 fix(gates)         C1（gate 唯一移动权）
23b1889 fix(auth)          D1
baea8be fix(transfer)      D2
28d8888 fix(fanout)        D4
467433c docs(control)      状态机文档同步
```
