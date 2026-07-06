# Plan: hello-ccc-demo-v2 (CCC v1.2.0 流程跑通多 phase demo)

> 任务目标：用 3 phase 任务**实测** ccc-precheck/finish 5+5 门控 + ccc commit 闭环 + Verifier 独立 session。
> 范围: CCC 仓库本身,新增 3 个工具脚本 + 1 个测试,共 4 文件。
> 起讫: 2026-07-06

---

## 范围

- **目标**: 在 CCC 项目内新增 3 个轻量脚本 (status / cost) + 1 个 smoke test,完整跑通 v1.2.0 流程门控
- **只改文件**:
  - `scripts/ccc-status.sh` (新建, ~40 行)
  - `scripts/ccc-cost.sh` (新建, ~50 行)
  - `tests/scripts/test_ccc_status_smoke.py` (新建, ~60 行)
  - `.ccc/reports/hello-ccc-demo-v2.report.md` (新建, Executor 产物)
  - `.ccc/verdicts/hello-ccc-demo-v2.verdict.md` (新建, Verifier 产物)
- **不改文件**: 其他所有文件 (红线 3 范围白名单)

## 只改文件(白名单)

- `scripts/ccc-status.sh`
- `scripts/ccc-cost.sh`
- `tests/scripts/test_ccc_status_smoke.py`
- `.ccc/reports/hello-ccc-demo-v2.report.md`
- `.ccc/verdicts/hello-ccc-demo-v2.verdict.md`

## 改动文件清单

| 文件 | 行数 | 阶段 |
|------|------|------|
| `scripts/ccc-status.sh` | 105 | phase 1 |
| `scripts/ccc-cost.sh` | 85 | phase 2 |
| `tests/scripts/test_ccc_status_smoke.py` | 55 | phase 3 |
| `.ccc/reports/hello-ccc-demo-v2.report.md` | 85 | phase 4 (report) |
| `.ccc/verdicts/hello-ccc-demo-v2.verdict.md` | tbd | phase 5 (verifier) |

- **执行方式**: `auto`
- **Phase 数**: 3

---

## 改动 1: ccc-status.sh (Phase 1)

### 做什么
CLI 子命令 `ccc status` 增强版,补充看板上没有的"4 文件契约检查",给 Planner 提供一目了然的 .ccc/ 健康度。

### 怎么做
- 在 `scripts/` 下新建 `ccc-status.sh`(~40 行)
- 函数 `check_ccc_files()`: 输出 4 文件契约存在性 + 路径
- 函数 `check_recent_tasks()`: 读 `.ccc/plans/` 最近 3 个 task, 输出 plan/report/verdict 完整度
- 函数 `print_summary()`: 汇总 + 提示 (如某 task 缺 verdict)
- 支持 `--json` flag: 输出结构化 JSON
- 不修改 `scripts/ccc`(已有的 ccc 入口)

### 验收
- `bash scripts/ccc-status.sh` 退出码 0
- 输出含 "CCC 4-file contract" 标题
- `--json` 输出合法 JSON, 含 `profile`/`state`/`tasks` 三个 key
- `shellcheck scripts/ccc-status.sh` 通过

---

## 改动 2: ccc-cost.sh (Phase 2)

### 做什么
基于现有 `ccc-cost-report.sh` 的简化版,接受 `--task` 参数,只输出单任务的 cost summary。

### 怎么做
- 在 `scripts/` 下新建 `ccc-cost.sh`(~50 行)
- 解析 `--task <name>` 参数 (必填)
- 读 `.ccc/reports/<task>.report.md` 的 commit table
- 解析 commit message 提取 `ccc-task-id=`
- 输出: task 名 / commit 数 / 涉及文件数 / cost 估算
- 错误路径: task 不存在 → exit 2 + 错误信息

### 验收
- `bash scripts/ccc-cost.sh --task hello-ccc-demo` 退出码 0
- 输出含 "task: hello-ccc-demo" 和 "commits: 1"
- `bash scripts/ccc-cost.sh --task nonexistent` 退出码 2
- `shellcheck scripts/ccc-cost.sh` 通过

---

## 改动 3: test_ccc_status_smoke.py (Phase 3)

### 做什么
为 ccc-status.sh 写 pytest smoke test,覆盖两个场景:健康工作区 + 含缺 verdict 任务。

### 怎么做
- 在 `tests/scripts/` 下新建 `test_ccc_status_smoke.py`(~60 行)
- `test_status_text_output`: 跑 `ccc-status.sh` 检查 stdout 含 "CCC 4-file contract"
- `test_status_json_output`: 跑 `ccc-status.sh --json` 检查输出是合法 JSON
- `test_status_handles_missing_verdict`: 模拟一个 task 缺 verdict, 检查输出有 warning

### 验收
- `pytest tests/scripts/test_ccc_status_smoke.py -v` 3 cases 全过

---

## 改动 4: 写 Executor report.md (自动产物)

### 做什么
按 .ccc/reports/ 模板, 写 hello-ccc-demo-v2.report.md, 含 3 phase 总结 + 改动清单 + 自验。

### 验收
- 文件存在且非空
- 含 `> VERDICT: .ccc/verdicts/hello-ccc-demo-v2.verdict.md` 段

---

## 改动 5: 写 Verifier verdict.md (独立 session, 红色 11 强证据)

### 做什么
独立 `claude -p` session 跑, 写 verdict.md, ≥3 adversarial probes。

### 验收
- 文件存在
- 含 ≥3 个 `## Probe N` 段
- 含 `## VERDICT: PASS/CONDITIONAL_PASS/FAIL` 行

---

## Commit 计划

| Phase | 改动 | Commit message |
|-------|------|---------------|
| 1 | scripts/ccc-status.sh | `ccc-task-id=hello-ccc-demo-v2 phase=1` |
| 2 | scripts/ccc-cost.sh | `ccc-task-id=hello-ccc-demo-v2 phase=2` |
| 3 | tests/scripts/test_ccc_status_smoke.py | `ccc-task-id=hello-ccc-demo-v2 phase=3` |

---

## 全局验收清单

- [ ] 编译/语法检查: `bash -n` 3 个脚本全过
- [ ] shellcheck 3 个脚本全过
- [ ] pytest 1 个测试文件 3 cases 全过
- [ ] git diff 范围仅限 5 个 plan 声明文件
- [ ] 每个 phase 独立 commit, 含 ccc-task-id 前缀
- [ ] phases.json 与 plan phase 数一致 (3 phase), 全 done
- [ ] report.md 已写 + 含 > VERDICT: 引用段
- [ ] verdict.md 已写 + ≥3 probes + VERDICT 三选一
- [ ] ccc-precheck 5/5 PASS (启动前)
- [ ] ccc-finish 5/5 PASS (完成后)

---

## 后续步骤 (Planner 兜底)

完成后建议:
- 在 SKILL.md 中加引用 ccc-status.sh / ccc-cost.sh 工具
- 跨 IDE 实测这些工具 (Cursor / Zed)
- 写 E2E-DEMO.md 文档化本任务完整 trace

---

## 写法提醒 (红线 0 · 自然语言驱动)

不写步骤清单。每个"验收"用自然语言意图 + 参考命令,不堆命令。
