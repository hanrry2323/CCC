# 数据源可信度审计（2026-08-22 · Step 1 前置门禁）

> 审计人：Claude Code（W1·S140-01@M1）· 目的：核实 CCC 埋点/审计数据源是否存在「假数据」问题，产出可信度清单。
> 依据：2026-08-22 执行指令第一步。**此步未完成前，任何「修复后验证通过」的结论不成立。**
> 方法：读生产/消费代码（observer/metrics/exec_metrics/loader/audit_ledger/models）+ 2017 真实数据核验 + 真实日志格式比对。

## 一、结论先行

**发现 2 个结构性假数据源 + 2 个弱信号 + 1 个一致性漂移，直接影响看板/巡检可观测性：**

1. ❌ **`ccc-kb 调用次数`的 `call_success_rate` 恒为 100%（假数据）**——`failed_calls` 从不递增，成功率字段是摆设。调用次数本身经 ANSI 剥离后可计（2017 实测 44 次），但真实日志形态是 `⚙ \x1b[0m ccc-kb_kb_search`（glyph 与工具名夹色码），依赖剥离逻辑。
2. ❌ **`验收通过率`把「已关闭」当「机审通过」**——真实数据下近 30 卡显示 100%「通过率」，而实际已关闭卡机审 flag 仅 52.8%。这正是假关闭事故前的「假绿」指标。
3. ⚠️ **`机审命中率`可信但依赖回填 + 双机 ledger 分裂**——口径正确（基于 ledger.jsonl），但 approve-merge 在 M1 跑、机审在 2017 跑，两机 ledger 各自一份。
4. ⚠️ **`维护区覆盖率`与真门禁（docgate）不一致**——observer `is_maintenance_complete` 只认 `[是]/[否]`，docgate 已支持 `[x]` checkbox；漏计。
5. ✅ **`worker-events.jsonl` / `engine-metrics.jsonl` / `audit_ledger.jsonl` 本体可信**——append-only + 锁 + 原子写，结构真实。但 engine-metrics 心跳 08-22 03:04 后停止（8h 静默）→ **可观测性监控本身需要「看门狗的看门狗」**。

## 二、数据源逐项核实（生产端 → 消费端 → 可信度）

### S1. `worker-events.jsonl`（执行体/机审子进程退出事件）
- 生产：`server/engine/metrics.py record_worker_event`（engine 心跳循环，append-only JSONL）
- 消费：运维/看板异常原因视图（`exec/*.log` · `*.audit.log` 同源）
- 2017 实测：`tail -5` 见 xy057 run/audit 完整事件（ok/returncode/duration/peak_rss/peak_cpu/problem）——**真实**，且已包含机审「不通过」problem 字段。
- 可信度：✅ **可信**。局限：只覆盖 engine 派发的 worker；manual/远端认领事件不在此。

### S2. `engine-metrics.jsonl`（并发/心跳槽位快照）
- 生产：`record_slot_snapshot`（每轮心跳一行）
- 2017 实测：最后一行 `2026-08-22T03:04:48Z`，当前 ~11:00 → **心跳断 8h**。间隔本就不规律（10–30min）。
- 可信度：⚠️ **数据本身真实，但心跳停止无告警**——engine 进程活着（PID 65830，08-21 20:25 起）却不再写心跳，说明主循环可能挂起/阻塞在某个子进程或 SSH 调用。**这是 P1-1 需要根治的监控盲区。**

### S3. `{id}.log` / `.runN.log` / `.audit.log`（执行体原始输出）
- 生产：engine subprocess 重定向（`main.py:147`）
- 消费：`exec_metrics.parse_log_call_counts` + `observer.gather_mcp_metrics`
- 2017 实测：xy057.log = `opencode run --auto` 的原始 stdout（提示注入 + 执行体输出）；**110 个日志含 `kb_search("192.168.3.116",...)` 调用，0 个含 `⚙` 前缀**。
- 可信度：⚠️ **原始日志真实，但解析正则与日志格式脱节**：
  - `observer.gather_mcp_metrics` 正则 `⚙\s*(?:ccc-kb_kb_|kb_)\w+` → **实测匹配 0/110** → 指标恒 0。
  - `exec_metrics._ANSI_RE = \x1b\[[0-9;]*[A-Za-z]` 不剥离 `\x1b[?...` 私有序列 / OSC 序列 → 行首残留可能破坏 `^→`/`^$`/`^>` 匹配。
  - 工具/调用计数是**启发式**（`→`/`$`/`>` 行前缀），不是真实 MCP 调用数——只能当「活动强度」代理，不能当「调用数」。

### S4. `{id}.metrics.json`（调用数高水位 sidecar）
- 生产/消费：`exec_metrics.save/load_metrics_snapshot`
- 设计：只增不减，防日志覆盖归零——**合理**。
- 可信度：✅ 作为「高水位不归零」机制可信；数值本身仍是启发式计数。

### S5. `cards.index.jsonl`（任务卡解析缓存）
- 生产：`loader._load_dispatch_cards_incremental`（mtime 失效 + 锁）
- 消费：`loader` / `plans.sync_plan_progress` / `observer` / `approve-merge`
- 已知问题：**approve-merge 关闭卡后若不同步刷新索引，sync 读旧值**（断链 #1，P0-1 已加刷新，待验证生效）。
- 可信度：⚠️ **缓存**，mtime 机制总体可靠，但「改 .md 不刷索引」是回写断链主路径；且 M1/2017 各自一份索引。

### S6. `data/audit/ledger.jsonl`（机审结论 + 批准真值账本）
- 生产：`audit_ledger.record_audit` / `record_action`（append-only + fcntl 锁 + tmp+rename 原子写）
- 消费：`approve-merge.sh`（`has_action('machine_audit_pass', id)` 硬校验）、`observer.gather_audit_hit_rate`
- 可信度：✅ **可信（硬 provenance）**——append-only 不可改，命中回填独立。**但双机分裂**：机审在 2017 执行落 2017 ledger，approve-merge 在 M1 读 M1 ledger → 缺记录会误拒（已知教训）。

### S7. 卡体 `## 机审区`（执行体/engine 写入）
- 生产：engine `_append_machine_audit_pass` 自动落盘（`> 结论：通过` + ledger 双写）；**但执行体也可自写**。
- 消费：`models.machine_audit_passed_text` → BoardItem.machine_audit_passed → 看板列 / observer 指标
- 可信度：❌ **不可作为真值**——字符串匹配解析，执行体可自写「结论：通过」伪造。**真值必须查 ledger**（`machine_audit_pass` action）。当前 `machine_audit_passed` 派生自卡文，正是「两套数据源」问题的根源。

## 三、observer 5 项观测指标逐项判定

| 指标 | 函数 | 判定 | 根因 |
|------|------|------|------|
| 1. ccc-kb 调用次数 | `gather_mcp_metrics` | ❌ **success_rate 假数据** | `failed_calls` 从不递增 → 成功率恒 100%；调用次数经 ANSI 剥离可计（2017 实测 44），但依赖 `⚙` 前缀痕迹，漏计非 ⚙ 形态的调用 |
| 2. 维护区覆盖率 | `gather_maintenance_metrics` | ⚠️ 漏计 | `is_maintenance_complete` 只认 `[是]/[否]`，docgate 已支持 `[x]` checkbox |
| 3. 教训回流率 | `gather_lesson_recirculation_metrics` | ⚠️ 弱信号 | 只查「历史教训」字符串在不在，非真实回流质量 |
| 4. 验收通过率/打回率 | `gather_audit_trends_metrics` | ❌ **假数据** | `passed_count = machine_audit_passed OR state==已关闭`——关闭即算通过。实测近30卡 100%，真实机审通过率 52.8% |
| 5. 机审命中率 | `audit_ledger.hit_rate` | ✅ 可信 | 基于 ledger；但依赖回填被调用 + 双机 ledger 分裂 |
| 6. 功能巡查 | `run_playwright_smoke_test` | ✅ 可信 | 真实 HTTP 探测 |

**判定逻辑**（`run_observation` 的 有效/部分/无效）→ ❌ 继承上述假数据，可能误判。

## 四、2017 生产状态快照（本次核查时点）

- launchd：`com.ccc.engine` / `com.ccc.board-scheduler` / `com.ccc.web-server` / `com.ccc.scheduler` / `com.ccc.sync-skills` / `com.ccc.ai-loop-router` 全部在跑。
- `com.ccc.scheduler`（observer 定时调度）**已挂载**（plan-041 报告的「未挂载」已解决）；`~/.ccc/data/observer/` 快照到 08-22 02:18。
- **engine-metrics 心跳 08-22 03:04 后停止（~8h 静默）**——进程活着但主循环可能挂起，无告警。

## 五、必须修复项（Step 2 前置）

| # | 修复 | 状态 |
|---|------|------|
| F1 | `gather_mcp_metrics`：去掉虚假 success_rate（改为 None + 显式标注），ANSI 剥离补 `?` 序列 | ✅ 已修（2026-08-22，observer.py + test_gather_mcp_metrics_strips_ansi） |
| F2 | `gather_audit_trends_metrics`：「关闭率」与「机审通过率」分离，通过必须要求 machine_audit_passed，新增 closed_without_audit 红旗 | ✅ 已修（observer.py + test_gather_audit_trends_not_count_closed_as_passed） |
| F3 | `is_maintenance_complete`：对齐 docgate 的 `[x]`/`[ ]` checkbox 容忍 | ✅ 已修（observer.py + test_is_maintenance_complete_accepts_checkbox） |
| F4 | 机审真值单源化：`machine_audit_passed` 派生自 ledger（`machine_audit_pass` action），卡文只作提示 | ⏳ 待做（P0-3） |
| F5 | engine 心跳告警（看门狗的看门狗）：engine-metrics 停止 >N 分钟即告警 | ⏳ 待做（P1-1） |
