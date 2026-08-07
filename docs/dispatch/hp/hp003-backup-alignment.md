# 任务卡 hp003 · 备份对齐：pg 备份链路摸底与冷热备份机制规范化（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

对齐 hp 数据备份机制（Phase 5）：摸底 hp@192.168.3.131 的 PG 备份链路现状（cron 任务、dump 落点、冷/热备、WAL），修复/规范化为可复现的「定时冷备 + 异地副本 + 恢复验证」机制，并把机制落成 hp 仓文档。

## 红线（先看）

1. **只动 hp@192.168.3.131 备份链路文件**（`/data/backups/`、`/data/knowledge/backups/`、备份相关 cron 与脚本）与 hp 仓备份文档；**禁止**改 Mac2017 hp 仓 `local/scripts/cluster-health.sh` 等监控脚本（监控归 hp002 卡，防并发冲突）。
2. 禁止删除/覆盖既有备份与 WAL（含 `2026-07-04-pre-4finance.dump`、`/data/wal/`）；新增产物一律放新路径或新命名。
3. 恢复验证先做低风险演练：`pg_restore --list` 检查 dump 完整性即可；真恢复只允许到临时库（如 `knowledge_restore_test`），验证后删除，禁止动生产库数据。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- hp@192.168.3.131：`/data/backups/`（cron 引用路径）、`/data/knowledge/backups/`、`/data/wal/`、备份 cron 与脚本（只读摸底 → 低风险修整）
- hp 仓文档：备份机制说明 ≤1 篇（`docs/` 或已有运维文档原地更新）
- 本卡在 CCC 仓回写区

## 步骤

1. 摸底（只读，先摸清再动）：
   - `ssh hp "crontab -l | grep -i -E 'backup|dump'"`（已知有 `0 2 * * * /data/backups/pg_dump_knowledge.sh >> /data/backups/knowledge/cron.log`）
   - `ls -la /data/backups/ /data/knowledge/backups/ /data/wal/`；读 `/data/backups/pg_dump_knowledge.sh`（或实际存在的 dump 脚本）
   - 查 cron.log 尾部确认最近一次执行是否成功
   - 记录：备份产出去向（为何 `/data/knowledge/backups/` 只有 2026-07-04 一份？cron 是否真的在跑/落点错位/脚本缺失）
2. 低风险修整（仅备份链路）：修复 dump 脚本/落点/日志，使定时冷备可复现（**保留既有备份不动**，新 dump 落规范化目录或新命名）。
3. 异地/冷备规范化：设计并落成「本地冷备（PG dump）+ 异地副本（可选 scp/rsync 到 Mac2017 或现有异地路径，若已有机制则对齐）」方案；新增内容写清路径与恢复步骤。
4. 恢复验证：对最新一份 dump 跑 `pg_restore --list`（或同等完整性检查），证明 dump 可读；输出检查结果。
5. 文档（hp 仓）：备份机制说明 ≤1 篇：定时任务、落点、保留策略、恢复步骤、异地副本同步方式。
6. commit+push 到卡内分支 `codex/hp003-backup-alignment`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 摸底结论写清：原备份链路为何断（cron 未跑/落点错位/脚本缺）——回写区必有「现状分析」段。
2. 修整后备份链路可复现：手动跑一次 dump 脚本成功，产物落在规范化路径（附实测命令与产物路径 + `pg_restore --list` 完整性通过）。
3. 既有备份与 WAL 零删除（回写区列 `ls -la` 前后对照）。
4. 备份机制文档落 hp 仓（定时/落点/保留/恢复/异地）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
