# HP 待验收方案证据分级审计

> 审计日期：2026-08-22 · 审计人：CCC 验收证据审计员（Claude Code）· 只读操作，未改动任何既有文件
> 审计对象：HP 项目（知识库服务仓）· 数据源：CCC 仓 + 2017 业务仓 /Users/fan/program/apps/hp + HP 节点运行时
> 可复现：所有结论均可用文末「复现命令」核对

## 一、首要结论（任务前提核对）

**HP 项目当前「待验收」方案数 = 0。** 任务前提（存在待验收方案）与实际不符。

全部 29 个方案状态分布：**已完成 24 · 作废 5 · 待验收 0**。

- 已完成：hp-plan-001、002、008、009、010、011、012、013、014、015、016、017、018、019、020、021、022、023、024、025、026、027、028、029
- 作废：hp-plan-003、004、005、006、007（里程碑级方案，2026-08-15 流程改造收回，未转卡）
- 按任务定义分档（严格口径）：**A=0 / B=0 / C=0，C 档清单 = 空**

因「待验收」档为空，本次审计补做**已完成方案的关闭证据分级**（同一套 A/B/C 口径），供老板拍板「已完成是否成立 / 是否需要退回待验收」。

## 二、已完成方案证据分级表

口径：A=卡全关+代码全在 main+有可复现验证；B=部分缺（代码在 main 但卡/交付缺证据，或代码部分不在 main）；C=代码不在 main 却标完成。

| 方案 | 标题 | 关联卡 | 卡状态 | 代码在main? | 交付报告 | 可复现证据 | 档位 | 缺什么 |
|------|------|--------|--------|------------|---------|-----------|------|--------|
| hp-plan-001 | 知识库底座固化(M1) | hp001-008,010-022 | 全关 | 主体在 main；hp018 回测脚本不在 SSOT main（仅 HP 节点运行 cron） | 有 hp-delivery-001 | pytest/探针/运行时UP | B | hp018 代码未合入 SSOT |
| hp-plan-002 | 合卡关闭(M1) | hp001-008,010-017,019-022 | 全关 | 同 001 | 有 hp-delivery-001 | pytest/探针/运行时UP | B | 主体代码在，卡写回缺 hp018 |
| hp-plan-008 | pipeline SSOT 回灌 | hp023 | 关 | 在 main (50c16f9) | 无 | pytest | B | 无交付报告 |
| hp-plan-009 | 双仓合并 | hp032 | 关 | 在 main (c72415c)；coderun_merge.py 未入 main | 无 | pytest | B | 卡为模板空白；无交付报告 |
| hp-plan-010 | 运行时 SSOT 对齐 | hp033 | 关 | 在 main 对应提交 | 无 | pytest | B | 卡为模板空白；无交付报告 |
| hp-plan-011 | 全文检索接入 | hp034 | 关 | 在 main (4e66ede) | 无 | pytest | B | 无交付报告 |
| hp-plan-012 | 双 DB 主备 | hp035 | 关 | 在 main (bfdae9b) | 无 | pytest | B | 卡为模板空白；无交付报告 |
| hp-plan-013 | 凭据治理 | hp036 | 关 | 在 main (f696e18) | 无 | pytest | B | 无交付报告 |
| hp-plan-014 | 可重建验证 | hp037 | 关 | 在 main (597ba2d) | 无 | pytest / dr_drill_test.sh | B | 无交付报告 |
| hp-plan-015 | 健康三态探针 | hp030,hp038 | 关 | 在 main (3ab6675)；test_probes.py 未入 main | 无 | hp-probes.py | B | hp038 卡空白；测试文件未入 main |
| hp-plan-016 | PG 健康前端 | hp039 | 关 | 在 main (af39ab2) | 无 | pytest | B | 无交付报告 |
| hp-plan-017 | 告警通道 | hp040 | 关 | 在 main (abf36a8) | 无 | pytest | B | 卡为模板空白 |
| hp-plan-018 | 孤儿 cron 清理 | hp041 | 关 | 在 main (074acbc) | 无 | pytest | B | 无交付报告 |
| hp-plan-019 | 健康报告自动化 | hp042 | 关 | 在 main (af39ab2) | 无 | hp-health-report.py | B | 无交付报告 |
| hp-plan-020 | 采集器加固 | hp043 | 关 | 在 main (3fd6bf5,071cc07) | 无 | pytest | B | 无交付报告 |
| hp-plan-021 | 过期数据重采 | hp044 | 关 | 在 main (66a7169，dsh/hp044 分支已合入) | 无 | pytest | B | 无交付报告 |
| hp-plan-022 | 短 chunk 治理 | hp045 | 关 | 在 main (d03a35c，codex/hp045 已合入) | 无 | pytest | B | 卡为模板空白 |
| hp-plan-023 | 相关性优化 | hp046 | 关 | 在 main (3bee4e3) | 无 | knowledge_search | B | 卡为模板空白 |
| hp-plan-024 | 采集监控 | hp047 | 关 | 在 main (2f7ad54) | 无 | pytest | B | 卡为模板空白 |
| hp-plan-025 | mx 接入(M5) | hp048 | 关 | 在 main (0727b7f mx-collect) + medio-0 域 56 docs | 无 | KB 域数据 | B | 卡为模板空白 |
| hp-plan-026 | qb 深化(M5) | hp049 | 关 | 无对应代码入 main | 无 | qb 域 103 docs（2026-08-08 早于卡） | **C** | 卡为模板空白无写回；无代码 |
| hp-plan-027 | xy 接入(M5) | hp050 | 关 | 无对应代码入 main | 无 | xianyu architect 23 docs(2026-08-17) | **C** | 卡为模板空白无写回；无代码 |
| hp-plan-028 | 流程集成(M5) | hp051 | 关 | 无对应代码入 main | 无 | KB 无 flow 域 | **C** | 卡为模板空白无写回；无代码无数据 |
| hp-plan-029 | 质量回检(M5) | hp052 | 关 | 无（test_feedback.py 未入 main） | 无 | 无反馈数据 | **C** | 卡为模板空白无写回；无代码 |

**分档汇总（已完成方案补档口径）**：A=0 · B=20（001,002,008-025）· C=4（026,027,028,029）

## 三、红旗与风险清单

1. **M2-M5 卡批量模板假关闭（系统性问题）**：hp032-hp052 多数卡文件为 148 行模板占位（实现/范围/验收标准/门禁 全空白），2026-08-17 同日标「已关闭」，无写回区、无 commit hash、无机审/验收结论、维护区空。典型：hp049/050/051/052。
2. **M2-M5 方案跳过「待验收」门禁**：033 状态机要求 部分执行→待验收→已完成；hp-plan-008~029 于 2026-08-16/17 直接置「已完成」，未经过待验收拍板环节。
3. **交付报告缺失**：仅 hp-delivery-001.md（覆盖 hp-plan-001/002）。22 个 M2-M5 方案（008-029）无交付报告。
4. **代码不在 SSOT main 却在运行（hp018）**：HP 节点 cron 已运行 backtest_cron_sync.sh + backtest_backup.sh（`# hp018-backtest` 标记），但这两个脚本 + backtest_db.py 只在未合入的 codex/hp018 分支，SSOT main 无此代码——运行时依赖未入仓，重建即丢。
5. **分支未合入（13 个 codex 分支非 main 祖先）**：hp004/005/007/009/011/012/018/020/021/032/038/050/052 分支 tip 均非 main 祖先（多为 squash 合入导致，非全部假关闭）；但 hp018/050/052 的内容确认未进 main。
6. **测试文件未随代码入 main**：test_probes.py（hp038）、test_feedback.py（hp052）、coderun_merge.py（hp032）。
7. **维护区（Doc-Gate）未完成**：hp018/049/050/051/052 维护区为占位或空。

## 四、可复现验证证据（2017 实测）

- pytest 可用（9.1.1）：tests/server/test_version.py 收集 6 用例通过；pipeline/tests + tests/server 全套件存在。
- 健康探针：scripts/qa/hp-probes.py 可运行输出三态报告（2017 为 SSOT，服务未启属预期）。
- 运行时（HP 节点 hp@hp /data/knowledge）：8083 mcp-server / 8082 memory-store / 8000 graph / 5432 postgres 全部 LISTEN，mcp-server 可访问。
- 知识库域数据：hp-kb kb_status 显示 mx(medio-0 56 docs)、qb(103 docs)、xianyu(architect 23+memory 14 docs) 已入库；无 flow 域；xianyu 主域 0 docs。
- Git：tag v0.1.2 已存在；main 138 commits。

## 五、复现命令

```bash
# 待验收方案数（0）
cd /Users/fan/program/CCC/docs/projects/hp/plans/ && grep -l '状态：待验收' *.md
# 状态分布
grep -H -oE '状态：[^ ·]+' /Users/fan/program/CCC/docs/projects/hp/plans/*.md
# 卡状态
grep -H -m1 -oE '状态：[^ ·]+' /Users/fan/program/CCC/docs/dispatch/hp/*.md
# 分支合入检查（2017 业务仓）
cd /Users/fan/program/apps/hp && for b in $(git branch -r | grep -E 'origin/codex|origin/dsh'); do git merge-base --is-ancestor $b origin/main && echo MERGED $b || echo NOTMERGED $b; done
# 代码在 main 证据
git log origin/main --oneline | grep -iE 'hp046|full-text|probes|credential|dr-drill'
# 运行时（HP 节点）
ssh hp@hp 'lsof -nP -iTCP -sTCP:LISTEN | grep -E "8083|8082|8000|5432"; crontab -l | grep hp018'
```

## 六、给老板的建议口径

- 待拍板方案按本口径应**先退回「待验收」**再逐张验收：至少 hp-plan-026/027/028/029（C 档）不可直接放行。
- B 档 20 个：代码主体在 main + 运行时可用，但**卡写回/交付报告缺失**，需补卡证据或补交付报告后拍板。
- hp018 的 SSOT 缺口（脚本未入仓）属 P1 修复项，不补则「重建不可恢复」承诺不成立。
