# 任务卡 hp016 · 采集管道完整性恢复与 md_parser 解析修复（OpenCode 执行）

> 关联：ccc-plan: HP 采集管道完整性修复（ingest/md_parser 恢复 + 解析 bug + ccc-docs 补采） · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：hp · 日期：2026-08-08

## 目标

采集管道完整性恢复与 md_parser 解析修复（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `/Users/fan/program/apps/hp/local/scripts/kb-collect.py`
- `/Users/fan/program/apps/hp/local/scripts/com.hp-kb.collector.plist`
- `/data/knowledge/pipeline/ingest.py`
- `/data/knowledge/pipeline/md_parser.py`
- `/data/knowledge/pipeline/chunker.py`
- `/data/knowledge/pipeline/parsers/`
- `/data/knowledge/local/scripts/`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. {'摸底确认采集链路现状：/data/knowledge/pipeline/ 缺 ingest.py/md_parser.py/chunker.py 生产文件（仅 .bak-20260803-K23 与 .bak 残留），launchd com.hp-kb.collector（每晚 2': '00）→ 2017 kb-collect.py → ssh hp 执行 python3 ingest.py 的链路完整性'}
2. 恢复/重建 ingest.py、md_parser.py、chunker.py 生产文件（可从 .bak 恢复并按需修复，或重写）；恢复后 launchd 触发的采集能正常执行（手动跑一次 kb-collect.py 验证）
3. 修复 md_parser ValueError（too many values to unpack (expected 2)）：roadmap.md、orchestration-flow.md、pre-test-dual-host-sync.md、v0.66.x.md 等文档解析不再失败跳过
4. ccc-docs 补采：入库文档数从当前 ~742 提升至显著覆盖（磁盘 1535 文件大部分入库），新入库无 md_parser failed、K23 四列齐全、短 chunk 闸门生效（0 新增 <50 字符）
5. 采集后验证：kb-search stats 总数增加、mcp-server 检索能命中新入库文档；回写区含修复前后对照 + 采集日志证据
6. 改动提交到 codex/hp016-collector-pipeline-repair 分支（hp 仓 + /data/knowledge 部署相关），回写区含修复清单与回归证据

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
