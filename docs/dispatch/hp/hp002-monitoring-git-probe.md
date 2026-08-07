# 任务卡 hp002 · 监控盲区：cluster-health 增强 hp git 状态探针与统一探活（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

补 hp 监控盲区（Phase 4）：增强 Mac2017 `/Users/fan/program/apps/hp/local/scripts/cluster-health.sh`，加入 hp 仓 git 状态探针（dirty / ahead / 远程落后检测），并梳理统一探活覆盖（本地端口 + HP 远程 + git 状态），可手动运行或接入定时。

## 红线（先看）

1. **只动 Mac2017 hp 仓** `local/scripts/cluster-health.sh`（untracked 部署脚本）与 hp 仓文档（`docs/` 内监控相关 ≤1 篇）；**禁止**改 hp@192.168.3.131 节点上任何文件（备份链路归 hp003 卡，防并发冲突）。
2. 只读 ssh hp 做探活（`ss`/`curl`/`ps` 类）；禁止在 hp@ 上启停服务、装包、改配置。
3. qx-map（M1 `/Users/apple/qx-map`）非 CCC 出卡面且执行体不可达：探活结论只落 hp 仓，qx-map 侧同步留后续人工项，不在本卡。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- Mac2017 `/Users/fan/program/apps/hp/local/scripts/cluster-health.sh`（增强）
- hp 仓 `docs/` 监控说明（≤1 篇，若已有监控文档则原地更新）
- 本卡在 CCC 仓回写区

## 步骤

1. 读现状：`cd /Users/fan/program/apps/hp && cat local/scripts/cluster-health.sh`（已有本地端口 + HP 远程 CPU/MEM/chunks/ollama/端口检查），记录已有探针清单。
2. 在 cluster-health.sh 增加 **hp 仓 git 状态探针**：
   - `git -C /Users/fan/program/apps/hp status --porcelain`（dirty 检测）
   - `git -C /Users/fan/program/apps/hp fetch origin`（若允许远端访问）或 `git rev-list --count @{u}..HEAD`（ahead 检测），远端不可达时降级为本地 ahead 检测并提示。
   - 异常时沿用现有 `notify()` osascript 告警。
3. 探针自检：`bash local/scripts/cluster-health.sh` 正常退出（0=全绿 / 1=有异常），git 段输出真实状态；用「临时制造 dirty（touch 后还原）」验证 git 探针能检出（自测后必须还原工作区）。
4. 统一探活梳理：确认覆盖 = 本地端口（6100/6102/7788/8091）+ HP 远程（CPU/MEM/chunks/ollama/端口）+ hp git 状态，缺项补齐；梳理结论写进监控文档。
5. 文档（hp 仓）：监控说明更新 ≤1 篇，写清探针清单、运行方式（手动/定时）、告警行为。
6. commit+push 到卡内分支 `codex/hp002-monitoring-git-probe`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `bash local/scripts/cluster-health.sh` 实测输出含 **hp git 状态段**（如 `hp git: clean / ahead N / dirty`），退出码 0 或 1 符合文档说明。
2. 人为 dirty 自测能检出并还原（回写区记录自测过程与还原证据 `git -C /Users/fan/program/apps/hp status --porcelain` 为空）。
3. 监控文档写明探针清单 + 运行方式；hp@ 节点文件零改动（`ls -la /data/backups` mtime 不变即可，不在本卡触碰面）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
