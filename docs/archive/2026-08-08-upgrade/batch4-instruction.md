# 批次 4 执行指令 · CCC 系统化升级（C 调度韧性：指数退避 + 熔断 + kickstart/看门狗）

> 来源：qx-map/__archive__/decisions/ccc-系统化升级方案-2026-08-08.md（commit d4f463e）· 批次 4「C 韧性」
> 角色：OpenCode CCC 窗口（出指令 Agent）发出 · 你（Claude Code）是执行 Agent，**只执行本指令，不自行扩方向**
> 工作目录：/Users/apple/program/CCC（main 分支，批次 3 已闭环：84ab483e/e1daf37e/0d9265cd）

## 一、目标（一句话）

基础设施故障（infra）不再无限轰炸重试：**指数退避 + 连续失败熔断强制打回**（P4 灭）；交付**kickstart/看门狗/原子部署脚本**（P5 灭），SIGTERM 后自愈 <60s。

## 二、基线事实（先核对再动手）

- P4 现场（xy018×20、mx015×21）：`main.py` run 阶段 infra 失败走 `_hold_infra_failure(phase="run")`（:1481）——**不累计 infra_count、固定 60s 冷却后无限重试**，槽位被吃光
- 已有雏形（对齐用）：
  - `_hold_infra_failure`（:169-218）：infra → 不进业务重试预算、记 `infra_cooldown_until`（固定 `EXECUTOR_INFRA_COOLDOWN_SECONDS` 默认 60）、`infra_count` 可传入
  - **audit 阶段已有熔断**（:1544-1552）：`infra_count >= 2` → 回待分派人工跟进（阈值写死）
  - `_infra_cooldown_active`（:229-244）：派发过滤冷却中卡
  - 成功清零已存在（audit 成功 :1527 写 `infra_count=0`）
- `is_retryable_failure`（:128-149）：502/503/504 等关键词判 infra（批次 1 已验收，**不改**）
- Work 模型（server/engine/task.py:90）有 `retry_count`；`infra_count` 存 runtime sidecar（cards.jsonl）
- P5 现状：`scripts/` 无 kickstart/watchdog/deploy；2017 侧 engine plist 有 KeepAlive/ThrottleInterval=5，但**部署流程（unload→pull→load）中途崩溃即悬挂**

## 三、任务（严格按序执行）

### 任务 1：run 阶段 infra 连续失败熔断（P4 核心）

改造 run 失败处理（:1479-1482 的 infra 分支），对齐 audit 模式：

- run infra 失败时：读 sidecar `infra_count` → `+1` 写入（经 `_hold_infra_failure` 传 `infra_count=strikes+1`）
- 连续失败 ≥ `EXECUTOR_INFRA_MAX_STRIKES`（默认 5）→ **不再冷却续跑，强制打回**（REJECTED，problems 标注「基础设施连续失败 N 次强制打回（可人工恢复后再派）」）
- run 成功路径补清零：收单成功处写 `infra_count=0`（对齐 audit :1527）
- **注意**：熔断是单卡维度（每卡各自累计），不误伤其他卡

### 任务 2：指数退避（P4）

改造 `_hold_infra_failure` 的 `until` 计算：

- 冷却 = `base × 2^(strikes-1)`，封顶 `EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS`（默认 1800）
- base 沿用现 `EXECUTOR_INFRA_COOLDOWN_SECONDS`（默认 60），**保留字段名不变**（配置兼容）
- 参数化：`_hold_infra_failure` 收到的 `infra_count` 即连续失败次数（strikes），据此算退避
- 保持 `_infra_cooldown_active` 派发过滤逻辑不变（它只认 `infra_cooldown_until`）

### 任务 3：配置项（server/config/loader.py + config.env 同步）

新增（含默认值，loader.py 注册表对齐现有格式）：
- `EXECUTOR_INFRA_MAX_STRIKES`（默认 5）
- `EXECUTOR_INFRA_COOLDOWN_MAX_SECONDS`（默认 1800）
- `EXECUTOR_INFRA_COOLDOWN_SECONDS` 保留（base，默认 60，已有）

audit 阶段熔断阈值（:1544 写死 `>= 2`）改为读 `EXECUTOR_INFRA_MAX_STRIKES`（audit 也享受同一阈值，语义：连续 N 次 infra 后强制处置）。

### 任务 4：P5 交付脚本（仓库内，2017 部署用，**不 ssh 手改 2017**）

`scripts/kickstart-ccc.sh`：
- 幂等重启 engine 与 web-server：`launchctl kickstart -k gui/$(id -u)/com.ccc.engine`（web-server 同），失败回退 `killall` + `launchctl start`
- 退出码规范（0=成功拉起，非 0=失败详情到 stderr）

`scripts/watchdog-ccc.sh`：
- 检查：engine 进程存活 + `~/.ccc/logs/engine.stdout.log` 最近心跳（mtime < 120s 为健康）
- 不健康 → 调 kickstart-ccc.sh；记录动作到 `~/.ccc/logs/watchdog.log`
- 输出一行状态（健康/已拉起/失败），退出码对应
- 附注释：如何挂 cron/launchd（每 60s）

`scripts/deploy-ccc.sh`：
- 原子部署：`git pull --ff-only` → `pytest server/tests/ -q`（t53 存量失败容忍）→ kickstart-ccc.sh
- **关键（P5 灭）**：任何一步失败 → 打印明确错误 + 恢复指引，**不悬挂**（不用 unload/bootout 停掉再拉；用 kickstart 热重启）
- 全部脚本 `set -euo pipefail`，幂等，带用法注释

### 任务 5：单测

`server/tests/test_infra_resilience.py`（新建）：
1. run 阶段连续 infra：第 5 次 → REJECTED（熔断打回）；前 4 次 → 待分派+冷却
2. 指数退避：strikes=1 → 60s、2 → 120s、3 → 240s、4 → 480s；封顶 1800
3. run 成功 → infra_count 清零
4. audit 阈值读配置（非写死）
5. 熔断打回后 problems 含「连续失败」「强制打回」标记

用 mock `subprocess.run`/`read_card_state`/`write_card_state`（同批次 3 测试手法），不依赖真网络。

## 四、红线（违反即停）

1. **不改**：`is_retryable_failure` 关键词列表（批次 1 验收）；sidecar 覆盖规则/回收判定（批次 2/3 验收）；`_infra_cooldown_active` 派发过滤
2. **禁止 ssh 改 2017**（plist/launchd/部署仅交付仓库脚本）
3. 禁 `git add -A`；禁含密钥提交
4. 测试不过/歧义 → 停手记录

## 五、验证（写完必须跑）

1. `pytest server/tests/test_infra_resilience.py -v` 全绿
2. `pytest server/tests/` 全绿（t53 存量 3 失败除外）
3. 三个脚本 `bash -n` 语法检查通过
4. `git status` 干净

## 六、交付（执行完输出）

1. 改动文件清单 + diff 摘要（含行数）
2. 单测结果
3. 熔断/退避逻辑说明（阈值、退避序列、打回语义）
4. 脚本用法一句话说明（每个）
5. push commit hash
6. 未决项 / 遗留

## 七、验收条件（OpenCode 窗口复核用）

1. run 阶段连续 infra 熔断：默认第 5 次强制打回，前 4 次冷却续跑（单卡维度，不误伤）
2. 指数退避：60→120→240→480→封顶 1800，配置可调
3. run/audit 成功都清零 infra_count
4. audit 阈值读配置（非写死）
5. 三个脚本交付且语法通过、幂等、deploy 不悬挂
6. 单测全绿（t53 除外）；push 后 origin/main 含改动；工作区干净
7. 不碰已验收逻辑/2017 运行面/卡文件

> **2026-08-24 更新**：本文 EXECUTOR_INFRA_MAX_STRIKES 等旧熔断口径已被直修更新（强拆时距 1.5×EXECUTOR_TIMEOUT、台账+告警熔断），现行以 `docs/product/machine-audit-flow.md` 为准。
