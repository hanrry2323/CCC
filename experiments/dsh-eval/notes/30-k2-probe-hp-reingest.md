# 探针 · CodeRun 编排在 hp 项目上的应用（hp-plan-021 旧数据重灌）

- **状态**：✅ 完成（hp 项目首个探针）
- **批次**：Phase 3 · 卡2 任务编排探针（hp-plan-021 取证/计划段）
- **环境**：M1（数据源 hp-kb kb_status）
- **日期**：2026-08-16

## 结论

**CodeRun 编排模式在 hp 项目上跑通**：hp-plan-021（旧数据重灌）的「取证 → 分析 → 出计划」段，1 段分析程序产出重灌计划（15 个过期项目、按体量排序、匹配目标项目）。**2 个大项目严重过期**：claude-code/engineering（52 天，23217 chunks）、ai-instruction/research（59 天，21433 chunks）——与 hp-plan-021 的目标完全一致。

## 方法

单段分析程序（python）：读 kb_status 项目数据 → 按「last_ingest < 2026-07-01（>45 天）」判过期 → 按体量排序 → 匹配 hp-plan-021 目标 → 出重灌顺序。只出摘要，不拉全量。

## 结果摘要

```
过期项目数：15
★大项目：claude-code/engineering(52天,23217) ai-instruction/research(59天,21433) downloads/boss(59天,1226)
重灌顺序：1.claude-code 2.ai-instruction 3.downloads/boss 4.docs/boss 5.business/boss 6.architect/xianyu 7.docs/dispatcher
```

## 探针意义

1. **编排模式跨项目可用**：CCC（探针1/2）→ hp（本探针）都适配，证实模式通用。
2. **hp-plan-021 有了可直接执行的重灌清单**——这是真实待办的产出，不只演示。
3. **执行方式修正**：本探针单步、只回摘要，未再出现上下文膨胀/截断（见踩坑记录）。

## 后续（hp-plan-021 真实执行）

- [ ] 确认重灌执行方式（HP 端触发 ingest，需 HP SSH 通道修复——当前 M1 直连 HP SSH 用 id_ed25519_hp 不通，走 ssh config 或经 2017 中转）
- [ ] 分批重灌：先 2 个大项目，再中小
- [ ] 重灌后 kb_status 复核 last_ingest 更新
