# 任务卡 hp004 · 采集管道验证与数据源扩展（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：hp · 日期：2026-08-07

## 目标

验证 HP 采集管道（launchd `com.hp-kb.collector` → kb-collect.py → HP ingest.py）当前真实状态与覆盖范围，补齐数据源（目前仅 Mac2017 hp 仓 `docs/` 单源），并把采集状态纳入既有监控。

## 红线（先看）

1. **只动采集链路**：Mac2017 `local/scripts/kb-collect.py`（数据源扩展）、`com.hp-kb.collector.plist`、launchd 加载状态、hp@ 侧 `/data/knowledge/pipeline/ingest.py`（若需改解析/入库）。**禁止**动 DB 数据本身与检索逻辑（数据质量归 hp006 卡、检索归 hp006 卡，防并发冲突）。
2. 禁止删除/改写 PG 中已有数据（documents/chunks/memory_store）；新增采集只做增量。
3. 扩展新数据源前先确认源目录存在且可读；新增源写入卡回写区「源清单」。
4. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- Mac2017：`local/scripts/kb-collect.py`（源配置与扩展）、`local/scripts/com.hp-kb.collector.plist`（如需）、launchd 状态、`~/.kb-collect.log`（只读）
- hp@：`/data/knowledge/pipeline/ingest.py`（如需改）、`/data/knowledge/incoming/mac2017-docs`（只读）
- 监控：`local/scripts/cluster-health.sh` 已有 chunks 计数探针，确认覆盖采集状态（如缺则补一行采集时间探针）

## 步骤

1. 摸底（只读）：
   - `launchctl print gui/501/com.hp-kb.collector` 确认加载状态；`tail ~/.kb-collect.log` 确认最近 3 次执行结果（现状：每天 2:00 跑，近期全「no changes, skip」）
   - `python3 local/scripts/kb-search.py stats` 看当前文档分类分布（现状：RSS 30 篇 general + 少量 hp/docs）
   - 读 kb-collect.py 的 DOCS_ROOT/domain/project 配置，梳理当前数据源清单（现状：单源 Mac2017 hp `docs/`，23 文件已同步）
2. 扩展数据源（至少 1 个，可多个）：
   - 候选：Mac2017 其他可读知识源（如 `/Users/fan/program/CCC/docs/`、`/Users/fan/program/projects/` 下成熟仓的 docs、qx-observer 等）；选 1-2 个稳定、有知识的源接入（domain/project 命名清晰）
   - 接入方式沿用 kb-collect.py 既有增量机制（mtime+size tracking + ingest.py content_hash 去重）
3. 采集状态入监控：确认 cluster-health.sh 输出含「采集时间/上次同步」探针（无则补：读 tracking 文件 mtime 或 `~/.kb-collect.log` 最新行，异常时走既有 notify() 告警）。
4. 探针真跑：手动执行 `python3 local/scripts/kb-collect.py` 一次，确认新源文件入库（`kb-search.py stats` 或 PG 查询可见新增），旧源保持 skip 去重。
5. 回写区落「数据源清单」：源路径 / domain / project / 文件数 / 入库结果。
6. commit+push 到卡内分支 `codex/hp004-collector-source-expansion`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」。
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 摸底结论写进回写区「现状分析」：collector 是否健康、当前单源覆盖、日志证据。
2. 至少 1 个新数据源接入：手动跑 kb-collect.py 后新源文档入库（提供 `kb-search.py stats` 前后对照或 PG 计数证据），旧数据零删除。
3. cluster-health.sh 含采集状态探针（实测输出可见）。
4. hp@ 侧仅动 ingest.py（如需），DB 数据零改动证据（如 `SELECT count(*) FROM documents` 前后对照只增不减）。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
