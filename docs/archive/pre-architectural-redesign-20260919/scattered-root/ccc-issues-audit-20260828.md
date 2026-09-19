# CCC 问题深挖调查报告（第三方只读取证 · 2026-08-28）

- 性质：只读调查。全程未做任何 git 写操作、未起停服务、未动 launchd/crontab、未改删任何文件。
- 依据：仓内代码/文档/日志 + 仓外运行面（~/.dsh、~/.ccc/data、~/.ccc/logs）+ git 全史（log/show/diff/stash，只读）。
- 上轮基线报告：/Users/fan/program/ccc-freeze-audit-20260828.md（本报告引用其结论，不重复铺陈）。

---

## 一、流程断点全史（出卡 → 派发 → 执行 → 回写 → 机审 → 合入 → 部署）

> 证据源：docs/notes/ 教训与事故档（38 份）、docs/lessons.md（49 条 Lesson）、机审 ledger（4882 条）、git log（全 refs 命中 fix/打回/回滚/热修类 582 条提交）。

| # | 环节 | 断点 | 当时修复 | 修干净了吗（后绳） |
|---|------|------|----------|--------------------|
| B1 | 出卡/派发 | 批量出卡依赖链滥用：cla017-028 十二卡把数据流水线依赖误建成派发阻塞 depends_on，12 卡变 1 条串行；同仓并发闸门 registry.yaml max_concurrent:1 被忽略 | 解绑非真依赖、cla 并发 1→3、重启 engine | 机制层面解决；「只建代码级依赖」仍靠出卡人自觉，无强制闸门 → 后绳在 doc 层。证据：docs/notes/2026-08-18-batch-card-dispatch-lesson.md |
| B2 | 派发/执行/机审 | 08-22「工具收口」改中间环节全 DSH，引入 4 个 P0 断点：①机审席位交叉配对不认 DSH→机审静默跳过 ②生产 launchd PATH 无 dsh→派发必 127 ③DSH 默认沙箱阻断 worktree commit（headless 无审批通道）④绑定串精确匹配→store 角色推导为空→DSH 卡全跳派发 | 本轮 4 项全部修复并实测（开发 809s rc=0、机审 227s rc=0） | 4 个 P0 修了；P1 挂账未修：radon 缺失致质量分复杂度维度静默失效、run_audit.sh key 月配额 429 无监控、文档滞后 136 处 B 类、observer 幽灵探活、P2 一批。证据：docs/notes/2026-08-23-dsh-fullchain-audit.md §一/§三 |
| B3 | 机审门禁 | 门禁假绿 + 假阳性双发：①分支 worktree 缺 gitignored config.env → 主检出红、worktree 绿（门禁绿≠生产绿）②门禁命令按首个 ASCII 冒号切键值，在 pytest node-id :: 处腰斩 → exit 127 被当「测试真失败」误打回 | ①封闭化须隔离配置读取源 ②平台热修 test-evidence 优先全角冒号（main e21e974d2） | 平台侧修了；但「config.env 不在 worktree → 门禁环境不同」是结构性未解 → 后绳未断。证据：docs/notes/2026-08-24-tst-lessons.md |
| B4 | 机审→合入 | xy055 机审真值链断裂：ledger 有 machine_audit_pass（08-20T18:51Z）但 main 卡机审区是占位「（机审方填写）」，仍被合入（commit 6188bd929） | 08-22 硬化：账本单源化 + 分支信封证据 + 机审后漂移硬拒绝 | 单点已堵（判不追溯）；机制正确性仍全押在 approve-merge 实现 → 需重建时回归验证。证据：docs/notes/2026-08-23-xy055-incident.md |
| B5 | 机审/validate | C-locale 字节集漏认：v6_drift_gate [：:] 多字节括号 C locale 漏认规范字形→合入全量阻断；BSD sed 把「已关闭」截成单字节 0xE5 漏判（ccc068）；pytest 继承 UTF-8 故「本仓绿、部署红」双面证据 | 信封定位改字节字面量交替+全行锚定（176bfd7e9）；脚本顶部强制 LC_ALL | 修复落地；「部署环境(C)≠开发环境(UTF-8)」是反复出现的一类问题。证据：docs/notes/2026-08-24-ccc-locale-sed-byteslice.md + git 414b0b911/d160509b0 |
| B6 | 执行 | ccc083 执行体重启空转（B3 取证闭环） | 防旋三闸+会话探针（3bc16c7cb） | 已修。证据：git 3bc16c7cb |
| B7 | 出卡 | xy052 事故：出卡脚本 CARD 变量兜底误指最新既有卡，覆盖已有卡文件 | revert 逐字节恢复（c665d7b6e） | 卡内容恢复；根因后续用出卡原子化加固（3573c193e）。证据：git c665d7b6e |
| B8 | 出卡工具链 | new-card.sh 新增「先持久化后报错」语义（rc 5/6/7），调用方 plans.py convert_plan / plan-to-cards.sh 持「rc≠0⇒无卡」契约 → push 失败时纯 rm/unlink 回滚退化 → 孤儿 docs 提交+重复卡历史（ccc090 F1） | 执行体停止实现+如实回写+给处置选项；平台侧出卡原子化（3573c193e） | 已原子化；教训「改共享工具退出码语义必须枚举全部调用方」落档。证据：docs/notes/2026-08-25-ccc-lessons.md |
| B9 | 执行/回写 | git_sync 秒级回吃未提交编辑：_force_align_dispatch 把未 commit 的卡文件还原为 origin/main（tst005、ccc095 两度实证） | 纪律：改=add+commit+push 一气呵成；批量前 SIGSTOP 三 watcher | 流程纪律+临时手段；机制性风险仍在。证据：docs/notes/2026-08-26-ccc-lessons.md |
| B10 | 回写/机审 | ccc095 管理席直改卡未填维护区 → Doc-Gate 强制打回 + 审计熔断连锁 | 纪律（必须同步填维护区） | 靠纪律。证据：docs/notes/2026-08-26-ccc-lessons.md |
| B11 | 机审 | 机审第一轮通过率低：20 次「机审打回，状态落分支信封（防死循环）」提交（tst006×6 / ccc075×3 / tst004×2 / ccc081、ccc082、ccc088、ccc090、xy059、xy054、tst003、mx056、mx055 各 1） | 机制：engine 落信封（main.py:505）+ store 读信封（store.py:56/207）防死循环 | 防死循环机制在工作；但 20 次打回说明机审往返成本高。证据：git log --all --grep=打回（20 提交）+ server/engine/main.py:505 |
| B12 | 合入/部署 | FETCH_HEAD 竞态系列：deploy 与 git_sync 双侧并发竞态（38abb9f8a）、approve-merge pull 竞态（3b44c796c）、宽限窗 age 负值（0dfc3701c）、信封识别漏认复审型结论行致漂移基线钉死（42cedc0ed） | 双侧 --no-write-fetch-head、pull 走 origin/main ref、信封重申口径 | 均修；但竞态类热修在 08-24~26 密集出现 → 并发控制系统性脆弱。证据：git 38abb9f8a/3b44c796c/0dfc3701c/42cedc0ed |
| B13 | 前端/部署 | UI 自动迁移误删事故：M4 死样式自动清理语料假阴性误杀存活规则→整体回滚（1373c4fa4）；深度融合误删 /app 静态映射→旧书签 404（fe9c3f068）；静态资源版本戳丢失（1a358847d） | 各自 revert/fix | 修复到位；同属「自动清理/自动迁移误伤」反复事故。证据：git 三提交 |
| B14 | 机审记录 | ledger 探针噪声混入真值：audit-kind 1230 条中 conclusion=不通过 1151 条，抽样显示大量 work_id=b1/r1/ez1/ez2 等非真实卡号（卡片索引 0 命中）→ engine 心跳扫描把「无通过记录」写成「不通过」audit 记录；真打回仅 20 次，但账上读数 1151 | 无 | 未修 — ledger 语义需重建（探针/真值分离）。证据：data/audit/ledger.jsonl（4882 行，action 分布：machine_audit_pass 1253 / audit 1230 / infra 1033 / approve_merge 80 / quality_score 31） |

---

## 二、状态藏匿点全清单（账实不符的根）

> 通读 .gitignore（188 行）。凡被忽略 = git 层不可见 = 账实核对死角。本仓结构是「三份数据层」：仓内 gitignored data/、仓内 docs/dispatch/cards.index.jsonl 忽略副本、仓外生产数据根 ~/.ccc/data。

| 路径 | 内容（实测） | 写方 | 读方 | 账实风险 |
|------|--------------|------|------|----------|
| /Users/fan/.ccc/data/（仓外 · 生产数据根，522 文件） | cards/cards.index.jsonl（170834B@08-26 17:30:56）、observer/（468 文件，末写 08-26 17:31）、dsh/patrol-report-*.md（37 份 DSH 巡检报告）、ports/（12 份每日快照）、cluster.js、engine.lock、force_kill_ledger.json | 生产 web/engine/observer/DSH patrol | web:7788 生产看板 | 最核心藏匿点：完全在 git 层之外；与仓内副本分裂 |
| /data/（仓内 gitignored，.gitignore:168） | audit/ledger.jsonl（4882 条，末笔 08-26 17:30:57）、cards/index（296 行@08-28 07:11）、conversations(2)、observer(4，last-run 止 08-18)、ports(3，止 08-24)、quality(2，08-23)、dsh_compat(1) | engine/audit_ledger.py/loader/observer/quality-score | approve-merge/engine/web | 与生产 ~/.ccc/data 双写分裂；observer 仓内止 08-18 而生产 468 文件 → 两套观察数据 |
| docs/dispatch/cards.index.jsonl（.gitignore:169） | 296 行@08-26 17:34，md5=0386d152… | loader.py:220（dispatch_dir 回落写） | web server.py:1310 注释「陈旧双写残留」、plans.py:914/945 | 三份索引三份内容：与 data/cards md5=3788f8c9… 不同、与生产 home 副本 170834B 也不同 → 双/三索引分叉 |
| server/config/config.env（.gitignore:24） | 33 个运行时键（ENGINE/BOARD/WEB_PORT、DATA_DIR、CCC_WEB_PASSWORD_HASH、CLUSTER_TARGETS、CLUSTER_PORT_NAMES、CCC_BRAIN_* 等） | 人工 | 全部 server 栈 | worktree 天然缺此文件 → 门禁绿≠生产绿（tst004 实证）；凭证在忽略区 |
| server/config/executors.json（.gitignore:25） | 执行体注册表：验收=DSH dsh-auditor.sh、开发=DSH dsh-executor.sh、维护=DSH、只读=DSH headless、管理=Claude Code | 人工/收口脚本 | engine | 活配置与 example 漂移（P2-e 实测）；绑定心智全部 DSH |
| server/web/data/*.js（.gitignore:163-165） | 8 个前端派生数据文件（board.js/cluster.js…） | scheduler/export 重写 | web 前端 | 派生产物不入库，重建依赖脚本存在 |
| .ccc/ 内部 30+ 忽略项（:29-158） | chat/（119 文件会话）、verdicts/(1)、quarantines/(5)、board/index.json、warnings.json、stats/、engine-heartbeat.json、abnormal-reports/ 等 | engine/web/observer | 各组件 | 运行态全藏 git 层外；账实核对需要单独工具链 |
| docs/notes/*-ccc-patrol.md（.gitignore:178） | 今日 08-28 07:10 巡检报告：128 项发现（hp 48/cla 22/xy 20/mx 17/clw 8/qb 8/tst 3/cd 2），几乎全为「方案关联了不存在的任务卡」 | observer | 无人消费 | 问题清单本身被 gitignore → 发现问题也不进 git 账 |
| knowledge/.index/（:144） | KB 索引产物(1) | KB 采集 | brain | 可重建，低风险 |
| var/（:112）、.venv//.venv-hub/（:27/122） | 运行时/venv | 工具链 | 工具链 | 可重建 |
| vendor/loop-code/cli（:152-153） | 私有执行器二进制 | 外部 | 执行链 | 二进制不在版本控制 |
| ~/.dsh/（仓外） | profiles(web+headless)/sessions(59)/storages/skills/.agent-presets/run_executor.sh/run_patrol.sh/run_audit.sh/run_reingest.sh/watchdog-dsh-web.sh/reinject-uuid-polyfill.sh/settings.yaml | DSH | dsh-executor/auditor/card-maker | DSH 桥心智完全在仓外，无版本控制 |
| ~/.ccc/logs/（仓外） | engine.stderr.log(8MB@08-26 20:14)、web-server.stderr.log(1.6MB)、exec/（136 文件：ccc076-095 + tst006 的 audit/metrics/runN）、watchdog.log、health 报告 | engine/web/watchdog/cron | 排障 | 停摆后不再有；大日志未轮转 |

实测双索引分叉命令证据：
wc -l  → docs/dispatch/cards.index.jsonl 296 | data/cards/cards.index.jsonl 296
md5   → 0386d1527894fea102483fe68358a301  ≠  3788f8c9fabaadf6cdd1dfc528e691db
stat  → docs/dispatch 08-26 17:34:47 | data/cards 08-28 07:11:17 | ~/.ccc/data/cards 08-26 17:30:56(170834B)
写方证据：server/board/loader.py:220/225/228（index 路径三选）、server/web/server.py:1310（陈旧双写注释）、scripts/new-card.sh:50、scripts/approve-merge.sh:22/792/894（均标注「陈旧副本双写分裂」）。

---

## 三、DSH 现役耦合图（接触点逐条）

| 接触点 | 接哪个环节 | 实际干了什么 | 日志/实况证据 | 定性 |
|--------|-----------|--------------|----------------|------|
| dsh-web 进程（PID 804，:3080，RunAtLoad+KeepAlive） | 全链对话/代理入口 | 唯一存活的 CCC 链进程；自 08-26 21:23 起运行 2 天+ | web.log 仅启动行、末写 08-26 21:24；error 字样 628 行，反复 profile bundle "@deepseek-ai/dsh-mcp-client" declares no dsh.bundle | 隔离不彻底实体；自我观测缺失（日志停滞、启动错误反复） |
| cron 5 6 * * * ccc-prod-health.sh | 健康巡检 | 每日 06:05 只读巡检（launchctl list+curl 7788/6100+df）；今日 06:05 已跑 | prod-health-20260828.md：com.ccc.* 四项「(停)」、web:7788=000、router:6100 已退役✓ | 定时自跑活任务（被动无害） |
| ~/.dsh/run_patrol.sh | 巡检/全局核实 | DSH headless 跑通核实；08-28 07:35 有执行痕迹 | patrol_merge.log：末条 OUT unbound variable 失败；「上报巡检页失败（:7788 不可达）」 | 触发源不在 cron/launchd（疑 dsh-web 内部或人工）；本次执行失败 |
| ~/.dsh/run_audit.sh / run-executor.sh | 机审/取证 | DSH 只读审计；key 取自 run_audit.sh | fullchain-audit：key 月配额 429、plist key 与脚本 key 双源无配额监控 | DSH 桥运行面脆弱 |
| ~/.dsh/watchdog-dsh-web.sh | 常驻保障 | 30s 间隔强拉 dsh-web（3080 常在） | plist 已禁（08-22）；watchdog.log 显示 08-16/21 共 7 次 kickstart、08-22 17:21 job missing -> loaded | 文件在位，恢复启用即复活 dsh-web |
| ~/.dsh/.agent-presets/ | 出卡/执行/机审心智 | ccc-card-maker / dsh-executor / dsh-auditor 预设 | ~/.ccc/logs/watchdog.log：08-26 20:05:52→20:14:05 每 ~70s 一条 preset 变更告警（持续到停摆） | CCC watchdog 监控 DSH 预设 → 双向耦合 |
| ~/.ccc/data/dsh/patrol-report-*.md（37 份） | 巡检产物 | DSH patrol 报告落生产数据根 | 07:10 报告 128 findings | 问题产物无人消费、gitignored |
| executors.json 绑定 | 开发/验收/维护/只读 | 开发=DSH、机审=DSH、维护=DSH、只读取证=DSH headless、管理=Claude Code；备注明文「DSH 不稳回退 Claude Code/OpenCode」 | server/config/executors.json（08-22 工具收口现行态） | 整条执行+机审链主体 = DSH |
| :6100/:6102 中转 | 退休代理 | 已退役 | health 断言无监听 ✓ | 干净 |

「DSH 干了但干不好 / 干了但看不到问题」环节标注：
- 机审（DSH dsh-auditor）：20 次打回 + ledger 1151 条探针「不通过」 → 第一轮通过率低且真值混噪，账不可直接当数
- 质量分：radon 缺失 → 复杂度维度静默失效（P1-c 挂账，pytest 2 例红）
- 出卡（DSH ccc-card-maker）：模板 marker 串自指 → 验收标准字面不可满足（P2-g）
- 巡检（DSH patrol）：08-28 07:35 执行失败 + 上报失败；128 findings 无消费路径
- dsh-web 本体：进程存活但日志停滞、启动错误 628 行 → DSH 看不到自己的病

---

## 四、组件健康度与技术债

### 4.1 TODO/FIXME 实测
- 生产代码显式 TODO/FIXME ≈0（全仓 grep 精确到注释仅 1 处真 TODO：scripts/sync-skills.py:14「接入后填」；其余命中均为 State.TODO 枚举、# type: ignore、测试文件）。
- 含义：债不写在代码里，全在外部文档（docs/lessons.md 49 条、docs/notes/ 38 份、governance-debt 档）→ 代码内不可见债。
- 上帝文件：server/engine/main.py 228KB、server/web/server.py 198KB、server/engine/observer.py 81KB、server/web/wall.py（原 619 行，重构分支已拆未合入）。

### 4.2 已知脆弱点反推（修复提交/教训 → 同类隐患是否仍在）
| 脆弱点 | 史（修复提交） | 现状 |
|--------|----------------|------|
| 并发竞态（FETCH_HEAD/锁/索引） | 38abb9f8a、3b44c796c、0dfc3701c、42cedc0ed、8ec648795、f344d5063 | 多次热修后收敛；仍属并发控制脆弱类，需回归基线 |
| 双/三索引分裂 | ccc088 4df841c36（根治） | 未根治：本轮实测三份索引 md5/内容/mtime 各异 → 仍在分裂 |
| close-only 绕过 / 假关闭 | 22e83b7fc、d26c00eb2、b072a72a 教训 | 已硬化（全量 confirm），需重建时回归验证 |
| 机审信封 / 漂移基线解析 | 42cedc0ed、176bfd7e9、lesson 51 | 解析器脆弱（多轮结论窗口、字节字形）；audit_parser.py/adjudication.py 只在未合入分支 codex/engine-refactor-e1e2 |
| C-locale 双面证据 | ccc068（ed1a863c3）、414b0b911 | 部署环境≠开发环境问题反复出现 |
| config.env worktree 缺失 → 门禁假绿 | tst004（e21e974d2） | 结构性未解 |
| 打回防死循环信封 | main.py:505 / store.py:56,207 | 机制在 main，工作正常（20 次使用） |
| pre-commit 门禁 | .pre-commit-config.yaml 定义 ruff+card-validate | pre-commit 未安装（command not found）、.git/hooks 仅 sample → 门禁钩子当前未生效 |
| G4 全量 validate 未接入 approve-merge | governance-debt G4（08-16 登记） | 仍开放：approve-merge.sh:605 只跑 Doc-Gate verify_maintenance，无 server.board.validate 全量校验 → 红灯可合入 |
| G1 状态机机审位置文档冲突 | governance-debt G1 | 仍存：docs/CCC-PRIME-DIRECTIVE.md:80 = 待分派→执行中→机审→已回写→已关闭；server/engine/task.py:3/31 = 五态契约+六态枚举（机审在状态机外）→ 三种说法 |
| G2 异席隔离 vs 自验收 制度冲突 | governance-debt G2 | 未决（需老板拍板）：ENGINEERING-CANON「异席机审硬」vs DOC-PROTOCOL「自验收」 |
| G3 59 张 ccc 禁前缀卡 | governance-debt G3 | validate 常报 error（存量已闭环卡未豁免/未归档） |
| G5 测试白名单缺「作废」 | governance-debt G5 | 曾触发 hp009 假红；现状态枚举仍含括号变体（8 张作废卡状态文本 2 种写法） |
| key 双源无配额监控 | fullchain-audit P1-d | 429 曾发生；仍无监控 |

### 4.3 组件自启/运行状态（续上轮）
- 全部 server/engine、server/web、server/board、scripts 代码在位但无进程；自启已禁（com.ccc.* 移入 disabled-ccc/）。
- 唯一活组件 = dsh-web（:3080）+ cron 健康巡检。
- hooks：未安装（见上）。

---

## 五、未合入分支与 stash 盘点（只陈述事实与兼容性）

### 5.1 分支（3 条未合入）
| 分支 | 基 main | 领先 | diff --stat（合并区间） | 兼容性事实 |
|------|--------|------|------------------------|------------|
| codex/engine-refactor-e1e2（+origin，挂 worktree CCC-wt/backend-rework） | f903af10e 08-26 17:30 | +9 | 13 文件，+3908/-2585：engine E1 拆解（main.py 2801 行迁出 → adjudication 476/audit_parser 222/final_review 243/gate_checks 492/redline_rules 152/state_machine 578/worktree_mgr 980）+ 4 个契约测试文件 + registry/validate-plans 微调 | 代码兼容：main 自 f903af10e 仅 14 个 docs/.cursor/executors.example.json 中性化文件（git diff --stat f903af10e main 实测无任何 server/engine 代码改动）→ 干净可合 |
| feat/047-unification（+origin） | 1e22a443e 08-24 12:45 | +3 | 8 文件，+61/-26：legacy-chat 六页去 setInterval 轮询 + 2 个 docs | 与 main 兼容；与 feat/frontend-rework 互斥（同改 boardPage/consolePage/dshPage/opsPage/plansPage/roadmapPage.js） |
| feat/frontend-rework（+origin） | f903af10e 08-26 17:30 | +7 | 47 文件，+3184/-2521：前端数据层拆五域（data/*.js 新增、degrade.js、markdown.js/ports.js/state.js/utils.js 删除）+ wall.py 619 行删除 + server.py 62 行 | 与 main 兼容；与 feat/047-unification 互斥；wall.py 大改与当前 main 的 wall 存在较大面重叠 |

已合入/可弃：origin/codex/tst006-e2e-add-smoke（已入 main 历史）、ccc-audit-v6 与 repair/scripts-v6-pin-plans-status（同指向已合入 998140b01）、codex/ccc089-loop-infra-loop（f903af10e 已在 main）。

### 5.2 stash（5 条）
| stash | 基底 | 内容（diff --stat） | 事实 |
|-------|------|---------------------|------|
| @{0} | main a1a041bed | ccc/xy roadmap.md 微调（+16/-6） | 文档层，低价值 |
| @{1} | main a6e4ea00b | cla README/roadmap（+5/-30） | 文档层 |
| @{2} | main wip | cla roadmap（+4/-31） | 文档层 |
| @{3} | main 3670689ae | cla/hp/mx/xy roadmap+README（+26/-27） | 文档层 |
| @{4} | 已删分支 codex/ccc046-observer-scheduler-enable | observer.py +63 行真实代码 + server/deploy/com.ccc.scheduler.plist + .gitignore + notes 微改 | 唯一含代码的 stash，且其主题（observer 调度+plist）与重建基座直接相关 |

---

## 报告末尾三件套

### ① 问题总清单（编号 / 环节 / 分类 / 严重度 / 证据指针）

| # | 环节 | 分类 | 严重度 | 证据指针 |
|---|------|------|--------|----------|
| P01 | 出卡/派发 | 断点 | 中 | notes/2026-08-18-batch-card-dispatch-lesson.md |
| P02 | 派发/执行/机审 | 断点 | 高 | notes/2026-08-23-dsh-fullchain-audit.md（4×P0 已修、P1 挂账） |
| P03 | 机审门禁 | 断点 | 高 | notes/2026-08-24-tst-lessons.md（假绿+假阳性） |
| P04 | 机审→合入 | 断点 | 高（历史已堵） | notes/2026-08-23-xy055-incident.md |
| P05 | 机审/validate | 断点 | 高 | notes/2026-08-24-ccc-locale-sed-byteslice.md + git 414b0b911 |
| P06 | 执行 | 断点 | 中 | git 3bc16c7cb |
| P07 | 出卡 | 断点 | 高 | git c665d7b6e（xy052 覆盖事故） |
| P08 | 出卡工具链 | 断点 | 中 | notes/2026-08-25-ccc-lessons.md（退出码语义外溢） |
| P09 | 执行/回写 | 断点 | 高 | notes/2026-08-26-ccc-lessons.md（git_sync 回吃） |
| P10 | 回写/机审 | 断点 | 低 | notes/2026-08-26-ccc-lessons.md #3 |
| P11 | 机审 | 断点 | 高 | git log 打回信封 20 提交（tst006×6…） |
| P12 | 合入/部署 | 断点 | 高 | git 38abb9f8a/3b44c796c/0dfc3701c/42cedc0ed（FETCH_HEAD 竞态系列） |
| P13 | 前端/部署 | 断点 | 中 | git 1373c4fa4/fe9c3f068/1a358847d（自动迁移误删） |
| P14 | 机审记录 | 断点·藏匿 | 高 | data/audit/ledger.jsonl（1151 探针「不通过」/work_id b1-r1-ez1-ez2 非真实卡） |
| P15 | 账实 | 藏匿 | 高 | 三份索引 md5 分叉实测（loader.py:220/225/228 + web server.py:1310） |
| P16 | 账实 | 藏匿 | 高 | ~/.ccc/data 生产数据根 522 文件（observer 468 / patrol 37 / cards / ports） |
| P17 | 账实 | 藏匿 | 中 | .gitignore:168（/data/ 全忽略） |
| P18 | 账实/门禁 | 藏匿 | 高 | .gitignore:24-25（config.env/executors.json worktree 缺失 → 假绿） |
| P19 | 机审真值 | 藏匿 | 高 | ledger 在 gitignored data/，探针与真值混录（同 P14） |
| P20 | 运行 | 耦合 | 高 | dsh-web :3080 独活 + cron 活任务（上轮冻结报告 §2） |
| P21 | 架构 | 耦合 | 高 | server/config/executors.json（执行+机审全 DSH 绑定） |
| P22 | 运行 | 耦合 | 高 | fullchain-audit 差异 2/3/8（PATH/沙箱/429）；~/.ccc/logs/watchdog.log preset ALERT×8 |
| P23 | 运行 | 耦合 | 高 | web.log 停滞+628 行 error；patrol 08-28 128 findings 无消费；radon 静默失效 |
| P24 | 运行 | 耦合 | 中 | ~/.dsh/watchdog-dsh-web.sh 在位（恢复启用即复活 dsh-web） |
| P25 | 架构 | 技术债 | 中 | server/engine/main.py 228KB / server/web/server.py 198KB 上帝文件 |
| P26 | 质量 | 技术债 | 中 | pre-commit 未安装（command not found），.git/hooks 仅 sample |
| P27 | 合入 | 技术债 | 高 | approve-merge.sh:605 只跑 Doc-Gate，无全量 validate（G4 仍开放） |
| P28 | 文档 | 技术债 | 低 | CCC-PRIME-DIRECTIVE.md:80 vs task.py:3/31（G1 三说法） |
| P29 | 制度 | 技术债 | 中 | governance-debt G2（异席隔离 vs 自验收，需老板） |
| P30 | 质量 | 技术债 | 低 | 生产代码内联 TODO≈0，债全在外档（lessons.md 49 条） |
| P31 | 分支 | 技术债 | 中 | 047-unification 与 frontend-rework 互斥（同改 legacy-chat 六页） |
| P32 | 分支 | 技术债 | 中 | 3 未合入分支 + 5 stash（stash@{4} 含唯一代码 observer.py+63 挂已删分支） |

### ② 三个根因（各附支撑证据）

- R1 · 单一事实源缺失 → 状态账实分裂：卡索引/机审 ledger/观察数据散在三层（仓内 gitignored data/、仓内 docs/dispatch 忽略副本、仓外 ~/.ccc/data），且全部被 .gitignore 掩蔽 → git 层永远看不到真账。证据：三份索引 md5 分叉（0386d…≠3788f…、home 170834B@08-26 17:30）；loader.py:220/225/228 三选写路径；web server.py:1310 自注「陈旧双写残留」；机审 ledger 1151 条探针「不通过」与 20 次真打回同账混录；observer 仓内止 08-18 而生产 468 文件。
- R2 · DSH 既当主体又自我开发，运行面脆弱且自我观测缺失：开发/机审/出卡/巡检全部绑定 DSH headless，而 DSH 运行面（PATH/沙箱/配额/key/预设）脆弱、日志自我停滞。证据：executors.json 全 DSH 绑定；fullchain-audit 4×P0 + P1 挂账（PATH 127、沙箱阻断 commit、key 429、radon 静默失效）；20 次机审打回；dsh-web web.log 停滞 + 628 行启动 error；patrol 128 findings 无消费；watchdog 对 ~/.dsh 预设持续告警（20:05→20:14 ×8）。
- R3 · 无回归基线 + 并发/解析器脆弱 → 修复循环债：热修密集（08-24~26 每天多起），但门禁钩子未生效（pre-commit 未装、全量 validate 未接入 approve-merge），每轮「修复→新断点→再修复」。证据：P12 FETCH_HEAD 竞态 4 连修、P05 C-locale 双发、B11 打回 20 次、B13 revert 事故 3 起、G4 仍开放（approve-merge.sh:605 无全量 validate）、pre-commit 未安装实测。

### ③ 重建基座需要动的组件清单（信息性陈述）
- server/board/loader.py + server/web/server.py 索引读写链：单源化（生产 ~/.ccc/data 与仓内副本收敛为一，消除三份分叉）。
- server/board/audit_ledger.py + server/engine/main.py 机审出口：探针/真值分离，ledger 语义重建（区分 scan probe 与真实打回）。
- server/config（config.env / executors.json）：活配置纳入版本化默认 + worktree 一致性保证（消除假绿根因）。
- server/engine/：合入 codex/engine-refactor-e1e2 的拆解成果或同向重做（main.py 228KB 上帝文件）。
- server/web/ 前端：feat/frontend-rework 与 feat/047-unification 二选一合入/重做（消除互斥；wall.py 需独立核对）。
- scripts/approve-merge.sh：接入全量 server.board.validate（G4 闭环）+ 回归基线。
- .pre-commit / git hooks：安装并生效 ruff + card-validate 门禁。
- DSH 桥解耦：executors.json 绑定重定（DSH 回退业务侧）、~/.dsh 心智入仓或独立版本化、watchdog-dsh-web.sh/patrol 审计清理。
- docs/：中性化收尾 + G1-G5 治理债收敛 + 禁前缀卡豁免/归档。
- observer/patrol 产物消费：今日 128 findings 处置路径。
- 含代码 stash@{4}（observer 调度 + scheduler plist）评估收回或作废。

---

## 一句话总判

基线 git 干净（main=origin/main、296 卡零开放），但问题不在 git，而在三层藏匿的数据与 DSH 自证体系：账实分裂（三份索引+探针噪声）使状态不可信，DSH 全链自持主体使问题不可见（128 巡检发现无消费、日志自停滞、质量分静默失效），无回归基线使 20 次打回与 4 连修类循环债无法收敛——重建基座须先立「单一事实源 + 独立开发主体 + 强制门禁基线」三根柱。
