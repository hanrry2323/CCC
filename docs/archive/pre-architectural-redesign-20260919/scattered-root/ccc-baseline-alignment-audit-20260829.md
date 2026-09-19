# CCC 基线对齐审计差异报告（2026-08-29 · 只读）

> 执行：Trae 会话（2017=fan@192.168.3.116；M1=apple@192.168.3.140；HP=192.168.3.131）
> 性质：全程只读取证，无写操作（git 仅 status/log/diff/restore 还原测试副作用，见 §六自证）
> 结论：**A 实锤冲突 15 · B 疑似 7 · C 一致 6**。最严重 10 条见 §五。

---

## 一、用过的命令清单（只读自证）

```
# 身份/连通
/usr/sbin/scutil --get ComputerName; /usr/bin/uname -a; /usr/bin/id; /sbin/ifconfig en0 | grep 'inet '
ssh -o BatchMode=yes apple@192.168.3.140 'uname; whoami; ifconfig'          # M1 连通
ssh -o BatchMode=yes hp@192.168.3.131 'ls /data/knowledge/pipeline/'        # HP 连通
# A 文档
ssh M1 'sed -n "1,170p" qx-map/AGENTS.md; sed -n "243,512p" qx-map/AGENTS.md'
ssh M1 'ls -t /Users/apple/qx-map/__archive__/decisions/ | head -8'
ssh M1 'grep -nE "192.168.3.116:7788|解冻|08-28" qx-map/AGENTS.md'
ls -la /Users/fan/program/ccc-{freeze-audit,issues-audit}-20260828.md /Users/fan/program/ccc-rebuild-phase*.md
# B 看板
lsof -iTCP:7788 -sTCP:LISTEN -P -n
curl -m5 -s -o /dev/null -w '%{http_code}' http://192.168.3.116:7788          # 2017 本机
ssh M1 'curl -m5 -s -o /dev/null -w "%{http_code}" http://192.168.3.116:7788' # M1
ssh M1 'cat -n qx-map/sync/board-live.sh | head -80; head -30 qx-map/sync/board-live.md'
grep -nE '7788|LocalForward|RemoteForward' ~/.ssh/config   # 2017
ssh M1 'grep -nE "7788|LocalForward|RemoteForward|3456|1080" ~/.ssh/config'
cat ~/Library/LaunchAgents/com.fan.m1-tunnel.plist
# C hp-kb（HP MCP Streamable HTTP：initialize→tools/list→memory_list）
curl -X POST http://192.168.3.131:8083/mcp ... tools/list / memory_list
# D 服务
launchctl list; ssh M1 'launchctl list | grep -iE "ccc|dsh|board|litellm|qx"'
lsof -iTCP -sTCP:LISTEN -P -n; ssh M1 'lsof -iTCP -sTCP:LISTEN -P -n'
crontab -l; ssh M1 'crontab -l'
curl -m5 -s http://127.0.0.1:7788/health; curl -m5 -s "http://127.0.0.1:7788/cards?page_size=1"
# E 数据
ls -la ~/.ccc/data/cards/; wc -l ~/.ccc/data/cards/cards.index.jsonl
find /Users/fan/program/CCC \( -name 'cards.index.jsonl' -o -name '*.index.jsonl' \) | grep -v .venv
wc -l /Users/fan/program/CCC/data/audit/ledger.jsonl; grep -c '"probe"' .../ledger.jsonl
cd /Users/fan/program/CCC && git status --short; git branch -a --no-merged main; git stash list; git log --oneline origin/main -3
.venv-hub/bin/python -m pytest server/tests/ -q; echo EXIT=$?
# F 配置
cat /Users/fan/program/CCC/server/config/config.env（任务书写的根 config.env 不存在，实为 server/config/）
cat server/config/executors.json; cat server/config/executors.example.json
# G 遗留
grep -rn "_run_audit_worker" server/engine/main.py; grep -rniE "delete.?branch|git branch -d" server/engine/
ls ~/Library/LaunchAgents/disabled-ccc/; cat ~/.dsh/ccc-prod-health.sh
ps -p 86493 -o pid,ppid,lstart,command=; curl -m3 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/api/health
```

---

## 二、总判

- 核心冲突集中在**「08-28 解冻新架构（Trae 开发主体 / ZCode 外脑）已定调，但 qx-map/AGENTS.md 仍停在 2026-08-27 三层定调+Trae/ZCode 停用口径」**，叠加**看板 192.168.3.116:7788 实际不可达导致 board-live 永远回退**、**hp-kb 记忆停在 08-19**、**部署面与脚本脱节（仅 web 裸进程）**、**pytest 基线红 2 项 + 全量跑写真实仓副作用未隔离**。
- 一致项：7788 绑 127.0.0.1、06:05 巡检 cron、06:30 daily-sync launchd、3456 litellm 唯一中转链路、索引唯一写点、web API 本地 200、CCC 仓 git 干净。

---

## 三、模块差异表

### A 文档口径对齐

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| qx-map/AGENTS.md 工具表「Trae 停用（2026-08-06 起）」+ 2026-08-27 三层表 | Trae 停用/历史主力入口 | 08-28 决策档《CCC解冻与开发架构定调-外脑TraeDSH三层》定「开发主体=Trae（第三方）」，审计正运行于 TRAE | 08-28 解冻决策未回写入口 | 入口文档与最新决策冲突，误导新会话 | **A** |
| 同上「ZCode 已禁用（2026-08-22）」 | ZCode 禁用 | 08-28 决策「外脑=ZCode 本会话」；同文件 Windows 备用行又称「ZCode 桌面端→SSH 连 M1」 | 决策未回写 + 文档自相矛盾 | 工具定位双轨 | **A** |
| AGENTS.md 看板快照段 L303/305 | 数据源 `http://192.168.3.116:7788/cards`（免鉴权、实时） | 7788 仅绑 127.0.0.1；2017 本机与 M1 经 192.168.3.116:7788 均 HTTP=000 | 部署只监听回环 | 看板唯一状态线路失效 | **A** |
| AGENTS.md「2026-08-27 三层定调」 | 桌面端/CLI/DSH 自动化值班 | 08-28 决策三层=外脑(ZCode)/开发(Trae)/运行时(DSH)，两者并存未标注 | 决策版本叠加未收敛 | 三层口径双源 | B |
| AGENTS.md 部署端表 xy 行 | xy `:8765` admin+`:8080` 静态，探活 ✅ | lsof 无 8765/8080；curl 127.0.0.1:8765/api/health=000 | 服务停但表未更新 | 探活/部署检查误判 | **A** |
| AGENTS.md 模型出口「旧中转站群全部无监听」 | 6100/6102 全死 | M1 `com.qx.relay-tunnel-6100`(ssh 70630) 仍在 127.0.0.1:6100 监听 | 声明与 M1 实况不符 | 出口描述失准 | B |
| AGENTS.md 多处「M1 /Users/apple/program/CCC 已退役归档 2026-08-22」 | 已归档 | 目录仍存在且为活 git 仓（last commit 691954f6 @08-28，含 .git/.venv/.trae） | 归档未物理执行 | 双写点隐患/路径幻觉源 | **A** |
| AGENTS.md 目录结构/部署端 | CCC 权威仓=2017 /Users/fan/program/CCC、web:7788 | 一致 | — | 无 | C |
| AGENTS.md 每日同步 06:30 | launchd 每日 06:30 | com.qxmap.daily-sync.plist 06:30 在位；08-28 已跑（sync-20260828-063003.log，10:13 机眠补跑完成） | — | 无 | C |
| AGENTS.md 出卡质量规则（2026-08-18 摘要） | 摘要指向 CCC onboarding §3.2.1 | onboarding §3.2.1 仍 08-18 定稿，无 08-23 两环节/环节① 口径 | 流程口径未随两环节模型更新 | 出卡归属表述滞后 | B |

A2 决策档引用链：

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| `ls -t __archive__/decisions/` 最新=08-28 解冻定调档 | 最新决策应被 AGENTS.md 引用 | AGENTS.md 全文无「解冻」引用；工具表仍 Trae/ZCode 停用 | 决策落档但入口未同步 | 最新权威未达入口 | **A** |
| `ls -t` 顺序 | — | `工具架构定调-2026-08-27.md` mtime 反而早于 08-08/08-09 档（文件名日期 vs mtime 矛盾） | 文件复制/改名保留旧 mtime | 决策时序判读失真 | B |

A3 交接单引用链：6 份文件全部在位（freeze 08-28 22:06 / issues 08-28 22:30 / phase1 08-28 23:10 / phase2 08-28 23:34 / fix 08-29 00:09 / fix2 08-29 00:37）。
**日期可疑**：3 份 phase2 文件名标 `20260830`，实际 mtime 08-28~08-29（超前命名）→ B。另 08-28 决策档引用 freeze-audit 路径为 M1 `qx-map/docs/notes/`，而交接单实际在 2017 `/Users/fan/program/`（跨机路径漂移）→ B。

### B 看板链路

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| lsof 7788 | 探活 `curl 127.0.0.1:7788` | Python 86493 仅绑 127.0.0.1:7788 | — | 与探活方式一致 | C |
| B2 两端 curl | AGENTS.md 称 192.168.3.116:7788 实时可达 | 2017 本机=000；M1=000 | 回环绑定 | 外部 Agent 无法直读看板 | **A** |
| board-live.sh + board-live.md | 「实时、TTL20s」 | 结构=3 次重试×2s+git 快照兜底；board-live.md 顶部「本地 git main（FALLBACK，滞后勿信）」生成 02:03:14 | API 不可达→恒走兜底 | 看板快照永远滞后 | **A** |
| B4 隧道 | — | 2017/M1 ~/.ssh/config 均无 7788 转发；m1-tunnel(launchd)=3456→M1:3456 仅此 | — | 无暴露 7788 的既有通道 | C |

### C hp-kb 记忆对齐

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| /codex/topics/ccc/ | 应含重建期记忆 | 143 条，**最新 updated_at=2026-08-19T16:28**（dispatch-5cards-08-19） | KB 写入自 08-19 后停更 | 外脑记忆盲区 | **A** |
| 全库 | — | 3483 条，最新=08-27（research/strategy-edge-update） | 采集/同步未写 KB | 重建期无记忆 | **A** |
| C3 MISSING | 重建期该有 | 08-28 解冻决策 / 08-28~29 六份交接单 / 验收规律 / 测试口径教训（py3.9 typing.Self、sync_plan_progress 副作用）**全 MISSING** | 未落库 | 外脑/检索拿不到新事实 | **A** |

### D 服务实况对齐

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| 2017 launchctl | 部署端表期望 CCC 服务在 | 无 com.ccc.web-server/engine/board-scheduler/watchdog；4 plist 在 disabled-ccc/(08-26)；web 为裸进程 86493(PPID 1, 00:45 起) | 08-26 停用 launchd 服务改裸进程 | 部署/kickstart 脚本找不到服务 | **A** |
| dsh-web | com.deepseek.dsh-web 运行 | node PID 804，监听 `*:3080`（2017 全接口） | — | 与 M1 仅 127.0.0.1:3080 不对称 | C |
| M1 launchctl | litellm 3456 | com.litellm.gateway(Python 77453) 127.0.0.1:3456 监听；stats 741 | — | 一致 | C |
| com.qxmap.board-live | 每 10 分钟刷新 | launchd 无 PID；log 停在 02:03（08-29） | 未加载/间隙 | 快照不再刷新 | B |
| 2017 crontab | 06:05 巡检 | `5 6 * * *` ccc-prod-health.sh ✓ | — | 一致 | C |
| 06:30 同步 | AGENTS.md 称每日同步 | 在 M1 launchd（非 cron）com.qxmap.daily-sync 06:30 | — | 一致 | C |
| D4 API | 200 期望 | 127.0.0.1:7788=200；/cards?page_size=1 返回 `{"cards":[{id tst997…}],total:2}` | — | API 形状正常 | C |

### E 数据一致性

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| ~/.ccc/data/cards/ | 1 主账本+1 lock | cards.index.jsonl(2 行)+.lock ✓ | — | 一致 | C |
| 仓内索引副本 | 应无第二写点 | find（除 .venv）无任何 *.index.jsonl | — | 唯一写点成立 | C |
| ledger probe | fix2 称 record_audit 增 probe 字段、infra 自动 probe=true | 4891 行**无任何 `"probe"` 字段**（字段集=ts/source/kind/action/…无 probe） | 打标逻辑未落地/历史未重写 | 机审 infra 与真值不可区分 | **A** |
| git 状态 | 干净 | 审计前后干净（期间 pytest 副作用已 restore）；无 no-merged 分支、无 stash；origin/main=1726b0180(phase2 merge) | — | 一致 | C |
| pytest 基线 | fix2「1264 passed, 2 skipped」 | **EXIT=1，2 FAILED**（test_card_dispatch_gate_remote_check、test_new_card_flock_concurrency）；根因=子进程 new-card.sh 调系统 python3.9 → `typing.Self` ImportError（venv 3.12 vs 系统 3.9） | 测试调真实脚本+解释器漂移 | 验收判据红、部署门禁会拦 | **A** |

### F 配置对齐

| 位置 | 文档说 | 实况 | 根因 | 影响 | 级 |
|---|---|---|---|---|---|
| config.env 路径 | 任务书写根目录 config.env | 根目录无；实为 server/config/config.env（gitignore 内） | 任务书路径与实况不符 | 取证路径修正 | B |
| config.env 内容 | DATA_DIR / 注册表 / 端口 | DATA_DIR=~/.ccc/data ✓；EXECUTOR_REGISTRY_PATH=server/config/executors.json ✓；7788/7789 ✓；但 CLUSTER_SERVICES 声明 engine/board-scheduler 服务实未运行 | 配置声明面>运行面 | 与 G2 同源 | **A** |
| /health auth | 写端点强 Bearer（CCC_WEB_WRITE_AUTH=1） | /health 报 `auth_configured:false`（未深究；写端点 404 无法断言） | 运行进程配置装载待核 | 鉴权实况存疑 | B |
| executors.json(活) vs example | phase2 称「example 对齐活配置」 | 活=08-22 收门口径（DSH 开发/机审+Claude Code 终审）；example=08-27 三层口径（执行会话/值班组件，不写死 DSH）→ **再次漂移** | 活配置未随 08-27 定调更新 | 「去 DSH 绑定」目标未达成 | **A** |
| litellm 3456 | 唯一中转站 | M1:3456=litellm；2017:3456=ssh m1-tunnel(-L 3456:127.0.0.1:3456) | — | 链路成立 | C |

### G 遗留项 8 条实况

| # | 交接单遗留 | 当前现状 | 证据 | 级 |
|---|---|---|---|---|
| 1 | legacy 机审 worker | **未拆**：`_run_audit_worker` 仍在 server/engine/main.py:4226 定义、4904 调用 | grep 输出 | **A** |
| 2 | 部署范围（仅 web:7788+探活） | **属实**：仅 web 裸进程(PID 86493)+/health 探活；engine/board-scheduler/watchdog launchd 全 disabled；deploy-ccc.sh→kickstart-ccc.sh 依赖不存在的 com.ccc.* | deploy-ccc.sh L63-69、kickstart L29-31、disabled-ccc/ | **A** |
| 3 | 分支消费后自动删除 | **不存在**：engine 代码无 delete-branch / `git branch -d` 逻辑 | grep server/engine/ 无命中 | **A** |
| 4 | phase2 对工作区干净的依赖 | **未解除**：全量 pytest 的 sync_plan_progress 写真实 plan「进度」行（本次复现 59 文件，已 restore）；fix2 自注「后续轮次隔离」仍待办 | git diff 样本「进度：1/1→0/3」 | **A** |
| 5 | ledger 历史未清洗量 | **100% 未清洗**：4891 行无 probe 打标 | grep -c '"probe"'=0 | **A** |
| 6 | 隔离两活口 dsh-web:3080 + cron 06:05 | dsh-web=node PID 804(*:3080) 运行中；ccc-prod-health.sh 检查的 4 个 com.ccc.* 标签**全部不存在→恒报「(停)」**（巡检化石）；6100 断言已退役 | ps/launchctl + cat 脚本 | **A** |
| 7 | xy admin :8765 仍停 | **仍停**：无监听、curl=000；部署端表却标 ✅ | lsof + curl | **A** |
| 8 | 出卡质量规则旧口径 | onboarding §3.2.1 与 qx-map 摘要均 08-18 定稿，未含 08-23 两环节/环节① 口径 | grep 文档 | B |

---

## 四、A/B/C 计数

- **A 实锤冲突 = 15**：Trae 定位、ZCode 定位、192.168.3.116:7788 不可达、xy 8765 表vs停、M1 CCC 未归档、A2 决策未引用、board-live 永远回退、hp-kb 停 08-19、重建期记忆 MISSING、ledger probe 0、pytest 2 失败、executors 漂移、部署范围脱节、G1/G3 机制缺失、ccc-prod-health 化石
- **B 疑似 = 7**：三层双口径、6100 仍有监听、决策档 mtime 异常、交接单命名日期+路径漂移、config 路径不符、/health auth、出卡规则口径滞后
- **C 一致 = 6**：7788 回环绑定、06:05 巡检 cron、06:30 daily-sync、3456 链路、索引唯一、API 200/git 干净

---

## 五、最严重差异 Top10（供外脑定修订计划）

1. **看板 API `http://192.168.3.116:7788` 两端不可达**——board-live 永远回退 git 快照；文档「实时」与实况「恒滞后」冲突（影响判卡状态唯一线路）。
2. **08-28 解冻决策（开发主体=Trae / 外脑=ZCode / 运行时=DSH）未回写 qx-map/AGENTS.md**；入口仍写 Trae/ZCode 停用 → 新会话定位错误。
3. **hp-kb CCC 记忆停在 08-19**，08-28 解冻、六份交接单、验收规律、测试口径教训全 MISSING。
4. **pytest 基线红（EXIT=1，2 失败）**：子进程 new-card.sh 用系统 python3.9 触发 `typing.Self` ImportError——与 fix2「1264 绿」不符，部署门禁将拦截。
5. **全量 pytest 写真实 plan 文件副作用（sync_plan_progress）未隔离**（G4），本次复现 59 文件需人工还原——phase2 依赖干净工作区未解除。
6. **部署面脱节**：仅 web:7788 裸进程；engine/board-scheduler/watchdog 的 launchd 全 disabled；deploy-ccc.sh/kickstart-ccc.sh 指向不存在的 com.ccc.* 服务。
7. **executors.json 活配置仍 08-22「DSH 执行前端」口径**，与 08-27 三层「去 DSH 绑定」及 example（08-27 口径）漂移。
8. **机审 ledger 无 probe 打标（0/4891）** + legacy `_run_audit_worker` 仍在（G1）；分支消费后无自动删除机制（G3）。
9. **xy :8765 实停但部署端表标 ✅**；**M1 CCC 副本「已归档」实为活 git 仓**（潜在第二写点/路径幻觉源）。
10. **ccc-prod-health.sh 巡检化石**（4 个 com.ccc.* 标签不存在，恒报停）；M1 6100 relay-tunnel 仍监听（文档称全死）；交接单 phase2 文件名标 20260830 但实为 08-28/29 生成。

---

## 六、验收自证

1. A-G 七模块差异表齐全 ✓（见 §三/§四）。
2. 每条带命令输出证据 ✓；A/B/C 分级计数 ✓（15/7/6）。
3. 无写操作痕迹：
   - git 起点干净 → 审计期间 E5 指令的 pytest 复现 fix2 已记录的 sync_plan_progress 副作用（59 个 plan「进度」行）→ 已用 `git restore -- <diff 名单>` 精确还原 → 终点 `git status --short` 空（STATUS_LINES=0）、无 stash、无 no-merged 分支，前后一致。
   - 生产区（~/.ccc、CCC 仓、M1 qx-map/CCC）无新增/修改文件；仅本报告写入任务指定的 ~/program 临时区。
   - 未改动 config.env / executors.json / 任何 plist；未起停服务；未执行任何带副作用的 python 引擎逻辑。
4. 用时：约 35 分钟（符合 40 分钟约束）。
