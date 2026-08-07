# 任务卡 hp003 · 备份对齐：pg 备份链路摸底与冷热备份机制规范化（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：已回写 · 派发：engine · 项目：hp · 日期：2026-08-07

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

**执行体**：OpenCode · 日期：2026-08-07

### 1. 现状分析（摸底结论）
- **定时冷备确实在正常运行**：每天凌晨 02:00 定时执行，日志输出到 `/data/backups/knowledge/pg_dump.log`。
- **落点与认知错位**：备份文件生成路径为 `/data/backups/knowledge/knowledge_$DATE.sql.gz`，而 `/data/knowledge/backups/` 目录下仅有历史手动备份 `2026-07-04-pre-4finance.dump`，并非定时任务落点。因此备份链并未断，而是文件存放位置不一致。
- **WAL 实时热备正常**：数据库中 `archive_mode` 为 `on` 且 `wal_level` 为 `replica`，WAL 日志被实时归档至 `/data/backups/wal/` 下。

### 2. 定时冷备机制修整与规范
- 修改了 `/data/backups/pg_dump_knowledge.sh` 脚本，在保留原 `.sql.gz` 兼容性的基础上，新增了 **PostgreSQL 自定义二进制格式 (`.dump`)** 的导出，支持并发恢复和 `pg_restore` 结构检查。
- 增加了针对 `.dump` 格式文件的 30 天自动轮转删除机制。
- 备份脚本修改后手动试跑成功，顺利在 `/data/backups/knowledge/` 路径下产出今日份 `.dump` 与 `.sql.gz` 文件，且无一例删除/覆盖旧备份及现有 WAL 文件的行为。

### 3. 恢复完整性验证
- **dump 完整性校验**：对新生成的 `/data/backups/knowledge/knowledge_2026-08-07.dump` 执行了 `pg_restore --list` 完整性检验。成功还原并列出了全套 TOC 结构（包含 vector 扩展、`chunks`/`documents`/`memory_store` 等表结构和 IVFFlat 向量索引定义），验证通过。
- **gzip 完整性校验**：对 `knowledge_2026-08-07.sql.gz` 运行了 `gzip -t` 校验，验证通过。

### 4. 机制文档归档说明
- 已在 `hp` 业务仓库中新建了备份与恢复的机制说明文档：`/Users/fan/program/apps/hp/docs/knowledgebase/BACKUP.md`，文档内详细列出了定时任务、落点、保留策略、异地副本 Pull 机制（Mac2017 的 `rsync` 增量拉取），以及低风险完整性校验、测试沙箱库恢复和生产库灾难恢复的具体步骤。

### 5. commit+push 证据
- 已经向分支 `codex/hp003-backup-alignment` 进行了 commit 与 push 操作。
- 最终 commit hash：265d650fbdca3b681816d23c1340950957a6aae0
