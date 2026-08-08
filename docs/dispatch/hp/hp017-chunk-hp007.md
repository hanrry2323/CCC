# 任务卡 hp017 · 存量短 chunk 清理落库（hp007 遗留）（OpenCode 执行）

> 关联：hp007 遗留：存量 445 短 chunk 处理方案落库 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-09

## 目标

将 hp007 遗留的存量短 chunk（445 个，其中 437 个来自 knowledge/incoming）清理方案落库执行：合并或尾端对齐 <50 字符 chunk，降低短 chunk 占比（目标 <15%）。

## 红线（先看）

1. **只动存量短 chunk**：仅处理已识别的存量 <50 字符 chunk；不新建/删除其他知识文档数据。
2. **先备份后清理**：落库前必须对目标表/文件做备份或可回滚确认；清理失败可恢复。
3. **M1 禁改业务仓**：hp 仓与 /data/knowledge 的改动只在 Mac2017 / hp 节点执行，本仓只出卡不回写业务码。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/Users/fan/program/apps/hp`（业务仓，registry SSOT）
- `/data/knowledge/pipeline/`（hp 节点部署目录）及其 `clean_short_chunks.py`
- 数据库：knowledge DB（postgres，见 2017-hp-db-env 固化的隧道/凭据）

业务仓路径：`/Users/fan/program/apps/hp`（Mac2017）；部署节点 hp@hp `/data/knowledge`。

## 步骤

1. 先读 `docs/notes/2026-08-08-hp-env/2017-hp-db-env.md` 环境固化说明：建隧道 `/Users/fan/.ccc/bin/start-hp-db-tunnel.sh`，`source /Users/fan/program/apps/hp/.env`（KB_DB_* 指向 127.0.0.1:5433）。
2. 确认存量短 chunk 现状：统计 documents/chunks 表中 <50 字符 chunk 数量与来源（应≈445，其中 437 来自 knowledge/incoming）。
3. 运行/复用 `clean_short_chunks.py`（hp007 已提供并入仓）执行存量清理：合并或尾端对齐短 chunk，动作前先备份。
4. 落库后重新核算短 chunk 占比（目标 <15%），对比清理前后数字。
5. 验证检索正常：`kb-search.py` 抽查若干查询仍能命中，无索引/检索回退。
6. 回写区记录：清理前后短 chunk 数量、来源分布、方案（合并/对齐）、备份位置、验证输出。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 存量 <50 字符 chunk 从 ~445 清理后显著下降，短 chunk 占比 <15%（回写区含清理前后数字与方案）
2. 清理动作前有备份/可回滚证据（文件或 SQL 备份路径）
3. 落库后 `kb-search.py` 抽查查询仍正常命中；短 chunk 闸门不受影响
4. 探针：清理后数据统计命令可复现输出；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
