# CCC 基线对齐与现状盘点报告（2026-09-02）

> 日期：2026-09-02 · 范围：仅 CCC 平台本身（qx-map 等外部轨道仅作佐证引用） · 依据：本机（2017，192.168.3.116）只读实测
> 执行红线：全程只读；唯一写动作=A-1（09-01 报告提交 bfa3d5040，留本地不 push）；禁改代码/配置/服务/定时任务；密钥全部指纹化脱敏
> 复核口径：本报告所有结论附可复现命令与输出摘录；外脑（ZCode@M1）独立只读复核，不采信自报

---

## 一、基线对齐

### 1.1 git 基线

| 项 | 值 |
|---|---|
| 本地 main | `2f3936909341df261273ddc294d1bfbee664f73c` |
| 远端 origin/main | `2f3936909341df261273ddc294d1bfbee664f73c`（`git ls-remote origin main` 实测） |
| 差异 | 无（`[origin/main]` 对齐，无 ahead/behind） |
| 其他分支 | `codex/ccc089-loop-infra-loop` @ `1726b0180`，behind 34（非在役，历史分支） |
| 工作区在途 | 仅 `docs/notes/2026-09-01-ccc-issue-report.md`（已随 A-1 入库） |

复现：
```bash
git ls-remote origin main && git rev-parse main
git branch -vv && git status --porcelain
```

### 1.2 key 指纹三方一致复核（对比 08-29 基准 `2c7acd88cc34`）

方法：对密钥字符串取 `sha256` 前 12 位（脱敏，不落明文）；三方 = plist（com.deepseek.dsh-web.plist 现役）→ 进程（engine 80288 / dsh-web 96961 运行环境）→ 函数（`scripts/dsh-key.sh` resolve）。

| 来源 | sha256 前缀 | 说明 |
|---|---|---|
| plist（现役 dsh-web plist） | `e81c88daa504` | `PlistBuddy Print :EnvironmentVariables:OPENCODE_GO_API_KEY` |
| 进程 env | `e81c88daa504` | engine(80288)/dsh-web(96961) `ps eww` 抽取 |
| 函数 resolve（unset 后） | `e81c88daa504` | `source scripts/dsh-key.sh` 后取值 |
| **基准 2c7acd88cc34** | **不匹配** | 现役/历史任一来源、sha256/md5/sha1 任一算法均不命中；本机（仓库/qx-map/运行面）无该值任何记录 |

复现：
```bash
FP(){ printf '%s' "$1" | shasum -a 256 | cut -c1-12; }
# plist：FP "$(PlistBuddy -c 'Print :EnvironmentVariables:OPENCODE_GO_API_KEY' ~/Library/LaunchAgents/com.deepseek.dsh-web.plist)"
# 进程：ps eww -p 80288 | grep -oE 'OPENCODE_GO_API_KEY=\S+'
# 函数：(unset OPENCODE_GO_API_KEY; source scripts/dsh-key.sh; printf '%s' "$OPENCODE_GO_API_KEY")
```

**结论：三方内部一致（e81c88daa504）；与给定 08-29 基准不一致——基准所指密钥对象本机无可溯记录，疑基准为更早快照或所指非 OPENCODE_GO_API_KEY，需外脑确认基准口径。**

附带发现（⭐ 均与 053 阶段 3 相关）：
1. `~/.zshrc:40` 仍保留旧 key `sk-cFDJ…`（fp `c3bed002ce2c`，即 plan-053 标注的历史 429 源），交互 shell 的 `ANTHROPIC_API_KEY`/`claude` CLI 复用；`.bak-20260829-keyrot` 备份同源。**真枪复跑若走交互 shell，用的是旧 key**。
2. `disabled-ccc/com.ccc.engine.plist` 另存一支 key（len=85，fp `c68c77ee4c6e`）。
3. `scripts/ops/dsh_key_probe.py:29` 密钥源声明读 `com.ccc.engine.plist`（**已停用**）——陈旧单源，配额探针实跑时会读到停用 plist 的 key（版口与现役不一致）。

### 1.3 在役服务进程与监听端口清单

| 进程 | PID | 启动 | 监听地址 | 说明 |
|---|---|---|---|---|
| web-server（python -m server.web.server） | 80283 | 08-30 01:47 | `192.168.3.116:7788` | launchd com.ccc.web-server，KeepAlive=true |
| engine（python -m server.engine.main） | 80288 | 08-30 01:47 | 无监听 | launchd com.ccc.engine，KeepAlive=true |
| dsh-web（node dsh --profile web） | 96961 | 09-02 01:20 | `*:3080`（全网卡） | launchd com.deepseek.dsh-web 现役；**051 关停预案未执行** |
| m1-tunnel（ssh） | 78369 | — | `127.0.0.1:3456` | com.fan.m1-tunnel；litellm/SCNet 中转 |
| qb data-engine（python -m src.core.data_engine） | 803 | — | `*:8899` | com.qb.data-engine |
| medio healthprobe / hp-kb collector | 未运行 | — | — | launchd 标签在册但未装载（`-`） |
| com.qb.order-gateway | 8193 | — | 退出码 1 异常 | 非 CCC 平台范围，仅登记 |

复现：`lsof -nP -iTCP -sTCP:LISTEN`；`launchctl list | grep -iE 'ccc|dsh'`；`ps -o pid,lstart,command -p 80283,80288,96961`。

**核实项**：web 仅绑 `192.168.3.116:7788`（plist ProgramArguments `--host 192.168.3.116`）→ 127.0.0.1 探活 000 的结构性原因（见 §三.3）。

### 1.4 门禁链与定时任务在位情况

| 链 | 在位证据 |
|---|---|
| card_gate | `server/engine/main.py:4274-4278` 注册 `DispatchGate(name="card_gate", order=17, check=_card_gate)`，接线 `enforce_card_gate`（main.py:47） |
| dsh_quota | `scripts/dsh-key-check.sh`（429→ledger `dsh_quota_alert`+exit 2）被 `dsh-auditor.sh:23` / `dsh-card-maker.sh:20` / `dsh-executor.sh:21` 预检引用 |
| cron | 仅 1 条：`5 6 * * * /bin/bash /Users/fan/.dsh/ccc-prod-health.sh`（06:05 巡检） |
| launchd 在役 | com.ccc.engine / com.ccc.web-server（KeepAlive=true）/ com.deepseek.dsh-web；board-scheduler、watchdog 未注册（052 决定不恢复，属预期） |

复现：`crontab -l`；`launchctl list`；`grep -n "card_gate" server/engine/main.py | head`。

---

## 二、卡态盘点（B-1）

### 2.1 看板活跃卡全量清单

以看板 API 实测（`POST /session` 换 token → `GET /board/states` → `GET /board/recent`）：

| 状态 | 计数 |
|---|---|
| 待分派 / 执行中 / 已回写 / 打回 / 机审 | **0 / 0 / 0 / 0 / 0** |
| 已关闭 | 3（tst994 / tst997 / tst998） |
| 作废 | 3（tst995 / tst996 / tst999） |

- 账本 `~/.ccc/data/cards/cards.index.jsonl` 与 API 一致（6 条，全 tst 域）；最后写入 2026-08-30 12:54（tst996 作废收口）。
- **活跃卡 0 张、阻塞 0 张**；engine 心跳（09-02 实时）`scanned=0 dispatched=0 in_flight=0 audit_*_flight=0`，与空板一致。

复现：`GET /board/states`、`GET /board/recent`（需 Bearer）；`cat ~/.ccc/data/cards/cards.index.jsonl`。

### 2.2 051-055 五卡当前进度（08-30 以来状态变化）

| 编号 | 落盘 | 状态 | 08-30 以来变化 | 阻塞点 |
|---|---|---|---|---|
| ccc-plan-051（dsh-web 关停+巡检改造） | `docs/projects/ccc/plans/051-…md` | 待排期（待老板拍板） | 无变化；dsh-web 仍在跑（PID 96961, `*:3080`） | 老板拍板 |
| ccc-plan-052（部署扩展三期） | `052-engine-deployment-expansion.md` | 待排期 | engine/web launchd 已于 08-30 01:47 手动恢复（=第 1 期第 1-2 步实质完成），脚本集（deploy/kickstart/巡检服务段）未对齐 | 老板拍板（后续期数） |
| ccc-plan-053（全链自动化闭环） | `053-full-loop-automation.md` | 待排期（含 1 拍板点） | 阶段 1（真枪复跑）原定 08-30 15:00 触发未执行（维护期暂停） | 拍板点：值班节奏（7×24 vs 半自动过渡）；阶段 0 legacy 机审拆除前置 |
| ccc-plan-054（前端展示细化） | `054-frontend-display-refinement.md` | 待排期 | 无变化 | 老板拍板 |
| ccc-plan-055 | **无落盘**（方案池止于 054） | — | 仅 08-29 22:18 提交 `8ea98dd2b` 消息提及「ccc-plan-055 进度回写真值源守卫」，改动实体为 `server/board/plans.py`（双守卫），无 055 方案文件、无卡 | 编号空缺，需老板明确所指 |

**08-30 后流水**：01:47 服务重启（web 改绑 192.168.3.116；engine 载入新代码）→ 01:49-01:50 读闸收口/探活同源两提交（c0586fddc、cd7349bb2）→ 10:44-12:56 tst994/995/996 预演收口（11:18 tst994 自动合入关闭）→ 12:56 后进入维护期静默（活跃 0）。

复现：`ls docs/projects/ccc/plans/ | tail`；各方案文件头 `状态：` 行；`git log main --since=2026-08-30`.

---

## 三、流程排查（B-2 · 全程只读）

### 3.1 Relay 缺失告警（定位生产残留引用点）

- 源码：`server/config/loader.py:30` 注释 + REQUIRED_KEYS 集合均已移除 RELAY（2026-08-24 中转站退役后从必填移出）；`config.env` 仅留注释说明。
- 日志实证：`missing required config keys: RELAY_PORT, RELAY_UPSTREAM_URL` **仅文件头 15 行**（engine.stderr.log 自 08-03 追加，头部为 08-30 01:47 重启前旧运行段）；最后一次启动（日志行 51347）之后 0 次。
- **生产残留引用点（该修）**：`~/.zshrc:29-30` `export CCC_RELAY_BASE_URL=... / AGENT_PLANNER_BASE_URL=...`（均指已退役 `127.0.0.1:6100`）。其余运行面（plist/settings.yaml/config.env/disabled-ccc/*）无 RELAY 引用。
- 定性：现行运行体不再报错；残留为 shell 侧僵尸变量，清理即可（低风险）。

复现：`grep -c "RELAY_PORT" ~/.ccc/logs/engine.stderr.log`（=15）；`grep -rn "RELAY_" ~/.zshrc ~/.dsh/settings.yaml ~/Library/LaunchAgents/ ~/.ccc/engine.env | grep -v bak`。

### 3.2 作废状态告警（生产运行体版本对齐）

- 源码：`server/engine/store.py:50-52` 已含「已作废→State.VOIDED」别名归一（2026-08-24 直修，注释明示 ccc075/tst003 实证）；`main.py:2661` 卡头状态校验走 `base_state` 归一。
- 日志实证：`跳过未知状态卡: id=ccc075/tst003` 共 1634 次（817×2），**全部位于日志行 51347（=08-30 01:47 重启用 `Engine 持续模式启动`）之前**；重启后 0 次。
- 定性：**生产运行体（08-30 重启后）已与源码对齐，告警已消停**；09-01 报告按文件头部旧段误判为持续状态 → 按外脑口径修正。

复现：`LAST=$(grep -n "Engine 持续模式启动" ~/.ccc/logs/engine.stderr.log|tail -1|cut -d: -f1); awk -v L=$LAST 'NR>L&&/跳过未知状态卡/' ~/.ccc/logs/engine.stderr.log | wc -l`（=0）。

### 3.3 巡检/探活口径（127.0.0.1:7788 或 web 探活 · 该修清单，只列不改）

| # | 位置 | 现状 | 档位 |
|---|---|---|---|
| 1 | `/Users/fan/.dsh/ccc-prod-health.sh`（06:05 cron）`## HTTP` 段 `curl http://localhost:7788/health` | 恒 `000`（今日报告实证 `web:7788 000`）；服务段另查 board-scheduler/watchdog 两停用标签恒「(停)」 | **必修**：改 `192.168.3.116:7788`；服务段按 051 处置二清理化石标签 |
| 2 | `server/config/config.env` `CLUSTER_TARGETS=127.0.0.1:7788` | 集群巡检每轮 `nodes_checked:1, nodes_reachable:0`（engine 日志实证，白跑） | **必修**：改 `192.168.3.116:7788` |
| 3 | `/Users/fan/program/CCC/scripts/watchdog-ccc.sh:169` 默认 `CCC_WATCHDOG_WEB_HEALTH_URLS` 含 127.0.0.1 项 | 已适配（双地址任一 200 即健康），127.0.0.1 项冗余但无害 | 噪音（可去冗余） |
| 4 | `server/engine/observer.py:1386-1399` `_web_probe_url()` | 已用 WEB_HOST（plist 注入 192.168.3.116）优先；127.0.0.1 仅本地/测试回落 | 不改（设计内） |
| 5 | qx-map `sync/board-live.sh` / `ccc-poll.sh` / `daily-sync.sh` | 均已直连 `192.168.3.116:7788` | 不改（已对齐） |

复现：`cat ~/.ccc/logs/prod-health-20260901.md`；`grep -rn "127.0.0.1:7788|localhost:7788" scripts/ server/ ~/.dsh/ ~/qx-map/sync/*.sh`

### 3.4 看板 401（鉴权机制与预期行为）

- 机制：`server/web/server.py:290-293` — 2026-08-29 P1 收口「读闸全量入闸」，`_NO_AUTH_PATHS = {/health, /session, /config, /projects}` 之外的无凭据一律 401；写端点另由 `CCC_WEB_WRITE_AUTH=1` + Bearer 保护（config.env:31）。
- 实证：无凭据访问 `/`、`/board/states`、`/cards`、`/plans/list` 等 → 401；`POST /session`（账号 `ccc` + `~/.ccc/web-auth.txt` 口令）换 token 后同端点 → 200。
- 定性：**401 是设计行为（P1 收口），非配置故障**；09-01 报告 §二.4 未能取到卡列表系未走登录门。web-auth.txt 凭证与 `config.env` 的 `CCC_WEB_PASSWORD_HASH` 一致（sha256 前 12 位 `fc8b2df7c920` 双向印证）。

---

## 四、恢复条件（B-3）

### 4.1 opencode 配额现状（C1 真枪复跑前置）

- `scripts/dsh-key-check.sh` 实测：env 旧 key 线 exit 0、plist 新 key 线 exit 0（网关均非 429；探针等价 HTTP 200）。
- **结论：配额充足，C1 前置可通过**。注意：探针 `dsh_key_probe.py` 的密钥源声明（停用 plist）需先修正（见 §1.2 附带发现 3），否则管理席读到的配额对象是错 key。

复现：`bash scripts/dsh-key-check.sh --quiet; echo $?`（0=通过，2=429）。

### 4.2 待老板决项（5 条 · 每条带建议）

1. **051 拍板**：是否「关停 dsh-web(:3080) + 巡检脚本服务段改造」。建议：**是**（dsh-web 现仍全网卡暴露、零依赖，051 方案已具可验收步骤）。
2. **052 拍板（后续期数）**：第 1 期 1-2 步已实质完成（engine/web launchd 常驻已恢复），是否授权收口第 1 期 4-6 步（kickstart/deploy 服务集对齐 + 巡检服务段联动）。建议：**收口第 1 期**即可，2/3 期无强需求。
3. **053 拍板点**：真枪复跑前置两步——是否先执行「阶段 0 legacy 机审拆除」（禁未拆恢复自动派发）；值班节奏选 7×24 全自动 or phase2 半自动过渡 1-2 周。建议：**先拆阶段 0 → 半自动过渡**。
4. **054 拍板**：前端展示细化是否排期（依赖 049 组件线）。建议：与 049 合并推进节奏，暂缓无害。
5. **055 / push 授权**：055 编号无落盘，请老板明确所指；若为「真枪闭环合入后 push main 的执行授权」——建议：延续「合入即验收」红线，push 由审核席 approve-merge 一条龙授权（engine 仅 ff pull），不放开直推。

### 4.3 恢复开发前必须处理事项（按档）

**危险必修（不修则恢复开发带病）**

| # | 事项 | 依据 |
|---|---|---|
| R1 | 06:05 巡检 cron 探活改 `192.168.3.116:7788` + 服务段清理化石标签 | 每日假 `000` 持续污染健康证据链（§3.3#1） |
| R2 | `config.env CLUSTER_TARGETS` 改 `192.168.3.116:7788` | 集群巡检每轮 0 可达、白跑（§3.3#2） |
| R3 | 真枪执行链路 key 单源化：交互 shell 清旧 key 或 053 阶段 3 env 自包含（source dsh-key.sh） | 现状真枪若走 shell 用旧 key `sk-cFDJ…`（429 史源）（§1.2） |
| R4 | `dsh_key_probe.py` 密钥源改指现役 dsh-web plist | 现读停用 plist，配额探针对象错误（§1.2 发现3） |
| R5 | 053 阶段 0：legacy 机审（`_run_audit_worker`）未拆除前，禁恢复 engine 自动派发 | 双审冲突（053 阶段 0 定论；engine run_loop 与 phase2 同批已回写卡双审） |

**普通该修**

| # | 事项 | 依据 |
|---|---|---|
| M1 | `~/.zshrc:29-30` RELAY 僵尸 export 清理 | §3.1 残留引用唯一活点 |
| M2 | watchdog-ccc.sh 默认 URL 去 127.0.0.1 冗余项 | §3.3#3（低危，可选） |
| M3 | zshrc 旧 key 明示去留（若 R3 走自包含路线，则注销旧 export） | §1.2 发现1 |

**噪音（不处理无害，仅记录）**

| # | 事项 | 依据 |
|---|---|---|
| N1 | disabled-ccc/ 三 plist 与历史 .bak-* 文件滞留 | 不 bootstrap 即无副作用 |
| N2 | tst 卡作废清场已完成，cards.index.jsonl 与 API 一致 | §2.1 |
| N3 | `codex/ccc089-loop-infra-loop` 旧分支 behind 34 | 非在役，可按分支卫生清理（人发起） |

---

## 五、结论摘要（回执对应）

1. 报告路径：`docs/notes/2026-09-02-ccc-baseline-survey.md`
2. A-1 commit：`bfa3d5040`（留本地，未 push）
3. key 指纹比对：**三方内部一致（e81c88daa504；sha256 前缀）；与 08-29 基准 2c7acd88cc34 不一致**（本机无可溯对象，待外脑确认基准口径）
4. 卡态总览：看板活跃 0 张、阻塞 0 张（账本 6 张：3 已关闭 + 3 作废，全 tst 域；051-054 方案均待排期，055 无落盘）
5. 需老板决项 5 条（§4.2）+ 危险必修 5 条（§4.3 R1-R5）

> 红线声明：本调研未改动任何代码/配置/服务/定时任务；唯一写动作 = A-1 报告提交（09-01 报告追加外脑复核结论）。工作区已清场（A-1 后 `git status --porcelain` 为空；本报告入库后再核一遍）。