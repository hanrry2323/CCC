# CCC 冻结摸底调查报告（第三方只读取证）

- 调查时间：2026-08-28（Asia/Shanghai）
- 调查方式：只读命令实况取证（git 只读 / ps / lsof / launchctl list / crontab -l / 文件读取），未做任何写操作、未起停任何服务、未触碰 launchd/crontab/docker
- 权威仓：/Users/fan/program/CCC/
- 结论性质：实测取证；文档与实况冲突处两边并列记录

---

## 一、git 基线（权威仓 /Users/fan/program/CCC/）

### 1.1 当前分支 / HEAD / 工作区
- 当前分支：`main`，与 `origin/main` **完全一致**（同一 SHA）。
- HEAD：`691954f684b55a9b698edbd18f00dbcf914d1cc3`
- 工作区：**干净**（`git status` → `nothing to commit, working tree clean`）。
- 补充：`data/` 与 `docs/dispatch/cards.index.jsonl` 均被 `.gitignore` 忽略（`/data/`、`docs/dispatch/cards.index.jsonl`），故"工作区干净"只覆盖受跟踪文件，运行态数据全在忽略区（见 §5）。

```
git status → On branch main / Your branch is up to date with 'origin/main' / nothing to commit, working tree clean
git rev-parse HEAD main origin/main → 三值相同 691954f68
```

### 1.2 分支清单（实数）
- **本地分支 7 条**：`main`、`ccc-audit-v6`、`codex/ccc089-loop-infra-loop`、`codex/engine-refactor-e1e2`（挂在 worktree `/Users/fan/program/CCC-wt/backend-rework`）、`feat/047-unification`、`feat/frontend-rework`、`repair/scripts-v6-pin-plans-status`
- **远端跟踪 ref 7 条**：`origin/main`、`origin/HEAD`、`origin/codex/engine-refactor-e1e2`、`origin/codex/tst006-e2e-add-smoke`、`origin/feat/047-unification`、`origin/feat/frontend-rework`、`golive/main`（stale，见 §5）
- 另有非分支 ref：`refs/bundle/f3、f32、f33`（3 条 bundle 残留，见 §5）、`refs/stash`、约 150 条 tag（archive/*、board-*、v*）

### 1.3 领先 main 未合入的分支（含卡分支）
`git branch -a --no-merged main` 实列 3 分支（本地+远端各一条）：

| 分支 | 领先 main | 落后 main | 是否合入 | 备注 |
|------|----------|----------|---------|------|
| `codex/engine-refactor-e1e2`（本地+origin） | +9 | -3 | **未合入** | 挂 worktree；9 个提交为 engine E1 绞杀拆解（main.py 迁出 gate_checks/state_machine/adjudication/worktree_mgr）与终审补课 |
| `feat/047-unification`（本地+origin） | +3 | -233 | **未合入** | 3 个提交：047-P1 去轮询化、mx-plan-009 回写、ccc075 作废缓办 |
| `feat/frontend-rework`（本地+origin） | +7 | -3 | **未合入** | 7 个提交：ccc-plan-049 P0/P1 前端重构（dsh_compat 隔离层、死码删除、数据层拆五域） |

已合入/已完结：`origin/codex/tst006-e2e-add-smoke`（已合入 main 历史）、`ccc-audit-v6` 与 `repair/scripts-v6-pin-plans-status`（同指向已合入提交 998140b01）、`codex/ccc089-loop-infra-loop`（f903af10e 已在 main）。`origin/repair/scripts-v6-pin-plans-status` 已报 `gone`。

### 1.4 main 最近 15 条提交时间线
```
691954f68 | 2026-08-28 01:58 | docs(neutralize): A4 收尾补改——executors.example.json 槽位中性化 + 大脑 Agent 去 Claude Code 绑定
518a1ecb7 | 2026-08-27 16:39 | Merge remote-tracking branch 'origin/main'
ea30f5ce3 | 2026-08-27 16:20 | docs(neutralize): 工具架构三层定调中性化改写（A4 批次）
f903af10e | 2026-08-26 17:30 | merge: 合入批准 tst006
3105dc982 | 2026-08-26 17:28 | 机审(验收席): tst006 第4轮复审通过 · v4 全量重验证据落卡
ab0dabd02 | 2026-08-26 17:18 | Merge origin/main into codex/tst006-e2e-add-smoke
42cedc0ed | 2026-08-26 17:16 | fix(approve-merge): 信封识别补重申口径
c4dcce5cd | 2026-08-26 16:49 | 机审(验收席): tst006 三轮复审通过
f9bccaeac | 2026-08-26 16:46 | tst006 第9次回写: 独立复核刷新回写区证据
0e4e78873 | 2026-08-26 16:38 | Merge origin/main into codex/tst006-e2e-add-smoke
b671fb636 | 2026-08-26 16:35 | 机审(验收席): tst006 复审通过
3c535c7fc | 2026-08-26 16:24 | docs(plan): ccc-plan-049→050 改号
78292e889 | 2026-08-26 16:22 | docs(plan): ccc-plan-049 合入自动化研究报告
eb581d52f | 2026-08-26 16:20 | docs(plan): ccc-plan-049 前端架构重构研究定稿
d62d0ba87 | 2026-08-26 15:50 | Merge origin/main into codex/tst006-e2e-add-smoke
```
要点：main 最后一次业务动作在 08-26（tst006 合入 + 机审全链收尾）；08-27~08-28 的提交全部是**文档中性化**（freeze 的文档面动作），08-28 01:58 为最新。

### 1.5 其他
- `git stash list`：**5 条 stash**（`stash@{0}…{4}`），其中一条挂在已删分支 `codex/ccc046-observer-scheduler-enable` 上（见 §5）。
- 远端：仅 `origin`（`git@github.com:hanrry2323/CCC.git`）；`golive` 远端已不在 config，但 ref `refs/remotes/golive/main` 残留。

---

## 二、运行态

### 2.1 进程（CCC 相关）
- ⚠️ **`node /Users/fan/.npm-global/bin/dsh --profile web`（PID 804，label `com.deepseek.dsh-web`）存活中**：启动于 2026-08-26 21:23:27，已运行 2 天 40 分，CPU 0.2%（空闲），监听 `*:3080`。**这是当前唯一存活的 CCC 自动化链路进程（DSH 桥），隔离未彻底的核心证据。**
- `com.qb.data-engine`（PID 803，Python，业务仓 qb，监听 127.0.0.1:8091）——业务进程，非 CCC。
- 无 `server.engine.main` / `server.web.server` / `board.scheduler` / `watchdog-ccc` 任何 Python 进程。
- 无 `codex` / `opencode` / `claude` / `dsh --profile headless` 执行体进程。
- 孤儿残留：`ms-playwright chromium` crashpad handler 2 个（PID 86324/86326），另 Google Chrome for Testing 调试口 127.0.0.1:9222 在监听。

```
ps aux | grep -iE "ccc|dsh|engine|loopengine" → 仅 803(qb data-engine)、804(dsh web) 相关
ps aux | grep -iE "server\.web|server\.engine|board\.scheduler|watchdog-ccc" → 空
```

### 2.2 端口
| 端口 | 状态 | 归属 |
|------|------|------|
| `:7788` | **无监听（停）** | CCC web-server（08-26 20:14 起停） |
| `:3080` | **LISTEN** | dsh-web（PID 804，存活） |
| `:6100 / :6102` | 无监听 | ai-loop-router 中转（已退役，符合退役断言） |
| `:3456` | LISTEN | ssh m1-tunnel（com.fan.m1-tunnel，业务隧道） |
| `:8091 / :8092` | LISTEN | qb data-engine(PID 803)；8092 属主 PID 5817 已消失（见 §5） |
| `:9222` | LISTEN | Chrome for Testing（playwright 调试口） |

### 2.3 launchd（用户级 ~/Library/LaunchAgents，逐条）
**CCC 相关，共 11 个条目（2 活 / 4 禁 / 5 退役备份）：**

| 条目 | 状态 | 属性 | 说明 |
|------|------|------|------|
| `com.deepseek.dsh-web.plist` | **活 ⚠️** | RunAtLoad=true + KeepAlive=true | 自启+常驻；`node dsh --profile web`；:3080；含密钥环境变量（报告脱敏）。**开机自启活任务** |
| `com.deepseek.dsh-web-watchdog.plist.disabled-20260822` | 禁 | （改名禁用 08-22） | 原 30s 间隔看门狗，脚本 `~/.dsh/watchdog-dsh-web.sh` 仍存在（若恢复启用会强拉 dsh-web） |
| `disabled-ccc/com.ccc.board-scheduler.plist` | 禁 | （08-26 20:11 移入） | `.venv-hub/bin/python -m server.board.scheduler --watch --interval 60` |
| `disabled-ccc/com.ccc.engine.plist` | 禁 | （08-26 20:11 移入） | `.venv-hub/bin/python -m server.engine.main` |
| `disabled-ccc/com.ccc.watchdog.plist` | 禁 | （08-26 20:11 移入） | `/bin/bash scripts/watchdog-ccc.sh` |
| `disabled-ccc/com.ccc.web-server.plist` | 禁 | （08-26 20:11 移入） | `.venv-hub/bin/python -m server.web.server --port 7788` |
| `.retired-20260824-relay/com.ccc.ai-loop-router.plist` +3 bak | 退役 | （08-24 移入） | 中转路由，已退役 |
| `com.deepseek.dsh-web.plist.bak-*` ×4 | 备份 | — | 配置演进备份 |

- **同机非 CCC 业务条目（供知悉，非 CCC 自动化）**：`com.qb.data-engine`（活，PID 803）、`com.qb.order-gateway`（已加载，进程抖动/退出码1，见 §5）、`com.xianyu.worker`（活，PID 817）、`com.medio.healthprobe`（已加载，每 300s 探活）、`com.hp-kb.collector`（已加载，每日 02:00 采集）、`com.fan.m1-tunnel`（已加载，ssh 隧道）。
- **系统级**：`/Library/LaunchAgents`、`/Library/LaunchDaemons` 均无 CCC 条目（0 条）。
- `launchctl list` 现网加载中 **只有 `com.deepseek.dsh-web`（PID 804）属于 CCC 自动化链**；四个 `com.ccc.*` 全部不在加载列表。

### 2.4 crontab
- **1 条（活）**：`5 6 * * * cd /Users/fan && /bin/bash /Users/fan/.dsh/ccc-prod-health.sh >> /Users/fan/.ccc/logs/prod-health-cron.log`
- 该脚本为**只读巡检**（launchctl list + curl :7788/health + curl :6100 + df），不启动服务，但属**每日定时自跑活任务**，且**今天 06:05 已执行**（`prod-health-20260828.md` 生成，输出：com.ccc.* 四项皆"停"、web:7788=000、router:6100 已退役✓）。
- 无 `/etc/crontab`；`/etc/periodic` 为系统默认（daily/monthly/weekly），无 CCC 条目。

### 2.5 运行态时间线（隔离动作实锤）
- 08-26 20:11–20:15：四个 `com.ccc.*` plist 被移入 `disabled-ccc/`；`web-server.stderr.log`（1.6MB）、`engine.stderr.log`（8MB）最后写入均为 **08-26 20:14** → engine/web/board/watchdog 于该时刻停摆。
- 08-26 21:23：`com.deepseek.dsh-web` 进程启动并**存活至今**（晚于停摆 1 小时，未包含在停摆动作内）。
- 08-28 06:05：cron 健康巡检照常执行。
- 08-28 07:11：`data/cards/cards.index.jsonl` 被触碰（见 §5）。
- 08-28 07:35：`~/.dsh/patrol_report_latest.md`、`patrol_merge.log` 被更新（见 §5）。

### 2.6 Docker
- **未安装**（`docker: command not found`），无容器可查。

---

## 三、卡片与看板账实

### 3.1 总账（docs/dispatch/cards.index.jsonl，296 行记录）
按用户口径分类（实况状态字段为 已关闭/作废，映射如下）：

| 口径 | 实数 |
|------|------|
| 待分派 | **0** |
| 执行中 | **0** |
| 已回写 | **0** |
| 已关闭 | **288** |
| 打回 | **0** |
| 作废（含"已作废"2 + 带原因作废 6） | **8** |
| **合计** | **296** |

### 3.2 开放卡清单
- **无开放卡**（0 张）。全部 296 张均已关闭或作废；无一张处于待分派/执行中/已回写/打回。

### 3.3 文件卡落盘实况
- `docs/dispatch/` 下活动卡文件仅 1 个（受跟踪）：`docs/dispatch/tst/tst006-e2e-add-smoke.md`（状态**已关闭**，2026-08-26 合入批准）。
- 归档实体：`docs/archive/ccc-tasks/` 下 **295 个卡 .md**（9 个前缀：ccc/cd/cla/clw/hp/mx/qb/tst/xy）。296 索引 = 295 归档 + 1 活动，账实相符。
- 其余前缀目录（ccc/cd/cla/clw/hp/mx/qb/xy）在 dispatch 下为空。

### 3.4 机审 ledger / engine-metrics 最后一笔记录时间
- **机审 ledger**：`data/audit/ledger.jsonl`（4882 条），**末笔 2026-08-26T09:30:57Z（= 08-26 17:30:57 +0800）**，为 `approve_merge` + `quality_score`（tst006，pass:true）。
- **engine-metrics**：`~/.ccc/logs/exec/engine-metrics.jsonl`（917KB），**最后写入 2026-08-26 20:14**（与 engine 停摆同刻）；同目录 `worker-events.jsonl` 末写 08-26 16:47。
- engine 心跳：`~/.ccc/logs/engine.stderr.log` 最后写入 **08-26 20:14:22**。
- observer：`data/observer/last-run.json` 末跑 **2026-08-18 02:04**（此后未再跑）。
- 执行产物目录 `~/.ccc/logs/exec/`：约 136 个文件（ccc076–ccc095 及 tst006 的 audit/log/metrics/runN/test-evidence），最后活动 08-26。

---

## 四、自动化组件残留（"隔离不彻底"的实体盘点）

| 组件 | 在位情况 | 自启入口现状 |
|------|----------|--------------|
| `server/engine/`（main.py 228KB、observer.py 81KB、scheduler.py、dispatch.py、gates.py、metrics.py、cluster/pool/store/task/runtime_state） | **在位**（代码完整） | `com.ccc.engine` **已禁**；无进程 |
| `server/web/`（server.py 198KB、wall.py、brain.py、chat_bridge.py、exec_metrics.py、dsh_compat/） | **在位** | `com.ccc.web-server`（:7788）**已禁**；无进程 |
| `server/board/`（audit_ledger.py、validate.py、loader.py、plans.py、scheduler.py） | **在位** | `com.ccc.board-scheduler` **已禁**；无进程 |
| `scripts/` 出卡/合入/审计脚本：plan-to-cards.sh、new-card.sh、approve-merge.sh、redispatch-card.sh、archive-cards.sh、card-evidence.sh、dsh-card-maker.sh、dsh-auditor.sh、audit-merge-agent.sh、watchdog-ccc.sh、backfill-stale-audit.sh、sync-audit-ledger.py、validate-plans.sh、check-entry-docs.py 等 | **在位**（均存在） | 无独立自启；被禁的 watchdog plist 引用 `scripts/watchdog-ccc.sh` |
| **DSH 桥** `~/.npm-global/bin/dsh` + `~/.dsh/`（profiles/web+headless、watchdog-dsh-web.sh、run_executor.sh、run_patrol.sh、run_audit.sh、run_reingest.sh、sessions/、storages/、settings.yaml 含 LLM provider 配置） | **在位** | **`com.deepseek.dsh-web` 存活（PID 804，:3080，KeepAlive）⚠️**；watchdog 脚本被禁但文件在位 |
| git hooks / pre-commit | `.pre-commit-config.yaml` 定义了 ruff + card-validate 两个钩子，但 **pre-commit 未安装**（`command not found`），`.git/hooks/` 仅系统 sample → **本克隆门禁钩子未生效** | 无 |
| 运行时数据 `data/`（audit/ledger、cards/index、observer、quality、ports、dsh_compat） | 在位，全部 gitignored | — |
| `.venv-hub/`（被禁 plist 引用的 Python 环境） | 在位 | 无进程 |

**小结**：CCC 核心（engine/web/board/watchdog）已停且自启被禁；**但 DSH 桥（:3080）仍在运行且带 KeepAlive 自启**，加上每日 cron 健康巡检，自动化链并未完全断电。

---

## 五、异常与疑点（只记录，不评不修）

1. **隔离不彻底 · 活任务 ①**：`com.deepseek.dsh-web`（PID 804）仍存活监听 :3080，KeepAlive=true 开机自启；停摆动作（08-26 20:11–20:15）未覆盖它。
2. **隔离不彻底 · 活任务 ②**：crontab `5 6 * * * ccc-prod-health.sh` 仍为活条目，今天 06:05 已执行（脚本本身只读无害，但属"定时自跑"）。
3. **patrol 今天 07:35 有执行痕迹**：`~/.dsh/patrol_report_latest.md`、`patrol_merge.log` 更新于 08-28 07:35；但 cron / launchd 均**无 patrol 定时条目**，触发源未在定时层找到（疑为 dsh-web 内部调度或人工触发）；且本次执行**失败**（`OUT` unbound variable + 上报巡检页失败，因 :7788 不可达）。
4. **卡片索引被触碰**：`data/cards/cards.index.jsonl` mtime 08-28 07:11（服务停摆后仍有人/进程读写），与 patrol 07:35 同窗口。
5. **watchdog 恢复隐患**：`~/.dsh/watchdog-dsh-web.sh` 与 `reinject-uuid-polyfill.sh` 文件仍在；若 `com.deepseek.dsh-web-watchdog` 被误恢复启用，30s 内会强拉 dsh-web。
6. **文档 vs 实况**：仓内 `AGENTS.md`/`CLAUDE.md` 仍以"平台在运营"口径描述双入口/环节②审核合入中枢/看板 API/deploy/topology；实况 engine/web/board 已停、dsh-web 独活。08-27~08-28 的 main 提交在做**文档中性化**（A4 批次、去 Claude Code 绑定），中性化仍在进行中，尚未全覆盖。
7. **bundle 残留 ref**：`refs/bundle/f3、f32、f33` 三条（不属于 heads/remotes/tags 命名空间）。
8. **stale / 悬空 ref**：`refs/remotes/golive/main`（golive 远端已从 config 移除）；`origin/repair/scripts-v6-pin-plans-status` 报 `gone`；本地 `ccc-audit-v6` 与 `repair/scripts-v6-pin-plans-status` 同指向已合入提交（重复分支）。
9. **stash 残留 5 条**：含一条挂在已删分支 `codex/ccc046-observer-scheduler-enable` 上的 WIP。
10. **账实掩蔽**：`data/` 与 `docs/dispatch/cards.index.jsonl` 全被 gitignore → `git status` 干净掩盖了全部运行态数据与卡片账本（账本只存在于 ignored jsonl）。
11. **状态枚举漂移**：作废 8 张中状态文本不统一（"已作废"×2 vs "作废（原因）"×6），存在状态机取值漂移。
12. **进程抖动（业务仓）**：`com.qb.order-gateway` launchctl 状态为 1（上次退出码 1），PID 5680/8092 属主 5817 在采样间消失；`com.xianyu.worker` 存活。属业务仓，非 CCC，供知悉。
13. **孤儿浏览器残留**：`ms-playwright chromium` crashpad handler（PID 86324/86326）与 Google :9222 调试口在监听，自动化浏览器链路的遗留。
14. **大日志未轮转**：`~/.ccc/logs/engine.stderr.log`（8MB）、`web-server.stderr.log`（1.6MB）截至停摆时刻。
15. **dsh-web 日志停滞**：`~/.dsh/web.log` 最后写入 08-26 21:24（仅启动行），进程存活但日志停滞。

---

## 一句话总判

**git 基线干净（main=origin/main、工作区无脏、296 张卡零开放），但隔离未彻底：DSH 桥（:3080，KeepAlive 自启）仍在运行、cron 健康巡检仍定时自跑（今日 06:05 已执行），且今天仍有 patrol/卡片索引的触碰痕迹——重启前必须先停 `com.deepseek.dsh-web`、清理 cron 健康巡检条目与 `disabled-ccc`/watchdog 残留，否则自动化链路可在开机或看门狗恢复时自行复活。**
