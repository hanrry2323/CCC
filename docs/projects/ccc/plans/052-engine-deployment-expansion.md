# 方案 · 部署范围扩展：引擎侧服务部署与守护分期方案

> 项目：ccc · 编号：ccc-plan-052 · 状态：待排期（待老板拍板，拍板前不动手） · 作者：ZCode（Mac2017 执行窗口 · 指令直改模式 任务九） · 工具：ZCode
> 创建：2026-08-29 · 更新：2026-08-29
> 关联卡：无（拍板前不动手）
> 关联方案：ccc-plan-051（巡检脚本服务段与本方案第 1 期联动）、ccc-plan-050（合入自动化研究——本方案是其运行时承载）
> 取证基线：本仓 main @ `448719464`（2026-08-29）；全程只读取证。

## 目标

把当前「仅 web:7788 裸进程 + 探活」的部署面扩展为「**web 常驻 + 引擎闭环常驻（派发+phase2 消费+内嵌巡检）+ 部署脚本对齐**」的最小可运维集，分三期实施，每期独立可验收、可回退。

## 背景（现状取证 · 2026-08-29）

| 项 | 实况 | 缺口 |
|---|---|---|
| web:7788 | 裸进程 PID 86493（`python -m server.web.server --host 127.0.0.1 --port 7788`，PPID 1，08-29 00:45 起） | 崩溃无自愈（无 launchd KeepAlive） |
| engine（前半段派发） | `com.ccc.engine` launchd **停用**（plist 在 disabled-ccc/）；run_loop 未运行 | 卡的自动派发/机审填槽无运行时 |
| phase2（后半段闭环） | 无守护进程；仅被 engine run_loop 内嵌调用或手动 `--once/--daemon` | CC 审核→合入→部署→终态的自动化无运行时 |
| board-scheduler | `com.ccc.board-scheduler` 停用；巡检任务已内嵌 run_loop（「内嵌 scheduler 线程」） | 单体服务冗余，可不再单独部署 |
| watchdog | `com.ccc.watchdog` 停用 | 自愈缺位 |
| deploy-ccc.sh | 原子流（fetch+ff → pytest 门禁 → kickstart）完好 | 第 3 步 kickstart 指向已停用的 com.ccc.* → 部署链断 |
| kickstart-ccc.sh | 幂等重启+防旋完好 | 同上，服务集与现实脱节 |
| 业务仓合入部署 | approve-merge.sh `close_business_repo` 已在合入时经 ssh 收口业务分支（含删除已合入分支） | 业务仓自身部署属各项目档案口径，CCC 侧无统一守护需求 |

**关键判断**：08-26 停用 launchd 是重建期主动行为（避免旧口径服务干扰重建），重建完成后**没有恢复任何常驻运行时**——当前 CCC 的自动化闭环实际处于「全手动」状态。这是部署范围必须扩展的根因。

## 方案内容（分期 · 唯一建议）

### 第 1 期：最小常驻闭环（建议先行，收益最大）

1. **恢复 `com.ccc.web-server` launchd**：plist 已在 disabled-ccc/，核对内容（WorkingDirectory、`--host 127.0.0.1 --port 7788`）后 `launchctl bootstrap` 装回；web 从裸进程转常驻（KeepAlive 自愈）。切换动作：停裸进程 → bootstrap → /health 探活。
2. **恢复 `com.ccc.engine` launchd**：run_loop（`python -m server.engine.main --loop`）承载**前半段派发 + phase2 消费 + 内嵌巡检**三合一，单服务即完整闭环。plist 核对后装回。
3. **board-scheduler / watchdog 维持停用**：巡检已内嵌 engine；watchdog 的自愈职责由 launchd KeepAlive 承接，暂不恢复单服务（第 3 期再评估）。
4. **修 kickstart-ccc.sh 服务集**：从三服务改为实际两服务（web-server、engine）；防旋/draining 机制保留。
5. **修 deploy-ccc.sh**：第 3 步 kickstart 不再指向不存在服务（随 4 自动修复）；pytest 门禁改用 `.venv-hub/bin/python`（现 `CCC_PYTHON_BIN:-python3` 落到 /usr/local/bin/python3 可用但不显式，统一钉死 venv）。
6. **巡检脚本对齐**：ccc-prod-health.sh 服务段改查两服务（联动 ccc-plan-051 卡B）。

### 第 2 期：业务仓合入部署对齐

1. 盘点 registry 各业务项目的部署方式（cla/qb/xy/mx…），在项目档案 README「在 CCC 怎么动」补「合入后部署动作」一段（人工/脚本/无需部署）。
2. 有部署动作的项目补 `scripts/deploy-<prefix>.sh`（或标注手动 SOP），approve-merge.sh 收口后按 registry 提示执行。
3. 验收：任选一业务项目做一次「合入→部署→探活」演练。

### 第 3 期：守护深化（按需）

1. watchdog 策略重估：launchd KeepAlive 覆盖崩溃自愈后，剩余需求=深度巡检（卡积压告警、phase2 队列年龄、失败率突增）→ 建议以 engine 内嵌巡检任务扩展，不复活单体 watchdog。
2. 部署通知：deploy 成功/失败写 ledger + 控制台告警（已有基础），可选接 DSH 值班通知。

## 验收标准

### 第 1 期
- [ ] `launchctl list | grep com.ccc` 恰有 web-server、engine 两行且 PID 存活
- [ ] `lsof -nP -iTCP:7788 -sTCP:LISTEN` 由 launchd 拉起的 Python 监听；kill 进程后 launchd 10 秒内自动拉起（KeepAlive 实测）
- [ ] 出一张测试卡走完整闭环：派发 → 回写 → 机审/CC 审核 → 合入 → push → 部署探活 → 已关闭，全程无人工
- [ ] `deploy-ccc.sh` 全链可跑通（含 kickstart 步骤对两服务生效）
- [ ] 次日巡检输出服务段与实况一致（联动 051 卡B）
- [ ] 回退预案：`launchctl bootout` + disabled-ccc/ 归位，恢复裸进程手工态

### 第 2 期
- [ ] registry 各 taskable 项目档案含「合入后部署动作」段
- [ ] 至少一个业务项目完成合入→部署→探活演练

## 功能卡（拍板后转卡用）

### 卡A：web-server launchd 恢复

目标：web:7788 常驻自愈。
实现：核对 disabled-ccc/com.ccc.web-server.plist → bootstrap → 探活 → 停裸进程。
验收：KeepAlive 实测拉起 + /health 200。
颗粒度：运行面单服务切换；依赖：无；架构位置：2017 launchd + scripts/kickstart-ccc.sh。

### 卡B：engine launchd 恢复（run_loop 三合一）

目标：派发+phase2 消费+内嵌巡检常驻。
实现：核对 com.ccc.engine.plist（确认启动参数为 --loop 模式）→ bootstrap → 测试卡全链演练。
验收：上述第 1 期第 3 条。
颗粒度：运行面单服务切换；依赖：卡A（探活依赖 web 常驻）；架构位置：2017 launchd + server/engine/main.py run_loop。

### 卡C：kickstart/deploy 脚本对齐

目标：部署链与两服务现实一致。
实现：kickstart-ccc.sh 服务集改两服务；deploy-ccc.sh PYTHON_BIN 钉 .venv-hub。
验收：deploy-ccc.sh 全链跑通。
颗粒度：两脚本小改；依赖：卡A/卡B 后；架构位置：scripts/。

### 卡D：业务仓部署对齐（第 2 期）

目标：业务项目合入后部署动作成文可执行。
实现：registry 项目档案补部署段；有需要者补 deploy-<prefix>.sh。
验收：一项目演练通过。
颗粒度：文档+可选脚本；依赖：无（独立）；架构位置：docs/projects/*/README.md + scripts/。

## 风险与回退

- plist 内容是 08-21 口径，bootstrap 前必须核对（启动参数/环境变量/日志路径是否匹配现 config）；不符则以现 config.env 为准修 plist 再装回。
- engine run_loop 恢复即恢复**自动派发**——需与老板确认值班节奏（是否 7×24 自动派发，或先以 phase2 --daemon 单独常驻、派发仍手动）。**此为拍板要点之一。**
- 回退：bootout 两服务 + disabled-ccc/ 归位，回到当前裸进程态，数据零迁移。
