# CCC 底座全量现状与待修复项调查（T4 调研单 · 2026-09-02）

> 范围：CCC 平台本体全量（A 仓库/代码 · B 流水线闭环 · C 服务运行面 · D 配置通道 · E 数据状态 · F 测试验收 · G 清理冗余）
> 依据：本机（2017，192.168.3.116，`fan.local` Darwin 22.6.0 x86_64）只读实测 + 仓库源码 + 日志
> 执行红线：全程只读；唯一写动作 = 本报告落盘 + 仅含本报告的本地 commit（不 push）。未改任何代码/配置/服务/定时任务/数据库/方案/卡/ledger/远端。
> 取证口径：所有结论附「文件:行号」或「完整命令+关键输出摘录」；密钥/凭据一律指纹前缀（sha256 前 12 位）或「存在/缺失」，不回显明文。
> 复核口径：本报告区分【已证实】【未证实】【推测】【待老板决定】。

---

## 1. 调查范围、时间、机器、仓库、当前 HEAD 和工作区状态

| 项 | 值 | 证据 |
|---|---|---|
| 时间 | 2026-09-02 13:40–14:40（本地时区） | 会话记录 |
| 机器 | `fan.local` = 192.168.3.116（Mac2017，Darwin 22.6.0 x86_64） | `/usr/sbin/ipconfig getifaddr en0` → `192.168.3.116` |
| 仓库 | /Users/fan/program/CCC（git remote `origin git@github.com:hanrry2323/CCC.git`） | `git remote -v` |
| 分支 | `main` | `git rev-parse --abbrev-ref HEAD` |
| HEAD | `f61f9ee8900d9553d3294d2e58baa8fbd307c5e1`（短 `f61f9ee89`） | `git rev-parse HEAD` |
| 与远端 | ahead 3（本地 3 个未推送提交：f61f9ee89 勘误报告、d3f9ac446 基线报告、bfa3d5040 issue 报告）；origin/main=`2f3936909` | `git status` / `git log --oneline -5` |
| 工作区 | **clean**（`nothing to commit, working tree clean`） | `git status` |
| 其他分支 | `codex/ccc089-loop-infra-loop` @1726b0180（behind origin/main 34，历史分支） | `git branch -avv` |
| 报告目标文件 | 不存在（全新落盘，未覆盖既有报告） | `ls docs/notes/2026-09-02-ccc-foundation-full-survey.md` → No such file |

前置说明：本仓已有 09-02 凌晨《ccc-baseline-survey.md》（`d3f9ac446` 交付、`f61f9ee89` 勘误）。本报告不假设其结论正确，所有关键项均重新取证；发现两处需要**推翻/修正**其结论的项（见 §3.2 指纹、§4.1 通道错位）。

---

## 2. 一页结论：当前能否恢复 CCC；不能恢复的硬阻塞是什么

**结论：当前不能直接恢复全自动开发。** 底座代码、门禁、状态机、服务进程大多在位且自洽（engine/web 常驻、卡校验门、phase2 自动合入、进度双守卫均已接通）；但存在 **2 个硬阻塞 + 3 个高危误判点**，且其中一个直接否定「C1 前置已成立」的先前结论。

硬阻塞：
1. **H1 · 配额/通道判定不可信（假阴性 + 通道错位）**：`scripts/dsh-key-check.sh` 对 `http=000`（连接失败）静默 `exit 0`（通过），属假阴性缺陷；且探针打的是 `opencode.ai/zen/go`，而 DSH headless 执行面默认模型走 `local-litellm@127.0.0.1:3456`（M1 SCNet 隧道）——**探针通道 ≠ 真实执行通道**。ledger 实录 `2026-09-01T18:38:37 dsh_quota_alert …opencode.ai 429`（真实 429 存在）。恢复前必须先确定真实执行通道可用性并修探针，否则「误放行」与「误冻结」两种错误都可能发生。
2. **H2 · 回滚能力缺失 + 冒烟仅 /health**：全仓无自动化部署回滚（只有提交层 `reset --hard origin/main` 还原和 approve-merge 账本失败还原）；phase2 部署冒烟仅 `web :7788 /health` 探活，无真实功能冒烟。目标架构「部署及回滚」目前只有半段。

高危误判点（都会在恢复后立即触发错误行为）：
- **H3** · 06:05 巡检 cron 探活 `http://localhost:7788/health` 恒 `000`（web 只绑 192.168.3.116），每日污染健康证据链。
- **H4** · `CLUSTER_TARGETS=127.0.0.1:7788`，engine 内嵌巡检每 60s 一轮 `nodes_reachable=0` 白跑。
- **H5** · `~/.zshrc` 残留旧 key（fp `c3bed002ce2c`）与 RELAY 僵尸 export（`CCC_RELAY_BASE_URL`/`AGENT_PLANNER_BASE_URL` 均指已退役 127.0.0.1:6100）；恢复时交互 shell 环境会用错 key / 旧变量。

其余：看板空（活跃 0 卡，账本 6 张 tst 卡全终态）；051–054 方案均「待排期（待老板拍板）」，055 无落盘；engine 心跳 `scanned=0 dispatched=0` 静默运转正常；phase2 全自动合入 push 已接通（详见 §4）。

---

## 3. 架构对齐表：DSH / Claude Code CLI / CCC / 人工各自职责

依据：`docs/INDEX.md §0`、`docs/CCC-PRIME-DIRECTIVE.md`、`server/config/executors.json`（2026-08-27 三层分工）、`docs/projects/ccc/plans/053-full-loop-automation.md`。

| 角色 | 目标职责（053 方案口径） | 当前事实（实测） | 状态 |
|---|---|---|---|
| DSH（前端） | 前端开发管理、任务编排、出卡、开发执行（headless） | 开发执行体/维护执行体 = `scripts/dsh-executor.sh` → `dsh --profile headless`（executors.json「开发执行体」条目）；dsh-web `:3080` 常驻（PID 27151）；出卡自动化 = `dsh-card-maker.sh` / `plan-to-cards.sh` / `new-card.sh` | 在位，通道见 §4.1 疑点 |
| Claude Code CLI（后段） | 自动验收、合入、提交、部署、回滚 | `phase2.py` 消费「已回写」卡：CC 审核 → 合入 → 门禁 → 关闭+commit+push → 部署探活；CLI env 三件走 `dsh_gateway.py`（ANTHROPIC_BASE_URL=opencode.ai/zen/go） | 在位，无回滚（H2），审核通道 429（§4.1） |
| CCC 底座 | 意图/任务/执行/验收/合入/部署/冒烟/回滚串成自动闭环 + 门禁 + 证据链 | `server/engine/main.py` run_loop（派发门禁链 + 内嵌 scheduler + phase2 消费）、`server/board/*`（看板/方案/ledger）、`server/web/server.py`（HTTP+401 读闸+写鉴权） | 在位，自洽 |
| 人工 | 3 个入口：确定意图、验收最终功能、处理红线冻结 | 管理席=桌面端总调度（executors.json「管理席」无命令）；验收席=桌面端终审 + phase2 CC（自动）；审核合入=`scripts/approve-merge.sh` | 在位；自动合入（phase2）与人审（approve-merge）双轨并存，需老板定边界（§8 待决#6） |

---

## 4. 全自动流水线逐段状态表

> 逐段：当前入口 / 当前事实 / 证据 / 状态（通过|部分具备|缺失|异常|待核）/ 恢复前必须修复项。

### 4.1 通道与预检（贯穿前后段，先列）

| 项 | 事实 | 证据 | 状态 |
|---|---|---|---|
| opencode.ai 429 | ledger 实录 1 条 `dsh_quota_alert`（09-01 18:38:37）；09-02 凌晨基线报告经外脑三连复现 429×3 | `data/audit/ledger.jsonl` 末条；`docs/notes/2026-09-02-ccc-baseline-survey.md §4.1` | 【已证实】429 真实存在（opencode.ai/zen/go 通道） |
| 探针假阴性 | `dsh-key-check.sh`：`code="$(curl … || echo 000)"`，仅判 `==429`，其余（含 000）一律 `exit 0` | `scripts/dsh-key-check.sh:25,27,39-40` | 【已证实】缺陷（误放行） |
| 通道错位 | DSH headless 默认模型 provider=`local-litellm`，baseURL=`127.0.0.1:3456`（m1-tunnel→M1 192.168.3.140:3456）；而 dsh-key-check / dsh_gateway / phase2 探的是 opencode.ai/zen/go | `~/.dsh/settings.yaml`（yaml 结构读取：`llm-pi-ai.providers.local-litellm.baseURL=http://127.0.0.1:3456`、`apiKeyEnv=OPENCODE_GO_API_KEY`、`agent-default-model.provider=local-litellm`）；`server/engine/dsh_gateway.py:21-25`；`/usr/bin/nc -z -w 2 127.0.0.1 3456` → OPEN | 【已证实】探针≠执行通道。**推翻/修正凌晨报告「C1 前置不成立」**：429 只证明 opencode.ai 通道不可用，不证明 local-litellm@3456 不可用；反过来，若 local-litellm 可用而 429 未解除，preflight 会误冻结（over-block）DSH 派发 |
| local-litellm 真实可用性 | TCP 层可达（3456 OPEN）；未做真实模型请求（红线：不消耗配额） | `nc -z` 实测 | 【未证实】真实可用性需老板授权一次最小请求或等外脑代测 |

### 4.2 意图进入 → DSH 管理 → 卡/任务生成

| 段 | 入口 | 事实 | 证据 | 状态 |
|---|---|---|---|---|
| 意图进入 | 老板 ↔ 桌面端 / dsh-web :3080 | dsh-web 常驻 `dsh --profile web --trusted-host 192.168.3.116/140`（PID 27151，`*:3080`） | `ps`/`lsof` 实测 | 通过 |
| 出卡 | `scripts/dsh-card-maker.sh` / `plan-to-cards.sh` → `new-card.sh` | 批量/单卡生成 `docs/dispatch/<prefix>/<prefix>NNN-slug.md`；new-card 校验 registry 禁卡表（Forbidden prefix 断根） | `scripts/plan-to-cards.sh:1-129`；`scripts/new-card.sh:120-149` | 通过 |
| CCC 自研防派发 | registry ccc 前缀 `taskable:false, forbidden:true`（FORBIDDEN_CARD_PREFIXES） | CCC 自身改动不会进 engine 自动派发路径 | `docs/projects/registry.yaml:25-39` | 通过（红线语义成立） |

### 4.3 开发执行

| 段 | 入口 | 事实 | 证据 | 状态 |
|---|---|---|---|---|
| 派发门禁链 | `server/engine/main.py:run_once` + `_build_dispatch_gates` | 11 门禁按 order 链式执行：infra_cooldown(10)/retry_backoff(12)/short_session_breaker(15)/card_gate(17)/worktree_card_copy(20)/accepted(30)/parent_closed(40)/depends_closed(50)/cycle(60)/decision(70)/dsh_quota(75)/slot(80)/biz_isolation(90)/relay_probe(100)/submit(110) | `server/engine/main.py:4243-4476`；`server/engine/gates.py` | 通过 |
| 卡校验门 | `enforce_card_gate` | 仅 DSH 执行体+待分派卡做五项校验；非法→作废 + ledger `card_gate_reject` + alerts 留痕 | `server/engine/card_gate.py:150-181` | 通过 |
| 配额预检 | `_dsh_quota` gate → `preflight_gateway` | 429/拔 key 拒单 + ledger；TTL 缓存 300s；**预检自身起不来时放行不拒单** | `server/engine/main.py:4388-4400`；`server/engine/dsh_gateway.py:58-104` | 部分具备（受 4.1 假阴性影响；预检失败放行是设计但有窗口） |
| 执行 | `scripts/dsh-executor.sh` | 预检 → `dsh --profile headless`（danger-full-access）→ 测试证据截获 test-evidence.log | `scripts/dsh-executor.sh:16-127` | 通过（通道疑点见 4.1） |
| 防重复派发 | `pool.py` submit 同 work_id 抛错；marker 跨重启防双审 | | `server/engine/pool.py:47-75`；`server/engine/main.py:1442-1505` | 通过 |

### 4.4 CLI 验收 / 自动修复 / 红线冻结

| 段 | 入口 | 事实 | 证据 | 状态 |
|---|---|---|---|---|
| 后段审核 | `server/engine/phase2.py:consume_once`（run_loop 内嵌，main.py:4875/4945） | 消费全部「已回写」卡：CC 审核（PASS/REJECT/ERROR，指数退避重试）→ 合入 → 门禁 → 关闭+push → 部署探活 → 分支清理；ERROR 保留「已回写」待重试；REJECT 自动打回；工作区脏则整轮跳过+ledger 告警 | `server/engine/phase2.py:293-629` | 通过（有真实闭环） |
| 红线冻结（机器可判部分） | `_dispatch_blocked_by_ledger`（main.py:3433） | ledger 阻断派发；其余红线（密钥改动/force push/生产配置/CCC 本体改动）未见独立机器门禁，主要靠 approve-merge 密钥扫描（AKIA/私钥/token）与 card_gate/registry 前置 | `scripts/approve-merge.sh:204-221`；`docs/projects/ccc/plans/053` | **部分具备**：密钥/凭据类可机器扫；force push/历史改写/生产配置变更/不可逆操作**未见机器可判门禁**，仍依赖人 |
| 人工接力点 | phase2 REJECT/打回需人处理；管理席裁决；老板拍板 | 均存在显式 ledger 动作 | ledger 实录 | 通过（设计内人工节点） |
| 双审风险 | legacy 机审 `_run_audit_worker` 已从代码拆除（053 C0），run_loop 只留 phase2 CC | `grep -rn "_run_audit_worker" server/` → 无活引用；`main.py:4489,4727` 注释；`docs/ENGINEERING-CANON.md:147` | 【已证实】双审冲突已消解；**凌晨报告 R5 的前提（未拆除）已过时** |

### 4.5 合入 / commit / push / 部署 / 冒烟 / 回滚

| 段 | 入口 | 事实 | 证据 | 状态 |
|---|---|---|---|---|
| 合入（自动） | phase2 `merge_branch_to_main` | fetch + checkout main + merge --no-edit origin/<branch>；失败 abort 回原分支 | `server/engine/phase2.py:387-401` | 通过 |
| 合入（人工） | `scripts/approve-merge.sh`（老板「审核合入」入口） | 预检 → 机审/维护区四问门禁 → 密钥扫描 → 批处理 ready_for_merge → 合入；账本写失败=合入失败回滚 | `scripts/approve-merge.sh:53-221,800-807,1145` | 通过 |
| commit+push（自动） | phase2 `set_card_state(_CLOSED)` + `git push origin main` | 每卡独立 close commit（可独立 revert）；**直接 push main** | `server/engine/phase2.py:562-568,1145 关联` | 通过（但直推 main 与「产线不直推 main」红线的边界需老板明确，见 §8 待决#6） |
| 部署 | `deploy_and_probe` | web 未在听则拉起 `server.web.server`，然后 `/health` 探活 | `server/engine/phase2.py:462-488` | 通过（CCC 自身 web 部署） |
| 冒烟 | 同 `deploy_and_probe` | 仅 HTTP `/health` 200 判定 | `server/engine/phase2.py:442-447,485` | **部分具备**（无真实功能冒烟/业务探活） |
| 回滚 | — | 无自动化部署回滚；仅提交层还原（phase2 门禁失败 `reset --hard origin/main`；approve-merge 账本失败 checkout 还原；单卡 close commit 可独立 revert） | `server/engine/phase2.py:551`；`scripts/approve-merge.sh:807`；grep revert/rollback 全仓 | **缺失**（H2） |
| 状态回写/审计 | `record_action` → `data/audit/ledger.jsonl` | 追加写 + fcntl 锁 + tmp+rename；终态写回唯一索引（`_refresh_index`）；approve-merge 账本失败即合入失败 | `server/board/audit_ledger.py:3,64,274`；`server/engine/phase2.py:207-220` | 通过 |

### 4.6 逐段失败风险表（B 段核对「人工接力/隐式前提/重复消费/超时无终态/错误重试/无证据/回写污染」）

| 风险类 | 现状 | 证据 | 判定 |
|---|---|---|---|
| 人工接力 | 出卡、管理席裁决、老板拍板、REJECT 后续处置均为人 | registry/plans/phase2 | 设计内，非缺陷 |
| 隐式前提 | phase2 依赖工作区干净（脏则整轮跳过+ledger 告警，不静默）；dsh-key-check 依赖 `.venv-hub/bin/python`（存在，实测）；engine 依赖 config.env + executors.json（均在） | `phase2.py:599-629`；`dsh-key-check.sh:29` | 基本成立；`.venv-hub` 属隐式运行依赖（建议显式化） |
| 重复消费 | submit 同 work_id 防重；phase2 `_branch_in_main` 守卫「已合入但部署失败」重试场景跳过重复审核；marker 跨重启防双审 | `pool.py:47-75`；`phase2.py:505,535-536`；`main.py:1442-1505` | 通过 |
| 超时无终态 | 执行超时 `EXECUTOR_TIMEOUT_SECONDS=7200`；审核超时 1800s；scheduler 任务超时/异常隔离 | `config.env`；`scheduler.py:130-173` | 通过 |
| 错误重试 | 业务重试退避（retry_backoff gate）；CC 审核指数退避（max 默认 3）；基础设施冷却 60s/熔断 5 次 | `main.py:4253-4260`；`phase2.py:306-337` | 通过 |
| 成功但无证据 | 看板观测「已关闭但无机审通过（假关闭红旗）2 张」；机审命中率台账 100% | `~/.ccc/data/observer/observation-2026-09-02.md`（Loop Observer 产物） | **异常**：存在「关闭但无机器通过证据」路径（关闭可由人工/approve-merge 触发，非缺陷本身；但观测口径提示需明确证据链） |
| 回写污染 | 进度双守卫（缺卡跳过 + 单调保护）已消解 08-29「卡宇宙收缩批量回退」事故 | `server/board/plans.py:913-1038` | 通过（§6 详核） |
| CCC 自身改动误入派发 | registry ccc=forbidden + card_gate 前缀校验 + new-card Forbidden 拦截 | `registry.yaml:25-39`；`card_gate.py:101-112`；`new-card.sh:120-149` | 通过（断根） |

---

## 5. 待修复问题清单（P0/P1/P2/P3）

> 每项：现象 / 根因或未知点 / 影响 / 证据 / 复现命令 / 推荐修复方向 / 是否涉及红线。

### P0（恢复前必须修，否则恢复即失败/误放行/误冻结/证据链失效）

**P0-1 配额/通道探针假阴性 + 通道错位（H1）**
- 现象：`dsh-key-check.sh` 对 `http=000`（连接失败/超时）静默 `exit 0`；且探针打 opencode.ai/zen/go，与 DSH headless 实际执行通道（local-litellm@127.0.0.1:3456）不一致。ledger 确有 09-01 18:38 `dsh_quota_alert`（429）。
- 根因/未知点：`code="$(curl … || echo 000)"` 只判 429；000 落入「else → exit 0」。（未知点：local-litellm@3456 真实可用性未证实。）
- 影响：恢复后 A) 若 429 未解除 → DSH 派发/审核被 preflight 拒单（误冻结，即使 local-litellm 可用）；B) 若网络抖动 → 000 假通过 → 真枪静默失败循环。**C1 前置判定不可信。**
- 证据：`scripts/dsh-key-check.sh:25,27,39-40`；`server/engine/dsh_gateway.py:21-25`；`~/.dsh/settings.yaml`（local-litellm baseURL=127.0.0.1:3456）；ledger 末条。
- 复现：`bash scripts/dsh-key-check.sh; echo $?`（网络断时 exit 0）；`nc -z -w 2 127.0.0.1 3456`（OPEN）。
- 推荐方向：把 000/网络类单独判为非通过（区分「通过 / 429 / 网络异常」三态），探针改打真实执行通道（local-litellm@3456 或按 051/053 决定），并在管理席工具（`dsh_key_probe.py`）同步。
- 红线：无（只改探针逻辑与配置，不动业务/密钥）。

**P0-2 06:05 巡检 cron 探活恒 000（H3，即凌晨报告 R1）**
- 现象：`/Users/fan/.dsh/ccc-prod-health.sh:13` 用 `http://localhost:7788/health`，web 只绑 `192.168.3.116` → 每日产出 `- web:7788 000`，污染健康证据链。
- 根因：探活地址与 web 绑定地址不一致（`server/web/server.py` 以 `--host 192.168.3.116` 启动，实测 127.0.0.1:7788 → 000）。
- 证据：`/Users/fan/.dsh/ccc-prod-health.sh:13`；实测 `curl http://127.0.0.1:7788/health` → 000，`curl http://192.168.3.116:7788/health` → 200。
- 复现：`bash /Users/fan/.dsh/ccc-prod-health.sh` 后查看输出文件。
- 推荐方向：改 `192.168.3.116:7788`；服务段（`ccc-prod-health.sh:8`）同步清理 board-scheduler/watchdog 化石标签（052 决定不恢复，恒「(停)」）。
- 红线：涉及 `~/.dsh/` 运行面文件 → 修改需老板授权（本次只列不改）。

**P0-3 CLUSTER_TARGETS 白跑（H4，即凌晨报告 R2）**
- 现象：`config.env CLUSTER_TARGETS=127.0.0.1:7788` → engine 内嵌巡检每 60s `nodes_checked:1, nodes_reachable:0` 白跑（web 不在 127.0.0.1 听）。
- 证据：`server/config/config.env`；engine 日志实测 `内嵌巡检 cluster-collect: {'nodes_checked': 1, 'nodes_reachable': 0, …}`（09-02 实时）。
- 复现：`grep -n CLUSTER_TARGETS server/config/config.env`。
- 推荐方向：改 `192.168.3.116:7788`（同时核对 `CLUSTER_SERVICES` 三服务口径）。
- 红线：配置改动，需老板授权（本次只列不改）。

**P0-4 zshrc 旧 key + RELAY 僵尸变量（H5，即凌晨报告 R3/M1）**
- 现象：`~/.zshrc` 仍 export 旧 key（fp `c3bed002ce2c`，09-02 实测）与 `CCC_RELAY_BASE_URL`/`AGENT_PLANNER_BASE_URL`（均指已退役 127.0.0.1:6100）。
- 影响：恢复时若真枪/巡检走交互 shell，会用旧 key / 旧变量（429 史源），或读到已退役 RELAY。
- 证据：`grep -nE 'RELAY|PLANNER|6100|API_KEY|export ' ~/.zshrc`（行 28-43）；zshrc key noNL fp=`c3bed002ce2c`（复现：`grep -oE 'sk-[A-Za-z0-9_-]+' ~/.zshrc | head -1 | …shasum`）。
- 推荐方向：`dsh_gateway.py` 的 `cli_env` 已实现 env 自包含（不经 shell），恢复建议走该路径并注销/清理 zshrc 旧 export。
- 红线：`~/.zshrc` 为运行面，修改需老板授权（本次只列不改）。

**P0-5 回滚能力缺失 + 冒烟仅 /health（H2）**
- 现象：目标架构要求「部署及回滚」，当前仅提交层还原（`reset --hard origin/main`、approve-merge 账本失败 checkout 还原、单卡独立 close commit 可 revert），**无自动化部署回滚**；冒烟仅 `/health`。
- 证据：`grep -rniE 'revert|rollback|回滚' server/engine server/web scripts/*.sh`（仅提交层还原，无部署回滚实现）；`phase2.py:462-488`。
- 推荐方向：把「冒烟=真实功能探活」「回滚=上一版本 checkout + 探活回退」纳入 053 后续阶段或单独方案；恢复期可先以「部署失败即保留已回写待重试 + 人工回退」兜底。
- 红线：涉及部署/生产 → 新能力开发，需老板排期。

**P0-6 恢复后 phase2 自动合入 push main 的行为边界（H6）**
- 现象：run_loop 已接通 `phase2.consume_once`（`main.py:4875,4945`），一旦有「已回写」卡即自动 CC 审核→合入→push main→部署→关闭；与「产线不直推 main / 审核合入=人审环节②」的红线口径存在张力。
- 证据：`server/engine/main.py:4871-4880,4944-4948`；`phase2.py:562-568`；`docs/INDEX.md §0`。
- 推荐方向：老板明确「恢复后 phase2 是否全自动合入」；若否，先以 `PHASE2_AUDIT_DRIVER` 或开关只做「审核+打回」，合入留 approve-merge 人审。
- 红线：是（合入/push 属红线语义）→ 需老板拍板。

### P1（应修，可在同一开发批次）

- **P1-1 `dsh_key_probe.py` 密钥源声明与现役不一致**：源码 `scripts/ops/dsh_key_probe.py:29` 声明读 `com.ccc.engine.plist`（其注释还写着「已停用」）；实测现役 engine plist 已重载且在役，且 engine/dsh-web 两 plist 的 key 同源（均为 fp `e81c88daa504`）——风险已降级为「声明过期」，但仍应更正注释/统一单源到 `dsh-key.sh`。
- **P1-2 executors.json「验收席」= legacy 双轨**：验收席绑定 `dsh-auditor.sh`，但 run_loop 实际验收=phase2 CC；`--audit` CLI（`main.py:4915-4940`）仍走 `_run_machine_audit_after_writeback`。两条路径并存易口径漂移，建议收敛或标注。
- **P1-3 INDEX.md:55 引用已删除卡**：`docs/INDEX.md` 第 55 行引用 `dispatch/T31-…~T35-…`，文件已不存在（`ls docs/dispatch/` 只有空子目录 + tst 卡）。
- **P1-4 直推 main 与红线的文档边界**：phase2 `git push origin main`（`phase2.py:565,525,555,589`）与「产线不直推 main」并存，需在 AGENTS/INDEX 写明「phase2 为唯一自动合入席」。
- **P1-5 冒烟/证据链口径**：Observer 观测「已关闭但无机审通过（假关闭红旗）2 张」——建议把「关闭必须有 phase2_pass 或 approve_merge 记录」纳入终态判定（防止人工关闭无证据）。
- **P1-6 401 读闸后的本地工具适配**：读闸收口后 `127.0.0.1:7788` 结构性 000（web 只绑内网地址）；本地工具/文档（如 `CCC_WATCHDOG_WEB_HEALTH_URLS` 默认双地址）需统一到 192.168.3.116。

### P2（优化/噪音可延后）

- P2-1 `dsh_gateway.py:21-22` 硬编码 `ANTHROPIC_BASE_URL/MODEL`（违反「零硬编码」铁律；建议 config 化）。
- P2-2 `watchdog-ccc.sh:169` 默认 URL 含 127.0.0.1 冗余项（双地址任一 200 即健康，无害）。
- P2-3 大量 git 历史分支 refs（`board-*`、`v0.*`、`archive/*`、`backup-pre-reset-2026-07-21` 等约 120 个）待清理（须先验证已并入 main）。
- P2-4 `server/web/dsh_reader.py` 运行时无消费方（仅 `test_dsh_reader.py` 引用）——待核后决定保留/归档。
- P2-5 `server/web/dsh_compat/` 空目录（仅 __pycache__，无源码、无引用）。
- P2-6 `server/web/data/board.js` 陈旧导出（已从静态白名单移除，SPA 零消费）。
- P2-7 `dsh-key-check.sh` 依赖 `.venv-hub/bin/python` 写 ledger（隐式依赖，建议显式）。
- P2-8 `~/.ccc/engine.env`（29B）疑似空残留。
- P2-9 `.trae/documents/`（stage5-8、relay-cleanup-plan）为历史规划文档，建议标注或归档。

### P3（噪音/历史文本，仅记录）

- P3-1 文档内大量「:6100/:6102 中转」「hub/relay」历史文本（archive/retired-tooling 等）——属史实，保留。
- P3-2 `legacy-chat/` 目录名带「旧对话页」，实为**现役 SPA 前端**（server.py 静态托管）——命名误导，建议文档澄清而非删除。
- P3-3 `docs/notes/` 每日 patrol 报告（`*-ccc-patrol.md`，gitignored，Observer 产物）——正常运行产物。
- P3-4 `dsh settings.yaml.bak-*`、`LaunchAgents/*.bak-*`、`disabled-ccc/*.bak-broken-json` 等大量备份文件。

---

## 6. 旧冗余与清理候选清单（五分类）

> 本单**禁止删除任何一项**；以下仅为建议。每项附「引用/执行路径判定」。

### ① 可清理（已确认不可达，删除无风险）
| 对象 | 证据（引用扫描/路径判定） |
|---|---|
| `server/web/dsh_compat/`（空目录仅 __pycache__） | `grep -rn "dsh_compat" server/ scripts/` → 0 引用；`git ls-files server/web/dsh_compat` → 未跟踪 |
| `scripts/pipeline-flow-verify.sh` | `grep -rl pipeline-flow-verify` → 0 引用（文件自含探针桩） |
| `scripts/ccc-run-inline` | 0 引用（Run Code 内存脚本辅助，已无调用方） |
| `~/.ccc/engine.env`（29B） | 内容为空/无键；`~/.ccc` 残留 |
| `~/.ccc/flow-events.jsonl.bak-*`（8 个） | 旧 Hub 时代事件日志备份（0718–0730），无消费方 |
| `~/.ccc/engine-active-tasks.json(.lock)`、`engine-hang-retries.json`、`engine-loop-heartbeat.json` | 旧引擎运行时文件（0718–0802），新引擎用 `~/.ccc/data` |
| `LaunchAgents/*.plist.bak-*`（engine/web/dsh-web 多处） | 无 bootstrap 即无副作用（N1） |
| `~/.dsh/settings.yaml.bak-*`（约 12 个） | 历史备份 |
| `__pycache__/`（server+scripts 共 19 处） | gitignore 覆盖，未跟踪 |

### ② 已确认不可达、可排入清理，但需先做一次 git 侧验证
| 对象 | 验证要求 |
|---|---|
| 历史分支 refs（`board-*` ~90、`v0.*` ~30、`archive/*`、`backup-pre-reset-2026-07-21` 等） | 逐个 `git branch --merged main` / 远端 ref 是否已并 main 后再删（本单未删） |
| `codex/ccc089-loop-infra-loop`（behind 34） | 非在役；确认无未推工作后按分支卫生清理（人发起） |
| `server/web/dsh_reader.py` | 确认运行时无消费方（现仅测试引用）后再归档 |

### ③ 只归档/保留（历史或设计内，勿动）
| 对象 | 理由 |
|---|---|
| `docs/archive/` 全量 + `RETIRED-2026-08-22.md` + `arch-dead-files.txt` | 史实/门禁清单 |
| `server/web/data/arch/*.json`（ccc/cluster/index/medio-0/qb/quanthive/qxmap） | `arch-dead-files.txt:3` 明示 arch 体系保留数据 |
| `.retired-20260824-relay/`（ai-loop-router plist + baks） | 中转站退役归档 |
| `disabled-ccc/`（board-scheduler/engine/web-server plist + broken-json bak） | 停用保留（052 决定不恢复）；dsh-key.sh 回退源仍在读其 engine plist |
| `.trae/documents/`、`docs/archive/ccc-legacy-2026-08-02/` 等 | 历史规划/迁移记录 |
| `~/.ccc/data/audit/ledger.jsonl`（5062 行） | 审计证据，禁删 |

### ④ 状态不明、必须先验证
| 对象 | 未知点 |
|---|---|
| `~/.ccc/bin/`、`bg-sessions/`、`engine-claude/`、`intent-splitter/`、`proposal-outbox/`、`prompts/`、`stress-matrix/`、`hygiene-stash/`、`loop-code/`、`opencode-pids/` | 是否仍有新引擎/新组件消费（本单未逐项下钻） |
| `docs/dispatch/` 下空子目录 ccc/cd/cla/clw/hp/mx/qb/xy | 空目录 git 不跟踪，磁盘残留；确认无卡后清理 |
| `scripts/ready-probe.sh` | 仅归档文档引用，当前无调用方 |
| `scripts/manual-audit.sh` | 被 `approve-merge.sh` 引用（live）——保留，勿当死码 |
| `~/.ccc/logs/exec/` 内 ccc076-080 旧卡日志 | 历史执行产物，确认新流水线不再生成后归档 |

### ⑤ 涉及生产或不可逆风险、必须老板单独批准
| 对象 | 风险 |
|---|---|
| `~/.dsh/settings.yaml` / `.credentials.yaml` / `~/.ccc/web-auth.txt` / `xfyun-api-key` / `zhipu-api-key` | 密钥/凭据，禁止触碰；本单未读取内容 |
| `data/audit/ledger.jsonl` 及 `ledger.jsonl.bak-*` | 审计证据，禁删 |
| 远端分支删除 / force 操作 | 不可逆 |
| dsh-web(:3080) 关停（051） | 全网卡暴露零依赖，但关停需老板拍板 |
| `~/.zshrc` 清理（P0-4） | 运行面，需老板授权 |

---

## 7. 测试与验收缺口（F）

- **测试规模（静态盘点，未运行）**：`server/tests/` 共 70 个测试文件（`test_*.py` + `test_*.sh`）；`scripts/tests/test-card-resolve.sh` 另在。按面分类：engine（~24）、board（~20）、web（~8）、kb（~7）、infra/sync/门禁（~8）、shell 门禁（2）。
- **为什么未运行**：红线「唯一允许写入=报告」；运行 `pytest` 会写 `__pycache__`/`.pytest_cache`（虽 gitignore，仍是文件写入），故只做静态盘点 + 检查既有产物（`.pytest_cache`、`server/tests/__pycache__` 存在；无 `coverage.xml`/junit 产物）。「最近运行结果」= **未证实**（无持续产物），仅能引用既有 `docs/notes` 内 pytest 绿断言（不采信为本次事实）。
- **隔离性**：`server/tests/conftest.py:10-37` 已做隔离（EXECUTOR_PROBE_URL 置空、DATA_DIR/audit ledger/机审注册表落临时目录、注入测试凭据）——「测试写生产账本」污染已被 R2 直修堵住（2026-08-24）。
- **已覆盖的闭环阶段**：派发门禁（test_card_gate/test_card_dispatch_gate/test_engine_gates/test_engine_dispatch/test_ccc083_antispin）、状态机（test_engine_task/test_engine_runtime_contract）、runtime sidecar（test_runtime_state/test_engine_audit_marker/test_engine_audit_backfill）、phase2（test_phase2/test_validator_closed_card_approval/test_writeback_gate/test_engine_pass_ledger）、web 鉴权（test_http_api/test_web_p0_auth/test_server）、方案进度（test_plans/test_plan_reservations）。
- **缺口（缺失测试）**：
  1. 无真机 E2E（tst 预演是最近似，但 3 关 3 废，非持续回归）。
  2. 无红线反例（密钥改动/force push/生产配置变更/不可逆操作 → 是否触发冻结）测试。
  3. 无回滚测试（无回滚实现）。
  4. 无断电/重启恢复（仅部分：test_engine_runtime_contract/test_infra_resilience 覆盖跨重启 marker）。
  5. 无重复消费并发测试（防重主要靠代码路径，未见专门并发用例）。
  6. 无空卡集/缺卡/作废卡混排（缺卡跳过有 plans 测试，缺「空卡集派发」用例）。
  7. 无配置漂移测试（config.env 与代码键、CLUSTER_TARGETS 与实际绑定漂移——本次实测即抓到 P0-3）。
  8. 无探针假阴性测试（http=000 该判不通过而误 exit 0 —— 本次实测即抓到 P0-1）。

---

## 8. 恢复开发前最小修复批次及依赖顺序

> 本单只调查不实施；以下为建议批序（依赖前置者排前）。

**批次 0（拍板前置，老板决定）**
- 待决#1 通道口径：确认真实执行通道（local-litellm@3456 vs opencode.ai）并授权一次最小请求验证（或外脑代测）；若以 local-litellm 为主，探针/预检改指该通道。
- 待决#2 051：dsh-web(:3080) 是否关停。
- 待决#3 052 第 1 期 4-6 步是否收口。
- 待决#4 053：真枪节奏（7×24 vs 半自动过渡）。
- 待决#5 055：编号所指（无落盘）。
- 待决#6 phase2 恢复后是否全自动合入 push（P0-6）——若不，则加审核-only 开关。

**批次 1（P0 必修，无依赖）**
- P0-1 探针三态修复 + 通道对齐（最优先，解除 C1 判定不可信）。
- P0-2 巡检 cron 探活地址 + 服务段化石清理。
- P0-3 CLUSTER_TARGETS 改绑。
- P0-4 zshrc 旧 key/RELAY 清理（或走 env 自包含路线）。

**批次 2（P1 应修，可与批次 1 合并）**
- P1-1 dsh_key_probe 源声明更正 · P1-2 验收席双轨收敛 · P1-3 INDEX 死链修复 · P1-4 直推 main 文档边界 · P1-5 关闭证据链口径 · P1-6 本地工具 401 适配。

**批次 3（P2 优化）**
- P2-1 硬编码 config 化 · P2-2 watchdog URL 去冗余 · P2-3 分支清理（先验证已合入）· P2-4/5/6 dsh_reader/dsh_compat/board.js 收口 · P2-7 依赖显式化。

**批次 4（能力缺口，建议入 053 后续或新方案）**
- P0-5 回滚能力 + 真实冒烟。

**批次 5（清理，人发起、逐项验证）**
- §6 ①② 分类项按先验证后清理执行；⑤ 类一律老板单独批准。

---

## 9. 不能确认的事项、证据缺口和需要老板拍板的事项

**未证实/证据缺口：**
1. local-litellm@127.0.0.1:3456 真实可用性（TCP OPEN 已证，模型调用未证——红线禁耗配额）。
2. pytest「最近运行结果」（本次未运行；无持续产物）。
3. `~/.ccc/bin/` 等 10 个旧目录是否有新消费方（未逐项下钻）。
4. phase2 `_branch_in_main` 重试守卫、`_refresh_index` 在 08-30 之后是否仍按预期工作（空板期无样本）。
5. dsh-web `web.log` 中 110 次「plugin tree failed to load」错误的时间线（现 tail 正常；历史启动失败已自愈，未逐段对账）。
6. ledger「09-01 18:38 dsh_quota_alert」之后是否还有新的 429 探测记录（未运行 dsh-key-check，避免耗配额）。

**需要老板拍板：**
- 待决#1 通道口径（决定 P0-1 修复方向）。
- 待决#2–#6（见 §8 批次 0：051/052/053/055/phase2 合入边界）。
- §6 ⑤ 类清理对象的授权。
- P0-2/P0-3/P0-4 涉及运行面/配置修改的授权（本单只列不改）。

---

## 10. 附录：脱敏命令输出、文件清单、引用关系与复现命令

### 10.1 运行面快照（09-02 实测）
- `launchctl list | grep -iE 'ccc|dsh'` → `80288 com.ccc.engine` / `27151 com.deepseek.dsh-web` / `80283 com.ccc.web-server`（board-scheduler/watchdog 未装载，052 预期）。
- `lsof -nP -iTCP -sTCP:LISTEN`（相关项）：
  - `Python 80283 192.168.3.116:7788 LISTEN`（web-server）
  - `node 27151 *:3080 LISTEN`（dsh-web）
  - `ssh 78369 127.0.0.1:3456 LISTEN`（m1-tunnel → apple@192.168.3.140）
  - `Python 58013 *:8899` = `python -m http.server 8899 --directory design-samples`（**非** qb data-engine；凌晨报告 §1.3 将 8899 标为 qb data-engine 系误标，特此更正）
  - `Python 803 127.0.0.1:8091` = `python -m src.core.data_engine`（qb data-engine 本尊，绑 127.0.0.1:8091）
  - `Python 22456 127.0.0.1:8092`、`node 15481 127.0.0.1:6767`（Paseo Daemon，非 CCC 组件）
- `crontab -l` → 仅 1 条：`5 6 * * * cd /Users/fan && /bin/bash /Users/fan/.dsh/ccc-prod-health.sh >> /Users/fan/.ccc/logs/prod-health-cron.log 2>&1`。
- 健康实测：`curl http://192.168.3.116:7788/health` → 200；`curl http://127.0.0.1:7788/health` → 000。
- engine 日志（`~/.ccc/logs/engine.stderr.log`，共 51347+ 行）：最后「Engine 持续模式启动」=行 51347；其前 15 行 `RELAY_PORT` 缺失告警、`跳过未知状态卡` 1634 次——重启后两者均为 0；最新 heartbeat `{"scanned":0,"dispatched":0,"in_flight":0,…}`；cluster-collect `nodes_checked:1, nodes_reachable:0`。

### 10.2 密钥指纹（sha256 前缀，脱敏）
- engine plist / dsh-web plist / engine 进程 env / dsh-web 进程 env / `dsh-key.sh` resolve：均为 **`e81c88daa504`**（无换行口径）。
- `~/.zshrc` 旧 key：**`c3bed002ce2c`**（无换行口径）。
- disabled-ccc engine plist：**`c68c77ee4c6e`**。
- **指纹口径重要更正**：以「带尾换行」方式对同一值取指纹得到 `2c7acd88cc34`。凌晨报告中的外脑基准 `2c7acd88cc34` 恰等于「现役 key + 换行」的指纹——即**基准所指密钥 = 现役 e81 同一对象**，凌晨报告「基准与运行面不匹配」结论应被推翻。复现：
  - `FP(){ printf '%s' "$1"|shasum -a 256|cut -c1-12; }`（无换行）→ e81…
  - `FPNL(){ printf '%s\n' "$1"|shasum -a 256|cut -c1-12; }`（带换行）→ 2c7…
- 三处真实密钥不一致：现役（e81）/zshrc 旧（c3bed）/disabled（c68c）为**三个不同对象**，必须靠 P0-4 单源化收敛。

### 10.3 ledger 与数据真值源
- `data/audit/ledger.jsonl`（5062 行，gitignore `/data/`）：追加写 + fcntl 锁 + tmp+rename；末条 `2026-09-01T18:38:37 dsh_quota_alert gateway opencode.ai 429…`；含 `tst994 phase2_pass`（08-30 03:18）、`tst995/996 card_void`、08-30 `phase2_alert 工作区脏`×6。
- `~/.ccc/data/cards/cards.index.jsonl`（6 条，全 tst 域：3 已关闭/3 作废，末写 08-30 12:54）——与 engine 心跳空板一致。
- 真值源关系（代码口径）：**卡文件（docs/dispatch/*.md 卡头状态）= 磁盘唯一权威**；运行时 sidecar（`EXECUTOR_LOG_DIR/state/cards.jsonl`，append-only，末条为准）只存流程态/重试计数；cards.index.jsonl 为派生索引；ledger 为不可改审计证据；方案进度由 `sync_plan_progress` 回写且带双守卫（缺卡跳过 + 单调保护，`plans.py:913-1038`）。`~/.ccc/data/audit-inflight/` 空（机审在途目录）。

### 10.4 测试清单（文件级，静态盘点）
70 个文件：engine（audit_backfill/cross_datadir/marker/card_seed/cluster/dispatch/gates/main/metrics/pass_ledger/runtime_contract/scheduler/task/v2v3_gate/phase2/pipeline_status/runtime_state/worker_routing/worktree_dirty/worktree_lifecycle/writeback_gate/card_gate/card_dispatch_gate/ccc083_antispin）、board（archive/column_audit/export/loader/queries/roadmap/scheduler/validate/visibility/plans/plan_reservations/project_registry/roles/role_skills/ccc_plan/card_header/docgate_q1/validator_closed_card_approval/ssot/t53_console_roadmap）、web（http_api/server/web_p0_auth/dsh_reader/brain/brain_kb/brain_stream/exec_metrics）、kb（indexer/mcp/query_cases/search/seed_integrity/service）、infra（git_sync/infra_resilience/50_turn_stress/advanced_review/audit_format_contract/audit_ledger/entry_docs/quality_score/skeleton）、shell（test_card-resolve.sh/test_release_healing.sh）。隔离由 `conftest.py` 保证。

### 10.5 关键复现命令汇总
```bash
# git 基线
git -C /Users/fan/program/CCC status && git rev-parse HEAD && git branch -avv
# 运行面
launchctl list | grep -iE 'ccc|dsh'; lsof -nP -iTCP -sTCP:LISTEN | grep -iE '7788|3080|3456|8899|8091'
crontab -l; curl -s -o /dev/null -w '%{http_code}\n' -m 8 http://192.168.3.116:7788/health
# 探针假阴性（复现缺陷）
bash scripts/dsh-key-check.sh; echo $?        # 网络断时预期 exit 0（缺陷）；429 时 exit 2
# 密钥指纹（脱敏）
FP(){ printf '%s' "$1"|shasum -a 256|cut -c1-12; }
FP "$(/usr/libexec/PlistBuddy -c 'Print :EnvironmentVariables:OPENCODE_GO_API_KEY' ~/Library/LaunchAgents/com.deepseek.dsh-web.plist)"
# 通道
nc -z -w 2 127.0.0.1 3456 && echo OPEN
# 日志口径
L=$(grep -n 'Engine 持续模式启动' ~/.ccc/logs/engine.stderr.log|tail -1|cut -d: -f1)
awk -v L=$L 'NR>L' ~/.ccc/logs/engine.stderr.log | grep -c 'RELAY_PORT'   # =0
awk -v L=$L 'NR>L' ~/.ccc/logs/engine.stderr.log | grep -c '跳过未知状态卡' # =0
grep 'heartbeat:' ~/.ccc/logs/engine.stderr.log | tail -1
# ledger
tail -1 /Users/fan/program/CCC/data/audit/ledger.jsonl
```

### 10.6 与凌晨基线报告的差异（本单新增/修正）
| 项 | 凌晨基线报告 | 本单结论 |
|---|---|---|
| 基准指纹 2c7 不匹配 | 判定不匹配 | **推翻**：2c7=同一 key 带换行指纹，实为匹配 |
| 8899 端口 | 标 qb data-engine | **修正**：为 design-samples 静态 http.server；data-engine 本尊在 127.0.0.1:8091 |
| R5 legacy 机审未拆除 | 列危险必修 | **修正**：`_run_audit_worker` 已拆除（代码零活引用），R5 前提过时；验收席=phase2 CC |
| C1 前置 | 判定不成立（429） | **修正/细化**：429 属 opencode.ai 通道；真实执行通道 local-litellm@3456 TCP 可达、可用性未证——前置结论需按通道口径重判 |
| dsh-web PID | 96961 | 现为 27151（09-02 03:58 重启）；051 关停仍未执行 |

---

*红线声明：本调查未改动任何代码、测试、配置、plist、shell 配置、数据库、方案、卡、ledger、服务状态与远端；唯一写动作 = 本报告落盘 + 仅含本报告的本地 commit（未 push）。工作区提交前已复核 clean。*
