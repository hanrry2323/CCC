# 任务卡 ccc083 · 执行体重启空转根治——B3 取证与防旋修复（DSH 执行）
> 批准：老板合入批准 · 2026-08-25

> 关联：环节②交接指令(S116-01)卡2 · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

对「71 分钟 13 个短命执行体会话（7–16 步无编辑即断，llm_retry 最高 5 次/会话）」取证根治：核实 B3 假设（watchdog 对 LLM 失败的重派发循环）是否有直接日志证据；定位重派发循环并修复（重试退避/熔断/短命会话防旋）；会话寿命与编辑命中率纳入探针指标。

## 红线

- 白名单：scripts/watchdog-ccc.sh、scripts/kickstart-ccc.sh、server/engine/main.py（派发/重试段）、~/.dsh/run-executor.sh（只读参考）、server/tests/。
- 取证阶段只读：watchdog.log、engine.stderr.log、exec/*.log、worker-events.jsonl、engine-metrics.jsonl。
- B3 无法实证时必须显式标「推断」，不得当结论。

## 范围

- 取证：时间线对齐（会话起止 × watchdog kickstart 时刻 × LLM retry 记录），产出直接证据或排除。
- 修复方向（按取证结果择一或组合）：kickstart 前置 LLM 健康探针；短命会话计数熔断（N 分钟内 M 个短会话→暂停派发+告警）；重试指数退避。
- 探针：worker-events 增加会话寿命/编辑命中字段。

## 步骤

1. 全量取证并对时，先出证据段落。
2. 实施修复。
3. 自测：单测覆盖新熔断/退避逻辑；bash -n / py_compile。

## 验收标准

- [ ] 取证段有直接证据或明确「推断」标注
- [ ] 修复落地且有回归单测
- [ ] 探针字段可在 worker-events.jsonl 观察到

## 回写要求

- 回写区附证据时间线摘要与修复说明；维护区四问如实。

## 人工批注

（留空）

## 回写区

**实现说明**（commit `3bc16c7cb` · 分支 `codex/ccc083-executor-idle-restart-rootcure`）

### 一、取证时间线摘要（2026-08-24，全部只读取证，来源见括号）

| 时刻 | 事件 | 证据源 |
|----|----|----|
| 14:30:00 | 三服务热重启（ccc078 合入部署后） | watchdog.log:96-98 |
| 14:49:10–15:46:04 | watchdog 报「Engine: 进程不存在」**47 次** + 「日志心跳超时」8 次，每次即 kickstart --engine-only；间隔由分钟级加速至 **6–12s**（15:26:38 出现同秒双发）。当日全程累计 54 / 10 次 | watchdog.log:132-313（复现：`sed -n '132,313p' ~/.ccc/logs/watchdog.log \| grep -c '进程不存在'` → 47） |
| 14:49:09 / 14:56:09 / 15:00:07 / 15:06:10 / 15:11:15 … | 机审/开发会话执行 `bash scripts/watchdog-ccc.sh`（门禁实跑）与上行故障行**秒级对齐**（工具调用级证据：session cbe7c0714888@14:49:09、dc6bc052058a@14:56:09、f3d331b25318@15:00:07、bd899b05f067@15:06:10、773e1f7e1a8f@15:11:15 等） | ~/.dsh/sessions/--…-ccc078--/*/session.jsonl.zstd 的 tool/call 记录 |
| 15:39–15:46 | ccc078 worktree 新会话每 8–20s 一个（风暴峰值）；当日该目录累计 46 会话，短命（4–16 条 assistant 消息）且多数零编辑；全部同时死于 15:50:55–58（外部统一清理） | 同上目录 mtime + 转录解析 |
| 收单侧 | `失败回待分派重试: work=ccc079 retry=1/3 problems=['退出码非 0: 137（日志: …ccc079.audit.log）']`——在飞 worker 被 SIGKILL(137) 后被引擎按**业务失败**立即重派的直接证据 | 归档 engine.stderr.log（archive-20260824/engine.stderr.log.gz，16:35 轮转前末段） |
| 全程 | llm_retry 峰值 ×5/会话（session c9383a6f、bd899b05f067），provider=opencode-go EMPTY_RESPONSE/RATE_LIMIT | session.jsonl.zstd llm/retry 事件 |

**B3 判定**：方向正确（watchdog 参与了重派发循环），但机制修正为自持风暴——
机审/开发会话把 watchdog 脚本当「门禁实跑」（直接证据：工具调用与故障行秒级对齐）→ 单次观测即 kickstart → 重启窗口内 pgrep 判「进程不存在」再触发 → 在飞执行体被连带击杀(exit 137) → 引擎按业务失败立即原样重派 → 新一轮机审又实跑脚本。LLM 不稳定（llm_retry）是背景放大器，非触发器。
【推断】首触发原因未实证：14:49:09 首次实跑为何判「进程不存在」，最可能是 launchd ThrottleInterval=5s 重启空窗被 pgrep 命中或引擎当时短暂不可见；无法从现存日志复现，按卡红线如实标注为推断。

### 二、修复说明（三层防线 + 探针，均在卡白名单内）

1. **watchdog-ccc.sh 防旋四件套**：故障连续确认（streak≥2 才动手，孤立单次观测只记录）；同服务 kickstart 最小冷却（默认 300s，`CCC_WATCHDOG_KICKSTART_COOLDOWN` 可调）；风暴升级告警（streak≥10 写 `alerts/watchdog-flap-*.alert` 转人工，每小时至多一次）；`CCC_WATCHDOG_DRY_RUN=1` 演练开关。
2. **kickstart-ccc.sh 最内层闸**：同服务最小重启间隔默认 60s（`CCC_KICKSTART_MIN_INTERVAL`=0 关闭、`CCC_KICKSTART_FORCE=1` 强制越闸）+ DRY-RUN。任何调用方（watchdog/deploy/人工）统一受闸。
3. **server/engine/main.py（派发/重试段）**：
   - 击杀语义退出码（137/143/-9/-15/-137/-143）改判基础设施故障→冷却续派，不再烧业务重试预算立即重派；
   - 短命会话计数熔断：窗口内 ≥5 个「失败且寿命≤300s」worker 事件 → 全局暂停派发+告警文件 `EXECUTOR_LOG_DIR/alerts/short-session-breaker.txt`（`EXECUTOR_SHORT_SESSION_*` 可调），派发门禁链与机审补位双挂点；
   - 业务重试指数退避：回待分派重试按 retry_count 指数退避（60s×2^n 封顶 900s，进程内），收单成功/机审通过自动清除；
   - 未采纳「kickstart 前置 LLM 探针」：派发侧已有 relay_probe 门禁覆盖 LLM 健康，且取证显示 LLM 非触发器；LLM 故障场景由短命熔断兜住（会话快速死→暂停派发+告警）。
4. **探针字段落地**：worker-events.jsonl 每次 worker 退出追加一行 `kind=session`（`session_lifetime_s` 会话寿命 / `short_session` 短命标记 / `edit_hit` 编辑命中：相对 dispatch_tip 有新提交或有未提交改动；不可判定为 null 不伪造）。消费方按 kind 过滤互不干扰（web/server.py 只取 kind==worker，已单测锁定）。观测示例命令：`tail -2 ~/.ccc/logs/exec/worker-events.jsonl | python3 -m json.tool`。

### 三、自测结果

- 新增 `server/tests/test_ccc083_antispin.py` **34 例全绿**（机审席定点复跑核实；击杀码分类/熔断窗口过滤与阈值/退避单调封顶与过期/探针三字段含 git 夹具/watchdog 防旋闸 bash 子进程场景/kickstart 冷却与 DRY-RUN/bash -n）。
- 引擎回归：test_engine_main/dispatch/metrics/gates + antispin 合跑 **171 例全绿**。
- 卡面门禁：`bash -n scripts/watchdog-ccc.sh scripts/kickstart-ccc.sh` 通过；`python3 -m py_compile server/engine/main.py` 通过。
- 全量套件：1194 passed / 11 failed；失败集与改动前基线 **逐条 diff 完全一致**（test_brain_kb/test_brain_stream/test_http_api/test_advanced_review 会话族，本卡未触碰），另有一次运行的偶发第 12 失败（test_cross_round_slot_fill_no_batch_join，基线同现 1/6，属既有计时敏感偶发）。

### 四、push 核验

- 分支 `codex/ccc083-executor-idle-restart-rootcure` → origin，commit `3bc16c7cb86be9f59c2173992172ec211ea20187`，6 files changed, 927 insertions(+), 40 deletions(-)；回写提交为本分支第二个 commit。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：本卡关联环节②交接指令(S116-01)卡2，非 prefix-plan-NNN 方案转卡，无方案文需同步。
2. **教训沉淀**：[无]
   - 说明：「机审/开发会话把运维脚本当门禁实跑可触发生产动作」候选教训已完整写入本卡回写区供环节②裁量；docs/lessons.md 在本卡白名单外，未越界改动。
3. **档案/README**：[否]
   - 说明：新增环境变量开关与探针字段契约已写在两脚本头注释、main.py docstring 与本卡回写区，无项目档案/README 结构变更。
4. **线路图**：[否]
   - 说明：无新增线路意向；遗留观察（pgrep 首触发竞态的实证手段、exec 日志归档导致现役取证面变薄）已在本卡回写区披露，待后续卡按需认领。

## 机审区

**DSH 机审席 · 2026-08-25 · severity：轻**

> 本区为对已回写卡的**独立复审**（第二轮），逐条以命令复现证据、不引用执行体与前轮机审自述；
> 取代 commit `82f2e0c04` 所落第一轮机审区（历史见 git）。前轮两处就地更正（进程不存在
> 51→47 次、自测 32→34 例）经本轮独立复现**确认属实**。

### 一、范围核对（可复现）

- 分支 `codex/ccc083-executor-idle-restart-rootcure` 共三 commit：`3bc16c7cb`（修复）→ `14f6eed8a`（回写）→ `82f2e0c04`（首轮机审区），`git rev-list --left-right --count origin/…HEAD` → `0 0` 与 origin 同步，`git status --porcelain` 干净。
- 修复 commit 触及 6 文件全部在卡白名单内：scripts/watchdog-ccc.sh、scripts/kickstart-ccc.sh、server/engine/main.py（hunk 全部落点经 `git show --stat` + `grep '^@@'` 核验，限于基建判定/熔断退避/门禁装配/run_once 补位/探针段）、server/tests/test_ccc083_antispin.py（新增 439 行）、test_engine_gates.py / test_engine_main.py（既有用例适配）；后两 commit 仅触卡文件自身。`~/.dsh/run-executor.sh` 未改。无越界、无 `## 验收区

**合入批准** · 日期：2026-08-25
- 判定：通过
`、卡头状态「已回写」未变「已关闭」。

### 二、对抗式发现（0 P0/P1；4 观察项均不阻塞）

1. 【观察项】watchdog 升级告警在「kick 成功即清零 streak」语义下，纯 launchd 节奏（约 60s/轮）中 streak 峰值约 5–7 < FLAP_ALERT_STREAK(10)；且**持续性真故障**也会被每次 kick 重置而永不升级转人工。人工高频实跑形态（即本次风暴）可达阈值。属参数耦合设计缺口，建议后续卡档案化或改为按时间窗计数。
2. 【观察项】`_append_session_probe` 在收单路径内联执行两次 git 子进程（各 `timeout=10`），git 挂起最坏给收单尾部追加 ~20s 延迟；有界且整体 try/except 兜底不进异常路径，常态毫秒级。
3. 【观察项】kickstart DRY-RUN 分支会写入 last-kick 状态时间戳，演练后紧接的真实重启会被冷却闸跳过（仅演练模式语义噪声，生产路径不受影响）。
4. 【风险备查】短命熔断统计不过滤 exit_kind：连续 ≥5 个快速业务失败的坏卡批次也会全局暂停派发一个统计窗口（自动恢复 + `alerts/short-session-breaker.txt` 告警可见）。符合卡规格字面，属设计权衡。

### 三、修复落地正面核验（代码级）

- **击杀码改判**：`is_retryable_failure` 新增 `_kill_exit` 正则带负向断言 `(?![0-9])`，1370/-90 类不误匹配（有参数化单测）；run 相 main.py:3822、audit 相 :3979 两处 `retryable=True` 均走 `_hold_infra_failure`（strike 计数冷却续派），业务失败才走 `_fail_retry_or_reject`（retry_count++ + 指数退避）——「不烧业务重试预算」属实；audit 相业务打回判定先于 infra 分支，击杀改判不会吞掉业务打回。
- **短命熔断双挂点**：dispatch 门禁 `short_session_breaker` order=15 + run_once 机审补位候选循环全局闸（每轮一次判定，告警同文件覆盖写不膨胀）；门禁链 order 10/12/15/20…110 无冲突，GateContext 具备 now_ts/log_dir/cfg/counters（server/engine/gates.py:58-72）。
- **指数退避**：`retry_backoff_seconds` 60×2^(n-1) 封顶 900s，收单成功（:3757）/机审通过（:3864）清除，进程内实现、重启失效由熔断兜底（docstring 明示，可接受）。
- **会话探针**：marker_id 命名 `{id}` / `{id}-audit` 与全仓 running-marker 惯例一致（main.py:1336/3556），`edit_hit` 三态（True/False/null 降级不伪造）判定链成立；消费方按 kind==worker 过滤有单测锁定。
- **既有测试适配非削弱**：门禁链断言 11→13 与新门禁一致；test_engine_main 改换卡 ID 系隔离新防旋语义（被回收击杀卡改走基建冷却），边界断言 dispatched==3 保持原样。
- **未采纳「LLM 前置探针」理由成立**：relay_probe 门禁已在派发链中覆盖 LLM 健康，且取证显示 LLM 非触发器；弃用决策在回写区显式交代。
- bash 层测试全程 HOME 重定向 + DRY-RUN + 假进程名，无生产副作用。

### 四、取证真实性抽查（本轮全部独立复现）

| 卡面引用 | 复现结果 |
|----|----|
| watchdog.log:96-98 三服务热重启 | `[2026-08-24 14:30:00]` 起 engine/web/scheduler 三行 ✓ |
| 区间 [132,313] 故障 47 次/心跳 8 次 | `sed -n '132,313p' ~/.ccc/logs/watchdog.log \| grep -c 进程不存在` → **47**；心跳超时 → **8** ✓ |
| 当日累计 54 / 10 | 按 `^\[2026-08-24` 前缀过滤 → **54 / 10** ✓ |
| ccc079 exit 137 被按业务失败立即重派 | `gunzip -c ~/.ccc/logs/archive-20260824/engine.stderr.log.gz \| grep '退出码非 0: 137'` → `work=ccc079 retry=1/3 problems=['退出码非 0: 137…]` 原句 ✓ |
| session cbe7c0714888@14:49:09 实跑脚本 | 解压该 session.jsonl.zstd：`tool/call` name=bash time=**14:49:09.755** command=`cd …/ccc078 && bash -n scripts/watchdog-ccc.sh && bash scripts/watchdog-ccc.…`，与 watchdog.log:132 故障行 **14:49:10** 亚秒对齐 ✓（本轮新增工具调用级独立取证） |

- B3 首触发原因（launchd ThrottleInterval 重启空窗竞态）现存日志不可复现，卡面按红线如实标注【推断】，验证属实。机制叙事「门禁实跑→自愈误触发→连带击杀→业务重派放大」每一环均有上表一手证据支撑。

### 五、维护区四问核对（机械判据）

- 四问均单选实填：[否] / [无] / [否] / [否]，无模板占位；说明均为一句实情非空转。
- 「教训候选已写入回写区、docs/lessons.md 在白名单外未越界改动」经 `git show --stat 3bc16c7cb` 核实属实（改动清单无 lessons.md）。
- 抽查其余引用工件（worker-events.jsonl、exec 日志目录、alerts 目录约定）均存在或为本卡新契约定义。

### 六、severity 判定与分流

- 影响面 1（遗留发现均为观察级，不改机制结论）+ 改动深度 2（引擎派发核心 +320 行，结构上为加法式、不动 submit 原子门禁不变量）+ 红线邻近 1（全程在卡白名单内、默认参数保守、env 开关可即时降级）= **4 分 → 轻**；无单维 3 分，不触发强制升级。
- 分流：轻 → 无需再就地修复（前轮两处失实已更正且本轮复核无误），维持现状通过。

机审：通过
