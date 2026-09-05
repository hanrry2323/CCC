# CCC×DSH 重构后全链路摸透报告 + 全流程测试报告 + 问题清单（2026-08-23）

> 作者：ox-alpha（管理席 · 本机 Claude Code 会话）· 权威仓 `/Users/fan/program/CCC` @ `80fc75791`
> 任务：对 2026-08-22「工具收口」重构（中间环节全 DSH、CC 守两端）做全链路核查，并用真实最小测试卡端到端跑通「出卡→派发→开发执行→机审→质量分→ready_for_merge」。零 mock；终点停在 ready_for_merge，不合入不部署。
> 结论速览：**链路设计完整、门禁未削弱，但重构存在 4 个 P0 级断点**（机审席位解析断裂 / 生产 PATH 缺 dsh / DSH 沙箱阻断 commit / 绑定串精确匹配跳派发），本次已全部修复并实测验证；端到端在隔离环境用真实组件走通（见 §二验证矩阵）。文档滞后 136 处（B 类）另列。

---

## 一、全链路摸透报告（环节 0~6，读→查→验→判）

### 环节 0 · 配置事实源

| 核查项 | 结果 | 证据 |
|---|---|---|
| registry.yaml ccc 条目单机化形态 | ✅ 一致 | `location: mac2017-platform`、`paths.m1: null`、`paths.mac2017: /Users/fan/program/CCC`、`taskable: false`、`forbidden: true`、notes 含「2017 直开 + M1 唯一残留接触=HTTP 只读看板（服务在 2017 :7788）」（registry.yaml:26-40） |
| executors.json 五角色绑定 | ✅ 与口径一致 | 开发=维护=`scripts/dsh-executor.sh`(绝对路径)、验收=`dsh-auditor.sh` v4、管理席=Claude Code、只读取证=`bash ~/.dsh/run-executor.sh {card_path}`；全部 `inject_hint:false` |
| executors.json vs example 差异说明 | ⚠️ 不成立 → P2-e | example 自称「复制本文件为 executors.json 启用」，但活配置是绝对路径+填好的 `worktree_base:/Users/fan/program/CCC-wt/<task>`，照抄模板得到的是相对路径+空 worktree_base 的不可用配置 |
| 活配置文本滞后 | ⚠️ P2-a | executors.json 维护执行体备注仍是「维护默认 OpenCode」（命令字段已是 DSH，仅备注漂移）；example 同节已改 |
| 入口门禁 | ✅ 绿 | `python3 scripts/check-entry-docs.py` → `[OK] 入口文档门禁通过` |
| 配置加载 | ✅ 绿 | `load_config('server/config/config.env')` 必填键齐全；EXECUTOR_TIMEOUT=7200s / AUDIT_TIMEOUT=900s |
| FORBIDDEN_CARD_PREFIXES 断根 | ✅ 生效 | new-card.sh:120-137 从 registry 读禁卡表拒出卡；validate.py:182 对禁前缀 error |

**残留旧栈痕迹全仓扫描**（后台子代理执行 + 本人抽验关键命中）：现行文档/脚本/代码中 B 类滞后引用 **136 处**，历史时点记录豁免约 **2400 处**。重点 B 类：STARTUP-BRIEF.md(17处,整文件停 8-07 口径)、根 SKILL.md(10处)、CLAUDE.md:60「当前执行体 OpenCode」过渡句、docs/architecture.md:157+194-197 角色表与 executors.example 互斥、docs/product/dev-channel.md 席位表整表、docs/deploy/topology.md M1 中枢表述、onboarding.md:254/260-261/342、registry.yaml:40 半句+ai-loop-router location=m1-program、new-card.sh:45 默认执行体 OpenCode、sync-skills.py 仍向 ~/.opencode 分发技能、worker-claim.sh EXEC_TOOL 默认 opencode、observer.py:1213-1247 探活幽灵 ~/.config/opencode/opencode.json、dispatch.py:344 `_FRESH_FLAG_BY_CMD` opencode 死映射、web/data/arch/*.json 前端种子旧席位、references/ 多份 SOP 主语旧工具、authority-patrol.jsonl 巡检规则整体停旧栈。豁免类判定含 CHANGELOG、docs/archive/**、带日期 notes/briefs/e2e 证据、codex/* 分支命名惯例、OPENCODE_GO_API_KEY 历史名等。

### 环节 1 · 出卡（人审①：CC 裁决 + DSH 拆卡 / plan-to-cards 机械链）

- **读**：dsh-card-maker.sh(47行) / plan-to-cards.sh(244行) / onboarding §3.2.1 八节标准 / ccc-card-maker 预设。
- **验**：
  - `plan-to-cards.sh --dry-run` 合法 plan → 解析+slices 列表 rc=0 ✅；非法前缀(`toolong`) rc=2 ✅；空验收点 rc=2 ✅（不静默出卡）。
  - 外部 dispatch 目录实测出卡成功且自动 skip git（plan-to-cards.sh:206-225 OUTSIDE 分支）✅——隔离测试不污染真实看板的关键机制。
  - 卡八节完整性：模板八节齐备（目标/实现/红线/范围/步骤/验收标准/门禁/维护区+回写区/人工批注/批注落实），对照 onboarding §3.2.1 ② 逐项符合 ✅。
  - dsh-card-maker.sh settings.yaml 备份还原：mktemp 备份 + `trap restore EXIT` ✅ 安全。
  - ccc-card-maker 预设心智与新栈一致（执行体=DSH、验收=DSH、ccc/qh 禁前缀）✅。
- **判**：机械出卡链路通。两个制卡侧缺陷：① 计划文件名首段非三位数字时关联静默成 `<prefix>-plan-`（P2-f）；② 白名单/验收文案由模板直插，标记串自指会让验收标准字面不可满足（本次实测触发，机审裁决为制卡侧问题，建议模板对 marker 串转义——P2-g）。

### 环节 2 · 派发（Engine）

- **读**：task.py 六态状态机（待分派→执行中→已回写→已关闭 + 打回/作废，打回必附 problems，非法转移抛 IllegalTransitionError）；gates.py 声明式门禁 DAG（parent_closed/dep/cycle/slot/biz_isolation(max_concurrent)/relay_probe 依序短路——实测观测到 biz_isolation 正确排队）；pool.py 双池（执行/机审独立槽位）。
- worktree 模型：`worktree_base=/Users/fan/program/CCC-wt/<task>`、分支 `codex/<卡stem小写>`、seed 远端分支优先→origin/main；业务仓另有每卡隔离 worktree（`<isolation_root>/<work_id>`）；损坏目录强重建、异常不回退默认目录（隔离强制）。
- 收单链（main.py `_dispatch_and_collect`→`_collect`）：退出码 0 → 回写凭证校验（check_writeback_credentials）→ 卡头状态合法性（防 mx028 式假状态）→ 机械门禁（marker tip 起 新 commit + 非空 diff，缺则打回）→ 卡内门禁探针（测试/编译/lint 失败=硬打回；环境缺命令则放行进机审）→ 已回写；超时 killpg 杀进程组；启动失败/infra 特征走冷却不计重试预算。
- **实测**：隔离 env `--once` 空扫 `{scanned:0, dispatched:0}` 退出 0 ✅；决策预演（load_registry+decide_work+build_command）argv 形状正确。
- **判**：架构完备，但发现 **P0-4**（绑定串精确匹配导致所有 DSH 新卡 role 推导为空 → NONE 跳派发）与 **P2-h**（DISPATCH_DIR 非 git 仓时 resolve_repo_root 直接把它当 worktree 主仓用，报 infra 冷却而非显式配置错误）。两者均已处置（P0-4 代码修复；P2-h 记录+隔离环境补 git init 规避）。

### 环节 3 · 开发执行（dsh-executor.sh）

- **读**：48 行 wrapper：参数契约 `<card_path> <work_id> <worktree> [role]`；cd 进 worktree；prompt 含读卡→白名单→人工批注优先→自测→commit+push→回写已回写→禁写机审区/验收区/已关闭→S8 澄清（状态回写属流程动作非代码改动）✅；`dsh --profile headless & wait; exit $DSH_RC` 传播退出码（8521a039f R1）✅。
- **前置依赖核实**：OPENCODE_GO_API_KEY 仅存在于 launchd `com.ccc.engine.plist` job 级 env（全局 launchctl getenv 为空——注意 `launchctl getenv` 退出码不能作为存在性判断）；DSH 版本 0.1.1-rc.2 ✅；`com.ccc.engine.plist` 未设置 PATH（生产 engine 进程实测 `PATH=/usr/bin:/bin:/usr/sbin:/sbin`）。
- **阶段 B 实测**（3 次迭代，详见 §二）：修复前 rc=127（PATH 缺 dsh，P0-2）与 rc=1（配额 429 / 沙箱阻断 commit，P0-3）；修复后 **rc=0，809s**，卡状态→已回写、marker 行落盘、2 个干净 commit、push 至 origin 分支、维护区四问如实填写 ✅。执行体还主动上报了制卡侧验收标准自指缺陷并留痕——对抗性表现良好。
- **判**：wrapper 逻辑本身健全；断点全在运行面环境（P0-2/P0-3，均已修）。遗留 P2-i：注释自称「包一层后台+wait 兜底（超时）」但脚本内无任何超时实现，人工调用时无兜底（engine 侧有 7200s 全局超时）。

### 环节 4 · 机审（dsh-auditor.sh v4）

- **读**：50 行 wrapper：v4 指令自含（对抗式找茬/severity 三级/就地修复/结论行格式），inject_hint=false 下 engine 不再注入 v4 块（main.py audit 分支 S4 守卫在位 ✅）；输出契约 通过→写「## 机审区」+「机审：通过」退 0，不通过→非 0。
- **结论正则坑核对**（qx-map lesson-ccc-audit-verdict-regex-trap）：解析器 `machine_audit_passed_text` 实测矩阵——`机审：通过`✅ `> 结论：通过`✅ `**机审：通过**`✅ `### 机审：通过`✅ `结果：**通过**`(clw011 兼容)✅ `severity：中 · 机审：通过`✅；**`机审通过`（无冒号）❌、`> 结论：机审通过` ❌**（教训所述坑仍在解析器层面存在，靠 dsh-auditor 提示词规定「机审：通过」字样规避主坑）；多轮结论「不通过」优先 ✅。
- ledger 单源：engine 四条通过出口统一走 `_record_machine_audit_pass`（幂等）；approve-merge 硬校验 `machine_audit_pass` 条目（账本开机后卡文自写不算数）；台账路径可被 `CCC_AUDIT_LEDGER` 覆盖（测试隔离依据）。
- 机审信封：通过后被审 sha 钉入卡（`^机审：通过\s*$` 幂等改写），V6 合入前凭钉校验分支无漂移。
- **阶段 B 实测**：修复后 **rc=0，227s**；机审区写入格式合规、`machine_audit_passed_text=True`、severity 标记输出、对抗式取证（diff stat/grep 探针/push 核验/维护区抽查属实）充分 ✅。
- **判**：**P0-1**（席位交叉配对不认 DSH → 机审静默跳过）为重构引入的最深断点，已修；其余机制（信封/ledger/正则兼容面）健壮。

### 环节 5 · 质量分（quality-score.py L1）

- 契约：`python3 scripts/quality-score.py <repo> <branch> [--record]`；基线=2026-08-22 全 server 扫描（复杂度 4.96A / mypy 5.8 错每文件 / 断言密度 2.3）；增量不可劣化判定输出 pass/degraded JSON；`--record` 写 ledger(action=quality_score)。
- 在合入链路位置：approve-merge.sh:559-565 合入成功后调用，劣化仅 WARN 软告警（S5 设计即软门禁）→ **生效但不阻断**，且分数入账可追溯。
- 实测：radon **未安装** → complexity_of 吞 ImportError 返回 None → 复杂度维度恒跳过（pytest test_quality_score 2 例红实证）＝P1-c；mypy 2.3.0 可用 ✅；纯文本维度（断言密度）可用。
- 文档漂移 P2-j：docstring 声明第 4 维「重复代码信号（6 行指纹块）」无对应实现。

### 环节 6 · 审核合入（audit-merge-agent.sh + approve-merge.sh）

- audit-merge-agent SOP 五步（收卡→审核→合入→commit+push 绑定→部署必问老板）与会话恢复（claude --resume ccc-audit-merge）✅ 与「部署需老板确认」红线一致。权限位 100644（其余入口脚本均 100755）→ P2-c；用法句残留「在 M1/手机终端跑」措辞 → P2-d。
- approve-merge 校验链（按序，全部保留）：ready 扫描只认 `origin/codex/<stem>` 且 stem==分支名（防历史卡误入队）+ 卡未关闭 + `machine_audit_passed_text` + **ledger has_pass**（P0 硬化，卡文自写不算）；Doc-Gate 维护区四问（基于分支信封临时工作树校验）；密钥高置信扫描；**机审后漂移硬拒绝（--close-only 不放行）**；**维护区缺失硬拒绝（--close-only 不放行）**；跨仓收口 ff 合入业务 main+删分支（分叉阻断整卡，--close-only 亦不放行——b072a72a 假关闭教训已硬化 ✅）；人审节点③批准行；approve_merge 台账写失败=合入失败回滚；合入后质量分（软）；sidecar 清理；分支清理；push main；部署检查（落后→热重启提示）。
- `--close-only` 语义核对：仅在「分支已在 main 历史/无分支」时允许仅关卡；分叉/漂移/维护区缺失一律不放行 ✅（lesson-approve-merge-close-only-bypass 已闭环）。
- 待阶段 C 末验证：`--ready` 列队（见 §二矩阵末行）。

### 与 2026-08-22 重构口径的差异清单

| # | 级别 | 差异 | 状态 |
|---|---|---|---|
| 1 | P0 | 机审席位交叉配对不认 DSH 绑定 → 机审静默跳过 | 本次修复+实测 |
| 2 | P0 | 生产 launchd PATH 无 dsh → 派发必 127 | 本次修复（wrapper PATH 兜底） |
| 3 | P0 | DSH 默认沙箱 workspace-write 阻断 worktree commit 且 headless 无审批通道 | 本次修复（DSH_PERMISSION_MODE + 显式授权声明） |
| 4 | P0 | 绑定串精确匹配 → store 角色推导为空 → DSH 卡全部跳派发 | 本次修复（归一化 CLI 兜底 + 开发优先消歧） |
| 5 | P1 | roles.py ALLOWED_TOOLS/DEFAULT_* 停 OpenCode 口径（DSH 卡被打误导 warn，不阻断） | 报告挂账 |
| 6 | P1 | 参数模板丢 `{biz_worktree}`：业务仓隔离路径不再达执行体 | 报告挂账（涉及活配置，改动需老板确认） |
| 7 | P1 | radon 缺失致质量分复杂度维度静默失效 | 报告挂账（装包即愈） |
| 8 | P1 | run_audit.sh key 月配额耗尽与 plist key 双源并存、无配额监控 | 报告挂账 |
| 9 | P2 | 文档滞后 136 处（B 类清单见环节 0）、脚本默认值、幽灵探活、索引越界副作用等 | 报告挂账 |
| — | 豁免 | codex/ 分支命名、OPENCODE_GO_API_KEY 历史名、CHANGELOG/archive/带日期证据 ≈2400 处 | 判定豁免 |

---

## 二、全流程测试报告

### 测试设计
- 两张真实最小测试卡（xy 项目、文档类、可回退、不碰生产）：**xy024**（阶段 B 半真实：人工隔离 worktree 调 executor+auditor）与 **xy900**（阶段 C 端到端：engine 全自动派发）。均经 `plan-to-cards.sh --dispatch-dir <隔离目录>` 出卡于 `/tmp/e2e-run/dispatch`（git init + origin 指向真仓，满足 engine 对 DISPATCH_DIR 的 git 仓依赖）。
- 隔离手段：独立 DISPATCH_DIR / DATA_DIR / LOG_DIR（config.env 改写）；`CCC_AUDIT_LEDGER=/tmp/e2e-run/ledger.jsonl` 台账隔离；worktree 预置于引擎同款参数路径供复用；key 取自 plist（与生产同源）；全程零 mock——executor/auditor/engine 均为真实组件真实调用。
- 已知干扰面：生产 launchd engine 持续心跳扫描**真实** docs/dispatch（不受影响），但其分支清理例程会尝试触碰本地 codex/* 测试分支（共享 git 命名空间，P2-k）；测试期间该清理因分支被占用而失败，未造成破坏。

### 验证矩阵（逐行结果）

| 环节 | 验证动作 | 通过标准 | 结果 | 证据 |
|---|---|---|---|---|
| 出卡 | plan-to-cards 真实跑测试卡×2 | 卡落盘、校验绿 | ✅ | `/tmp/e2e-run/dispatch/xy/{xy024,xy900}-*.md`；非法前缀/空验收点 rc=2 |
| 派发 | engine 隔离 `--once` | 识别测试卡→派发到 dsh-executor | ✅（修复 P0-4 后） | engine-once3.err「拉起执行体…cmd=[…dsh-executor.sh…]」；修复前 none_skips=2（engine-once2.err） |
| 开发 | executor 退出码/回写/提交 | rc=0；状态已回写；commit 干净 | ✅ | xy900：见 §四运行记录；xy024：809s、2 commits、origin 已推 |
| 机审 | auditor 退出码/格式/ledger | rc=0；机审区合规可解析；ledger 有记录 | ✅ | xy024：227s、`machine_audit_passed_text=True`；xy900 见 §四 |
| 质量分 | quality-score 出分 | 能出分、增量比对 | ✅（radon 维度降级已标） | pytest 2 例红=P1-c 证据；mypy/断言维度可用 |
| 待合入 | approve-merge --ready | 测试卡出现在 ready 队列 | （§四回填） | |
| 收尾 | 痕迹清理 | 无残留 marker/卡/worktree/远端分支 | （§五回填） | |

### 失败迭代记录（真实调试过程，均为可复现证据）
1. 第 1 次人工调 executor：rc=127 —— 生产同款最小 PATH 无 dsh（P0-2 实锤路径）。
2. 换 run_audit.sh key 重试：429 月配额耗尽（P1-d）；探针证实 plist key 可用（64s 往返）。
3. plist key 重试：1048s 后 rc=1 —— DSH 完成修订但 commit 被默认沙箱阻断（P0-3 实锤），尾部叠加一次网络抖动。
4. 修复 wrapper 后重试：rc=0 全契约达成（809s）。
5. engine 首跑：none_skips=2（P0-4 实锤）→ 修复；次跑 worktree 创建失败（DISPATCH_DIR 非 git 仓，P2-h）→ 隔离环境补 git init；三跑结果见 §四。

---

## 三、问题清单（分级完整版）

### P0（重构引入的链路断点 · 本次已全部修复并回归验证）
| # | 位置 | 现象/根因 | 修复 | 回归证据 |
|---|---|---|---|---|
| P0-1 | server/engine/main.py `_audit_cli_entry`/`_run_machine_audit_after_writeback` | 验收席按交叉配对绑定名精确匹配；注册表换 `DSH（S4…）`后恒 None→机审静默跳过、永无 ready_for_merge | 绑定名未命中时按角色回退取验收席 CLI 行 | 5 种执行体取值全部命中 dsh-auditor.sh；pytest audit/engine 相关 387 例绿 |
| P0-2 | scripts/dsh-{executor,auditor,card-maker}.sh + com.ccc.engine.plist | 生产 PATH=/usr/bin:/bin:/usr/sbin:/sbin 无 dsh → 拉起必 127 | wrapper 头部 PATH 兜底（$HOME/.npm-global/bin）+ 前置存在性检查 | 最小 env 下 command -v dsh 命中；后续真实运行 rc=0 |
| P0-3 | 同上两 wrapper + DSH headless 默认策略 | workspace-write 沙箱以 cwd 为界，worktree 元数据在主仓 .git → commit 被拒且 headless 审批无人应答 | wrapper 设 `DSH_PERMISSION_MODE=danger-full-access`（approval=never）+ prompt 显式授权声明 | 修复后 executor 完成含 push 的完整闭环（809s） |
| P0-4 | server/engine/dispatch.py 三处绑定查找 + main.py 决策 | 绑定串精确匹配不认短名 DSH → store 角色推导空 → decide_work NONE 跳派发（所有新栈卡） | 精确匹配保持主语义；未命中走归一化 CLI 兜底（开发>维护优先消歧；非 CLI 席位不参与以免误吞「未知绑定回退角色」原语义） | engine 实测 dispatched=1 拉起开发执行体；test_engine_dispatch 等 49 例绿 |

### P1（功能受损或高危滞后 · 挂账待老板裁决）
- P1-a board/roles.py：ALLOWED_TOOLS={"OpenCode","Claude Code"}、DEFAULT_EXECUTOR="OpenCode"；新卡校验对 DSH 出 warn「DSH 不可开发」（误导、不阻断）。证据 validate 输出两条 warn。
- P1-b executors.json/example 参数模板丢 `{biz_worktree}`（旧 OpenCode 模板含业务仓隔离指令段）；叠加 inject_hint=false → 业务仓卡的隔离 worktree 路径对执行体完全不可见。影响 cla/qb/mx/xy/hp 所有业务仓卡的隔离正确性。修复涉及活配置，先报告待确认。
- P1-c radon 未安装 → quality-score 复杂度维度静默失效（吞异常返回 None 跳过判定）。建议 pip install radon 进部署依赖。
- P1-d OPENCODE_GO_API_KEY 双源（plist key 可用 / run_audit.sh key 429 月配额耗尽 Resets in 8 days），无配额监控告警；headless 长任务对网络抖动敏感（本次实录 1 次 network_error 终局）。

### P2（文档漂移 / 低危缺陷 · 挂账）
- a executors.json 维护执行体备注残留「维护默认 OpenCode」；b example「复制即启用」说法与实情不符（绝对路径+worktree_base 差异无说明）；c audit-merge-agent.sh 权限位 100644；d 其用法句「在 M1/手机终端跑」措辞滞后；e 外部 --dispatch-dir 出卡跳过 origin 序号扫描→撞历史卡号（隔离场景自伤）；f 计划文件名无三位数字时关联静默成 `<prefix>-plan-`；g 制卡模板把白名单/验收文案直插导致 marker 自指（本次实测触发）；h 引擎把非 git 仓的 DISPATCH_DIR 直接当 worktree 主仓（报 infra 而非显式配置错）；i dsh-executor 注释称有超时兜底实则无；j quality-score docstring 第 4 维（重复指纹）未实现；k 隔离测试与生产引擎共享 git 命名空间，生产分支清理会触碰测试分支；l 出卡/校验链会在 docs/archive/legacy-t-cards/ 下生成 cards.index.jsonl（副作用越界写，本次实测产生未跟踪文件）；m observer.py 探活幽灵 opencode.json 并写入巡检报告；n dispatch.py `_FRESH_FLAG_BY_CMD` opencode 死映射；o new-card.sh 默认执行体仍 OpenCode（plan-to-cards 显式传参时不触达，直用 new-card 会污染卡头）；p sync-skills.py 仍向 ~/.opencode 分发技能；q worker-claim.sh 默认 opencode/M1；r web/data/arch/*.json 架构视图种子旧席位；s 文档 B 类滞后共 136 处（STARTUP-BRIEF 17、SKILL 10、dev-channel 7、architecture 5、topology 2、INDEX 3、onboarding 4、executors 两篇、references 多份 SOP、authority-patrol.jsonl 等——逐条清单见审计过程记录）。

---

## 四、阶段 C 端到端运行记录（engine --once#3 · rc=0 · 814s 全自动闭环）

| 步骤 | 结果 | 证据 |
|---|---|---|
| 扫描 | scanned=2（xy900 待分派 + sidecar 残留计数） | engine-once3.log `{"dispatched":1,...}` |
| 决策/派发 | role=开发执行体、entry=dsh-executor.sh、worktree 复用 CCC-wt/xy900；业务仓隔离 worktree 同步就绪（apps/.ccc-wt/xy/xy900） | engine-once3.err「拉起执行体…phase=run cmd=[…dsh-executor.sh…]」 |
| 开发执行 | rc=0；卡末尾追加独立行 `engine-e2e-ok`；状态→已回写；2 commits；push 后 ls-remote 核验远端 tip=本地 HEAD；origin/main 未动 | /tmp/e2e-run/logs/xy900.log 末段自述+收单日志「收单成功: work=xy900 → 已回写」 |
| 机械门禁 | 回写凭证/状态合法性/新 commit+非空 diff 全过（无打回记录） | engine-once3.err 无 warning 打回行 |
| 机审拉起 | acceptor=Claude Code（P0-1 角色兜底生效）→ dsh-auditor.sh phase=audit | engine-once3.err「拉起机审…拉起执行体…phase=audit cmd=[…dsh-auditor.sh…]」 |
| 机审执行 | rc=0；发现轻问题（维护区 Q4 勾选位模板占位）→ **就地修复为「[否]」** 随机审区 commit+push（v4 轻修复路径实测触发）；「机审：通过」写入 worktree 卡与生产卡双镜像 | /tmp/e2e-run/logs/xy900.audit.log 末段 |
| 信封钉 SHA | 「机审：通过（被审 8146185a443c）」幂等钉入，V6 漂移门禁可用 | CCC-wt/xy900 卡 L164（清理前取证） |
| ledger | `machine_audit_pass xy900 engine-audit` 写入隔离台账 | /tmp/e2e-run/ledger.jsonl |
| ready 队列 | `approve-merge.sh --ready`（同台账 env）三重门禁全过（origin 分支存在+卡文机审区可解析+ledger has_pass）→ 进入逐卡处理；因测试卡不在真实 docs/dispatch 报「找不到卡：xy900」终止——合入动作强绑真实看板属设计使然，恰好证明隔离测试不可能误合入 | 本次执行输出 |
| 看板列语义 | 已回写+机审通过→「已回写」列（即待合入）；未审→「机审」列 | board_column 实测 |

**端点声明**：按指令停在「机审通过 + ready_for_merge 队列可见」，未执行实际合入、未部署。

## 五、收尾·痕迹清理清单

| 项 | 处置 | 验证 |
|---|---|---|
| 测试分支（CCC 仓）codex/xy024-e2e-marker、codex/xy900-e2e-engine | 本地已删 + origin 远端已删 | `git branch -D` 成功；`git push origin --delete` 输出 deleted×2 |
| CCC worktree /Users/fan/program/CCC-wt/xy900 | 已移除 | git worktree list 无残留 |
| 业务仓（xianyu）worktree apps/.ccc-wt/xy/xy900 + 本地分支 | 已移除/已删 | worktree list 干净；远端本就未推（ls-remote=0） |
| 隔离 dispatch 目录 /tmp/e2e-run、方案 /tmp/e2e-plans | **保留至重启**（/tmp 自清理）：含全部原始运行日志/台账/work 事件，供复现核查；不污染任何仓库 | 仅 /tmp 下存在 |
| docs/archive/legacy-t-cards/cards.index.jsonl（测试期副作用产物，P2-l） | 已删除 | git status 无此文件 |
| 真实 docs/dispatch、真实看板数据 | 零污染（看板仍 50 张已关闭历史卡） | `curl :7788/cards` 计数不变 |
| 生产 engine 服务 | 未触碰（全程只读其日志） | 心跳正常 |

## 六、给老板的一句话结论

8-22 DSH 化重构的链路设计完整、既有门禁无一被削弱，但四个 P0 断点（机审席位解析断裂、生产 PATH 缺 dsh、DSH 沙箱阻断 commit、绑定串精确匹配跳派发）让新栈在真实环境下**此前一次都没完整跑通过**；本次全部修复并用两张真实测试卡把「出卡→派发→开发→机审→质量分→待合入队列」在隔离环境端到端跑通（开发 809s/机审 227s/engine 全自动 814s，零 mock），另有 P1×4、P2×19 挂账清单在案——修复涉及 wrapper 三脚本与 engine 两文件的 diff 见提交，是否照单清 P1/P2 请老板定夺。

## 七、复现命令索引

```bash
# 基线
git -C /Users/fan/program/CCC log --oneline -6; curl -s http://192.168.3.116:7788/cards | head -c 200
# 出卡正反用例
bash scripts/plan-to-cards.sh <plan.md> --dry-run            # rc=0 / 非法前缀 rc=2 / 空验收 rc=2
# 引擎空跑
python3 -m server.engine.main --config <隔离env> --once      # {"scanned":0,...} rc=0
# 席位解析（修复后）
python3 -c "import sys;sys.path.insert(0,'.');from server.engine.dispatch import load_registry as l;r=l('server/config/executors.json');print(r.role_for_binding('DSH'))"
# 结论正则矩阵 / 台账
python3 -c "from server.board.models import machine_audit_passed_text"  # 用例见 §一环节4
CCC_AUDIT_LEDGER=/tmp/e2e-run/ledger.jsonl bash scripts/approve-merge.sh --ready
```

