# P1 收尾补完报告 · 2026-09-06 指令执行

> 指令：`/Users/fan/.ccc/instructions/2026-09-06-p1-completion.md` · 执行：CCC 产线开发窗口（Claude Code CLI）· 日期：2026-09-07 执行，按指令日期落名。
> 目标仓：`/Users/fan/program/CCC`。开工前置 git pull --ff-only 已干净同步。

## 结论（一句话）

v2.0 P1.2 两修正经核验已在批2（`98a28aabc`）落地、本次补定向测试收口；**P1.3 结果 sidecar JSON 化本次全新实现并已合入部署**。全量测试绿、ruff 净、bash 语法过、服务重启 /health 200。

## 交付清单

### P1.2 补完（交叉验收两发现）

1. **main.py 消费端 severity 门** — 指令所提 `_audit_verdict_from_artifact`（约 :2241）在现行主干已不存在；实际 verdict 消费在 `server/engine/main.py` 机审段（约 :4020），由 `server/board/audit_verdict.py::read_verdict` 单源提供，**P0/P1 阻断、P2 仅留档**的门已在批2 实现。
   - 本次抽出可测 helper `server/engine/main.py::_blocking_findings`（仅 P0/P1 阻断），消费端改用之。
   - 定向测试：`server/tests/test_audit_verdict.py::test_p2_findings_not_blocking_main_consumer`（P2-only 不打回 / P0P1 混合只拦 P1 / 空 findings）。
   - 既有 `test_p2_findings_do_not_block`（phase2 侧）保留。

2. **cc-auditor.sh JSON 类型校验补强** — 现行 `scripts/cc-auditor.sh` 已实现 verdict∈{PASS,REJECT} + findings list + 每项 id/severity/file/line/note 全字段类型校验，非法走 fail-closed（写 fallback markdown verdict + exit 2）。
   - 测试补强：`scripts/tests/test-cc-auditor-verdict.sh` 新增 `findings-not-list`（findings 为字符串）与 `bad-verdict-value`（verdict=APPROVE）两例，均 expect rc=2。
   - 测试证据链未删，全过。

### P1.3 结果 sidecar JSON 化

3. **DSH 执行体产出 JSON sidecar** — `scripts/dsh-executor.sh`：写完 `.ccc-result.md` 后，经新模块 `server/engine/result_sidecar.py`（`convert_file`）从四段 markdown 提取生成同目录 `.ccc-result.json`。结构对齐指令样例：
   ```json
   {"work_id","card_title","probe_output","selftest_output","exit_codes":{"test","compile","lint"},"maintenance":{"plan_sync","lesson","readme","roadmap"},"evidence":{"commits","diff_stat"}}
   ```
   - 额外附 `maintenance_notes`（四问说明保留，audit 可读），未破坏样例契约。
   - 提取失败 → 告警 + 删 sidecar，**不阻断** markdown 链。
   - wrapper 传输段：`.ccc-result.json` 与 `.ccc-result.md` 一并拷贝到 log_dir（`${WORK_ID}-ccc-result.json`）。

4. **引擎收单优先读 JSON sidecar** — `server/engine/main.py::_apply_executor_result_to_card`：优先读 `<id>-ccc-result.json`（json.loads 提取 card_title/probe_output/selftest_output/maintenance → 直接映射回写区/维护区，不做字符串 split）；JSON 不存在/解析失败/结构非法 → 回退既有 `.ccc-result.md` split 逻辑（兼容窗口完整保留）。
   - 维护区四问从 JSON `maintenance` 对象映射为卡面格式 `N. **name**：[choice] 说明`，与 `new-card.sh` 模板及 `docgate.py::parse_maintenance_section` 兼容。
   - 收单入口 `_run_auto_worker` 改认 JSON 或 md 任一存在。

### 测试（指令第 5 条）

- 新增：`server/tests/test_result_sidecar.py`（sidecar 生成提取 / 引擎优先 JSON 收单 / JSON 缺失回退 markdown / 契约不完整抛错）+ `test_p2_findings_not_blocking_main_consumer` + bash 两例。
- 全量 `pytest server/tests/ -q` 绿（rc=0）· `.venv-hub/bin/ruff check server/` 净 · `bash -n scripts/dsh-executor.sh scripts/cc-auditor.sh` 过。

## 提交与部署

| commit | 内容 |
|--------|------|
| `3242d63f7` | feat(engine): add executor result JSON sidecar（main.py + dsh-executor.sh + result_sidecar.py + test_result_sidecar.py） |
| `48371ad2e` | test(audit): P1.2 severity gate helper + P2-only/JSON-schema targeted cases（main.py + test_audit_verdict.py + test-cc-auditor-verdict.sh） |

- 每 commit 即 push（续跑纪律）；当前 head = `48371ad2e`。
- 重启：`launchctl kickstart -k gui/$(id -u)/com.ccc.engine` 与 `com.ccc.web-server`。
  - 新 engine PID = **21888**（旧 28519），web-server = 21937（旧 28522）。
  - `/health`（http://192.168.3.116:7788/health）= **200**。

## 红线核对

- ✅ 未改 xianyu 业务仓；未动已关闭卡；未改 CardStateStore CAS/锁语义（只加 JSON 读取优先级 + md 缺失容忍）。
- ✅ JSON sidecar 缺失 → markdown 路径完整保留（兼容窗口）。
- ✅ fail-closed 未放松（verdict 非法仍 REJECT）；测试证据链保留。

## 备注

- 指令行号（:2241/:2713）为起草时近似，实际函数名随批2 重构变化；本文档按现行主干如实标注实际落点。
- `/cards` 端点返回 token 要求属正常鉴权（board 只读需 `/session`）。
