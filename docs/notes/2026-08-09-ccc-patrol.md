# CCC 巡查与一致性交叉验证风险报告 (2026-08-09)

> 自动生成时间：2026-08-09 23:16:28
> 风险概览：🔴 红旗 15 处 · 🟡 黄旗 386 处 · 🔵 蓝旗 0 处

---

## 巡查发现清单

| 严重程度 | 对象 (acting_on) | 发现分类 | 交叉确认 | 证据 (位置) | 详细描述 |
| :---: | :--- | :--- | :---: | :--- | :--- |
| 🔴 红旗 | `clw005` | 治理一致性 | ✅ 交叉确认 | `docs/dispatch/clw/clw005-settings-panel.md:1` | 【交叉确认】卡 clw005 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🔴 红旗 | `clw005` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 【交叉确认】开发卡 clw005 已关闭，但其关联方案 clw-plan-001 的状态仍为 '部分执行' (未完成)。 |
| 🔴 红旗 | `clw004` | 治理一致性 | ✅ 交叉确认 | `docs/dispatch/clw/clw004-ccc-webview.md:1` | 【交叉确认】卡 clw004 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🔴 红旗 | `clw004` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 【交叉确认】开发卡 clw004 已关闭，但其关联方案 clw-plan-001 的状态仍为 '部分执行' (未完成)。 |
| 🔴 红旗 | `clw003` | 治理一致性 | ✅ 交叉确认 | `docs/dispatch/clw/clw003-sidebar-git.md:1` | 【交叉确认】卡 clw003 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🔴 红旗 | `clw003` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 【交叉确认】开发卡 clw003 已关闭，但其关联方案 clw-plan-001 的状态仍为 '部分执行' (未完成)。 |
| 🔴 红旗 | `clw002` | 治理一致性 | ✅ 交叉确认 | `docs/dispatch/clw/clw002-task.md:1` | 【交叉确认】卡 clw002 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🔴 红旗 | `clw002` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 【交叉确认】开发卡 clw002 已关闭，但其关联方案 clw-plan-001 的状态仍为 '部分执行' (未完成)。 |
| 🔴 红旗 | `clw-plan-001` | 治理一致性 | ✅ 交叉确认 | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 【交叉确认】方案 clw-plan-001 关联卡已全部关闭，但方案状态仍为 '部分执行' (未推进至 '已完成')。 |
| 🔴 红旗 | `clw-plan-001` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 【交叉确认】从已关闭卡反推，方案 clw-plan-001 应该已完成，但实际状态仍处于 '部分执行'。 |
| 🔴 红旗 | `ccc021` | 治理一致性 | ✅ 交叉确认 | `docs/dispatch/ccc/ccc021-s8.md:3` | 【交叉确认】卡 ccc021 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🔴 红旗 | `ccc021` | 治理一致性 | ✅ 交叉确认 | `docs/dispatch/ccc/ccc021-s8.md:1` | 【交叉确认】卡 ccc021 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🔴 红旗 | `ccc021` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/ccc/plans/010-s8.md:1` | 【交叉确认】开发卡 ccc021 已关闭，但其关联方案 ccc-plan-010 的状态仍为 '部分执行' (未完成)。 |
| 🔴 红旗 | `ccc-plan-010` | 治理一致性 | ✅ 交叉确认 | `docs/projects/ccc/plans/010-s8.md:1` | 【交叉确认】方案 ccc-plan-010 关联卡已全部关闭，但方案状态仍为 '部分执行' (未推进至 '已完成')。 |
| 🔴 红旗 | `ccc-plan-010` | 逆向巡查 | ✅ 交叉确认 | `docs/projects/ccc/plans/010-s8.md:1` | 【交叉确认】从已关闭卡反推，方案 ccc-plan-010 应该已完成，但实际状态仍处于 '部分执行'。 |
| 🟡 黄旗 | `xy031` | 治理一致性 | — | `docs/dispatch/xy/xy031-config-path-resolution-fix.md:3` | 卡 xy031 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy031` | 治理一致性 | — | `docs/dispatch/xy/xy031-config-path-resolution-fix.md:1` | 卡 xy031 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy030` | 治理一致性 | — | `docs/dispatch/xy/xy030-video-encoding-progress-log.md:3` | 卡 xy030 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy030` | 治理一致性 | — | `docs/dispatch/xy/xy030-video-encoding-progress-log.md:1` | 卡 xy030 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy029` | 治理一致性 | — | `docs/dispatch/xy/xy029-task.md:3` | 卡 xy029 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy029` | 治理一致性 | — | `docs/dispatch/xy/xy029-task.md:1` | 卡 xy029 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy028` | 治理一致性 | — | `docs/dispatch/xy/xy028-pytest-3.md:3` | 卡 xy028 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy028` | 治理一致性 | — | `docs/dispatch/xy/xy028-pytest-3.md:1` | 卡 xy028 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy027` | 治理一致性 | — | `docs/dispatch/xy/xy027-xianyu-hyperframes.md:3` | 卡 xy027 的关联字段 'INT-122' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy027` | 治理一致性 | — | `docs/dispatch/xy/xy027-xianyu-hyperframes.md:1` | 卡 xy027 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy026` | 治理一致性 | — | `docs/dispatch/xy/xy026-p0-flow.md:3` | 卡 xy026 的关联字段 'xy PRM P0-FLOW 前置（xy024 意图重建）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy026` | 治理一致性 | — | `docs/dispatch/xy/xy026-p0-flow.md:1` | 卡 xy026 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy025` | 治理一致性 | — | `docs/dispatch/xy/xy025-media-quality-acceptance.md:3` | 卡 xy025 的关联字段 'ccc-plan: xy PRM 批3：成片质量验收联测 + 关卡自动验证脚本' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy025` | 治理一致性 | — | `docs/dispatch/xy/xy025-media-quality-acceptance.md:1` | 卡 xy025 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy023` | 治理一致性 | — | `docs/dispatch/xy/xy023-env-credential-alignment.md:3` | 卡 xy023 的关联字段 'ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy023` | 治理一致性 | — | `docs/dispatch/xy/xy023-env-credential-alignment.md:1` | 卡 xy023 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy022` | 治理一致性 | — | `docs/dispatch/xy/xy022-dynamic-path-derivation.md:3` | 卡 xy022 的关联字段 'ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy022` | 治理一致性 | — | `docs/dispatch/xy/xy022-dynamic-path-derivation.md:1` | 卡 xy022 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy021` | 治理一致性 | — | `docs/dispatch/xy/xy021-purge-hardcode-old-rules.md:3` | 卡 xy021 的关联字段 'ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy021` | 治理一致性 | — | `docs/dispatch/xy/xy021-purge-hardcode-old-rules.md:1` | 卡 xy021 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy020` | 治理一致性 | — | `docs/dispatch/xy/xy020-round2-legacy-inventory.md:3` | 卡 xy020 的关联字段 'ccc-plan: xy 第二轮历史遗留排查（根基立稳）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy020` | 治理一致性 | — | `docs/dispatch/xy/xy020-round2-legacy-inventory.md:1` | 卡 xy020 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy019` | 治理一致性 | — | `docs/dispatch/xy/xy019-prod-gap-fix.md:3` | 卡 xy019 的关联字段 'ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy019` | 治理一致性 | — | `docs/dispatch/xy/xy019-prod-gap-fix.md:1` | 卡 xy019 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy018` | 治理一致性 | — | `docs/dispatch/xy/xy018-config-drift-fix.md:3` | 卡 xy018 的关联字段 'ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy018` | 治理一致性 | — | `docs/dispatch/xy/xy018-config-drift-fix.md:1` | 卡 xy018 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy017` | 治理一致性 | — | `docs/dispatch/xy/xy017-storage-layout-normalize.md:3` | 卡 xy017 的关联字段 'ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy017` | 治理一致性 | — | `docs/dispatch/xy/xy017-storage-layout-normalize.md:1` | 卡 xy017 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy016` | 治理一致性 | — | `docs/dispatch/xy/xy016-video-pipeline-recon-html-report.md:3` | 卡 xy016 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy016` | 治理一致性 | — | `docs/dispatch/xy/xy016-video-pipeline-recon-html-report.md:1` | 卡 xy016 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy015` | 治理一致性 | — | `docs/dispatch/xy/xy015-eng-profile-renewal-2026-08.md:3` | 卡 xy015 的关联字段 'ccc-plan: xianyu 工程化底座补齐' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy015` | 治理一致性 | — | `docs/dispatch/xy/xy015-eng-profile-renewal-2026-08.md:1` | 卡 xy015 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy014` | 治理一致性 | — | `docs/dispatch/xy/xy014-eng-baseline-video-pipeline-alignment.md:3` | 卡 xy014 的关联字段 'ccc-plan: xianyu 工程化底座补齐' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy014` | 治理一致性 | — | `docs/dispatch/xy/xy014-eng-baseline-video-pipeline-alignment.md:1` | 卡 xy014 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy013` | 治理一致性 | — | `docs/dispatch/xy/xy013-render-hyperframes-glass-template.md:3` | 卡 xy013 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy013` | 治理一致性 | — | `docs/dispatch/xy/xy013-render-hyperframes-glass-template.md:1` | 卡 xy013 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy012` | 治理一致性 | — | `docs/dispatch/xy/xy012-tts-multi-voice-emotion-selector.md:3` | 卡 xy012 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy012` | 治理一致性 | — | `docs/dispatch/xy/xy012-tts-multi-voice-emotion-selector.md:1` | 卡 xy012 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy011` | 治理一致性 | — | `docs/dispatch/xy/xy011-subtitle-karaoke-style-ass-rendering.md:3` | 卡 xy011 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy011` | 治理一致性 | — | `docs/dispatch/xy/xy011-subtitle-karaoke-style-ass-rendering.md:1` | 卡 xy011 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy010` | 治理一致性 | — | `docs/dispatch/xy/xy010-video-high-bitrate-crf-encoding.md:3` | 卡 xy010 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy010` | 治理一致性 | — | `docs/dispatch/xy/xy010-video-high-bitrate-crf-encoding.md:1` | 卡 xy010 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy009` | 治理一致性 | — | `docs/dispatch/xy/xy009-video-pexels-clip-downloader.md:3` | 卡 xy009 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy009` | 治理一致性 | — | `docs/dispatch/xy/xy009-video-pexels-clip-downloader.md:1` | 卡 xy009 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy008` | 治理一致性 | — | `docs/dispatch/xy/xy008-auto-build-openclaw-plugin.md:3` | 卡 xy008 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy008` | 治理一致性 | — | `docs/dispatch/xy/xy008-auto-build-openclaw-plugin.md:1` | 卡 xy008 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy007` | 治理一致性 | — | `docs/dispatch/xy/xy007-bilibili-toutiao-cookie-collector.md:3` | 卡 xy007 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy007` | 治理一致性 | — | `docs/dispatch/xy/xy007-bilibili-toutiao-cookie-collector.md:1` | 卡 xy007 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy006` | 治理一致性 | — | `docs/dispatch/xy/xy006-platform-kuaishou-channels-bridge.md:3` | 卡 xy006 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy006` | 治理一致性 | — | `docs/dispatch/xy/xy006-platform-kuaishou-channels-bridge.md:1` | 卡 xy006 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy005` | 治理一致性 | — | `docs/dispatch/xy/xy005-fix-audio-bgm-and-level-norm.md:3` | 卡 xy005 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy005` | 治理一致性 | — | `docs/dispatch/xy/xy005-fix-audio-bgm-and-level-norm.md:1` | 卡 xy005 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy004` | 治理一致性 | — | `docs/dispatch/xy/xy004-fix-audio-voice-ducking.md:3` | 卡 xy004 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy004` | 治理一致性 | — | `docs/dispatch/xy/xy004-fix-audio-voice-ducking.md:1` | 卡 xy004 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy003` | 治理一致性 | — | `docs/dispatch/xy/xy003-wire-2pass-encoding.md:3` | 卡 xy003 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy003` | 治理一致性 | — | `docs/dispatch/xy/xy003-wire-2pass-encoding.md:1` | 卡 xy003 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy002` | 治理一致性 | — | `docs/dispatch/xy/xy002-bug-scan-and-fix.md:3` | 卡 xy002 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy002` | 治理一致性 | — | `docs/dispatch/xy/xy002-bug-scan-and-fix.md:1` | 卡 xy002 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `xy001` | 治理一致性 | — | `docs/dispatch/xy/xy001-write-video-script-command.md:3` | 卡 xy001 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `xy001` | 治理一致性 | — | `docs/dispatch/xy/xy001-write-video-script-command.md:1` | 卡 xy001 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `qb005` | 治理一致性 | — | `docs/dispatch/qb/qb005-script-argument-parsing-fix.md:3` | 卡 qb005 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `qb005` | 治理一致性 | — | `docs/dispatch/qb/qb005-script-argument-parsing-fix.md:1` | 卡 qb005 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `qb004` | 治理一致性 | — | `docs/dispatch/qb/qb004-api-response-time-logging.md:3` | 卡 qb004 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `qb004` | 治理一致性 | — | `docs/dispatch/qb/qb004-api-response-time-logging.md:1` | 卡 qb004 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `qb003` | 治理一致性 | — | `docs/dispatch/qb/qb003-lint.md:3` | 卡 qb003 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `qb003` | 治理一致性 | — | `docs/dispatch/qb/qb003-lint.md:1` | 卡 qb003 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `qb002` | 治理一致性 | — | `docs/dispatch/qb/qb002-task.md:3` | 卡 qb002 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `qb002` | 治理一致性 | — | `docs/dispatch/qb/qb002-task.md:1` | 卡 qb002 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `qb001` | 治理一致性 | — | `docs/dispatch/qb/qb001-qb-ssot.md:3` | 卡 qb001 的关联字段 'INT-121' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `qb001` | 治理一致性 | — | `docs/dispatch/qb/qb001-qb-ssot.md:1` | 卡 qb001 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `qb` | 治理一致性 | — | `docs/roadmap.md:1` | 项目 qb 缺失对应的 业务线路（qb）段落。 |
| 🟡 黄旗 | `mx029` | 治理一致性 | — | `docs/dispatch/mx/mx029-media-library-sort-persistence.md:3` | 卡 mx029 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx029` | 治理一致性 | — | `docs/dispatch/mx/mx029-media-library-sort-persistence.md:1` | 卡 mx029 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx028` | 治理一致性 | — | `docs/dispatch/mx/mx028-rss-feed-validation-before-add.md:3` | 卡 mx028 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx028` | 治理一致性 | — | `docs/dispatch/mx/mx028-rss-feed-validation-before-add.md:1` | 卡 mx028 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx027` | 治理一致性 | — | `docs/dispatch/mx/mx027-core-60.md:3` | 卡 mx027 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx027` | 治理一致性 | — | `docs/dispatch/mx/mx027-core-60.md:1` | 卡 mx027 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx026` | 治理一致性 | — | `docs/dispatch/mx/mx026-rssservice-websub-p0.md:3` | 卡 mx026 的关联字段 'mx025 架构问题清单 #1 P0' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx026` | 治理一致性 | — | `docs/dispatch/mx/mx026-rssservice-websub-p0.md:1` | 卡 mx026 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx025` | 治理一致性 | — | `docs/dispatch/mx/mx025-core-module-coupling-audit.md:3` | 卡 mx025 的关联字段 'ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx025` | 治理一致性 | — | `docs/dispatch/mx/mx025-core-module-coupling-audit.md:1` | 卡 mx025 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx024` | 治理一致性 | — | `docs/dispatch/mx/mx024-quick-xml-security-upgrade.md:3` | 卡 mx024 的关联字段 'ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx024` | 治理一致性 | — | `docs/dispatch/mx/mx024-quick-xml-security-upgrade.md:1` | 卡 mx024 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx023` | 治理一致性 | — | `docs/dispatch/mx/mx023-frontend-coverage-ci-gate.md:3` | 卡 mx023 的关联字段 'ccc-plan: medio-0 打磨第四批：质量门禁与安全债、架构暴露' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx023` | 治理一致性 | — | `docs/dispatch/mx/mx023-frontend-coverage-ci-gate.md:1` | 卡 mx023 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx022` | 治理一致性 | — | `docs/dispatch/mx/mx022-opml-import-attribute-order.md:3` | 卡 mx022 的关联字段 'ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx022` | 治理一致性 | — | `docs/dispatch/mx/mx022-opml-import-attribute-order.md:1` | 卡 mx022 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx021` | 治理一致性 | — | `docs/dispatch/mx/mx021-scheduled-health-probe.md:3` | 卡 mx021 的关联字段 'ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx021` | 治理一致性 | — | `docs/dispatch/mx/mx021-scheduled-health-probe.md:1` | 卡 mx021 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx020` | 治理一致性 | — | `docs/dispatch/mx/mx020-rss-save-transaction.md:3` | 卡 mx020 的关联字段 'ccc-plan: medio-0 打磨第三批：RSS 事务化 / 定时巡检 / OPML 导入修复' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx020` | 治理一致性 | — | `docs/dispatch/mx/mx020-rss-save-transaction.md:1` | 卡 mx020 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx019` | 治理一致性 | — | `docs/dispatch/mx/mx019-backend-coverage-core-tests.md:3` | 卡 mx019 的关联字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx019` | 治理一致性 | — | `docs/dispatch/mx/mx019-backend-coverage-core-tests.md:1` | 卡 mx019 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx018` | 治理一致性 | — | `docs/dispatch/mx/mx018-rss-reader-css-class.md:3` | 卡 mx018 的关联字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx018` | 治理一致性 | — | `docs/dispatch/mx/mx018-rss-reader-css-class.md:1` | 卡 mx018 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx017` | 治理一致性 | — | `docs/dispatch/mx/mx017-rss-image-proxy.md:3` | 卡 mx017 的关联字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx017` | 治理一致性 | — | `docs/dispatch/mx/mx017-rss-image-proxy.md:1` | 卡 mx017 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx016` | 治理一致性 | — | `docs/dispatch/mx/mx016-pc-keyboard-shortcuts.md:3` | 卡 mx016 的关联字段 'ccc-plan: medio-0 打磨第二批：交互/安全/显示/质量四线推进' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx016` | 治理一致性 | — | `docs/dispatch/mx/mx016-pc-keyboard-shortcuts.md:1` | 卡 mx016 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx015` | 治理一致性 | — | `docs/dispatch/mx/mx015-crawl-all-error-writeback.md:3` | 卡 mx015 的关联字段 'ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx015` | 治理一致性 | — | `docs/dispatch/mx/mx015-crawl-all-error-writeback.md:1` | 卡 mx015 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx014` | 治理一致性 | — | `docs/dispatch/mx/mx014-crawl-all-image-localization.md:3` | 卡 mx014 的关联字段 'ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx014` | 治理一致性 | — | `docs/dispatch/mx/mx014-crawl-all-image-localization.md:1` | 卡 mx014 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx013` | 治理一致性 | — | `docs/dispatch/mx/mx013-architecture-doc-dev-guide.md:3` | 卡 mx013 的关联字段 'ccc-plan: medio-0 框架优化第一批：文档地基 + RSS 巡检链路补齐' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx013` | 治理一致性 | — | `docs/dispatch/mx/mx013-architecture-doc-dev-guide.md:1` | 卡 mx013 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx012` | 治理一致性 | — | `docs/dispatch/mx/mx012-rss-stats-backend-aggregation.md:3` | 卡 mx012 的关联字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx012` | 治理一致性 | — | `docs/dispatch/mx/mx012-rss-stats-backend-aggregation.md:1` | 卡 mx012 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx011` | 治理一致性 | — | `docs/dispatch/mx/mx011-tablet-breakpoint-layout-fix.md:3` | 卡 mx011 的关联字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx011` | 治理一致性 | — | `docs/dispatch/mx/mx011-tablet-breakpoint-layout-fix.md:1` | 卡 mx011 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx010` | 治理一致性 | — | `docs/dispatch/mx/mx010-opml-export-bearer-auth.md:3` | 卡 mx010 的关联字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx010` | 治理一致性 | — | `docs/dispatch/mx/mx010-opml-export-bearer-auth.md:1` | 卡 mx010 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx009` | 治理一致性 | — | `docs/dispatch/mx/mx009-atom-parser-library.md:3` | 卡 mx009 的关联字段 'ccc-plan: mx HTTP 页面修复第一批：RSS P0/P1 四项' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx009` | 治理一致性 | — | `docs/dispatch/mx/mx009-atom-parser-library.md:1` | 卡 mx009 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx008` | 治理一致性 | — | `docs/dispatch/mx/mx008-http-page-ux-audit.md:3` | 卡 mx008 的关联字段 'ccc-plan: HTTP 页面体验巡检：RSS 优先 + 全页面代码/显示/双端适配' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx008` | 治理一致性 | — | `docs/dispatch/mx/mx008-http-page-ux-audit.md:1` | 卡 mx008 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx007` | 治理一致性 | — | `docs/dispatch/mx/mx007-settings-path-frontend-validation.md:3` | 卡 mx007 的关联字段 'ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx007` | 治理一致性 | — | `docs/dispatch/mx/mx007-settings-path-frontend-validation.md:1` | 卡 mx007 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx006` | 治理一致性 | — | `docs/dispatch/mx/mx006-cargo-fmt-ci-gate.md:3` | 卡 mx006 的关联字段 'ccc-plan: mx 打磨第一批：后端格式门禁 + 设置页路径校验' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx006` | 治理一致性 | — | `docs/dispatch/mx/mx006-cargo-fmt-ci-gate.md:1` | 卡 mx006 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx005` | 治理一致性 | — | `docs/dispatch/mx/mx005-polish-inventory.md:3` | 卡 mx005 的关联字段 'ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx005` | 治理一致性 | — | `docs/dispatch/mx/mx005-polish-inventory.md:1` | 卡 mx005 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx005` | 治理一致性 | — | `docs/roadmap.md:237` | 路线图状态 '已回写' (期望 已回写) 与卡真实状态 '已关闭' 漂移。 |
| 🟡 黄旗 | `mx004` | 治理一致性 | — | `docs/dispatch/mx/mx004-service-health-probe.md:3` | 卡 mx004 的关联字段 'ccc-plan: mx 打磨线启动：服务健康巡检 + 打磨盘点' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx004` | 治理一致性 | — | `docs/dispatch/mx/mx004-service-health-probe.md:1` | 卡 mx004 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx003` | 治理一致性 | — | `docs/dispatch/mx/mx003-recon-business-tracks.md:3` | 卡 mx003 的关联字段 'mx 业务线路摸底' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx003` | 治理一致性 | — | `docs/dispatch/mx/mx003-recon-business-tracks.md:1` | 卡 mx003 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx003` | 治理一致性 | — | `docs/roadmap.md:236` | 路线图状态 '已回写' (期望 已回写) 与卡真实状态 '已关闭' 漂移。 |
| 🟡 黄旗 | `mx002` | 治理一致性 | — | `docs/dispatch/mx/mx002-add-server-health-api-and-python-smoke-test.md:3` | 卡 mx002 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx002` | 治理一致性 | — | `docs/dispatch/mx/mx002-add-server-health-api-and-python-smoke-test.md:1` | 卡 mx002 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `mx001` | 治理一致性 | — | `docs/dispatch/mx/mx001-recon-and-baseline.md:3` | 卡 mx001 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `mx001` | 治理一致性 | — | `docs/dispatch/mx/mx001-recon-and-baseline.md:1` | 卡 mx001 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp022` | 治理一致性 | — | `docs/dispatch/hp/hp022-collector-network-error-retry.md:3` | 卡 hp022 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp022` | 治理一致性 | — | `docs/dispatch/hp/hp022-collector-network-error-retry.md:1` | 卡 hp022 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp021` | 治理一致性 | — | `docs/dispatch/hp/hp021-search-result-relevance-scoring-display.md:3` | 卡 hp021 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp021` | 治理一致性 | — | `docs/dispatch/hp/hp021-search-result-relevance-scoring-display.md:1` | 卡 hp021 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp020` | 治理一致性 | — | `docs/dispatch/hp/hp020-chunk.md:3` | 卡 hp020 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp020` | 治理一致性 | — | `docs/dispatch/hp/hp020-chunk.md:1` | 卡 hp020 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp019` | 治理一致性 | — | `docs/dispatch/hp/hp019-task.md:3` | 卡 hp019 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp019` | 治理一致性 | — | `docs/dispatch/hp/hp019-task.md:1` | 卡 hp019 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp018` | 治理一致性 | — | `docs/dispatch/hp/hp018-hp-pg-backtest-cron.md:3` | 卡 hp018 的关联字段 'INT-075' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp018` | 治理一致性 | — | `docs/dispatch/hp/hp018-hp-pg-backtest-cron.md:1` | 卡 hp018 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp017` | 治理一致性 | — | `docs/dispatch/hp/hp017-chunk-hp007.md:3` | 卡 hp017 的关联字段 'hp007 遗留：存量 445 短 chunk 处理方案落库' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp017` | 治理一致性 | — | `docs/dispatch/hp/hp017-chunk-hp007.md:1` | 卡 hp017 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp016` | 治理一致性 | — | `docs/dispatch/hp/hp016-collector-pipeline-repair.md:3` | 卡 hp016 的关联字段 'ccc-plan: HP 采集管道完整性修复（ingest/md_parser 恢复 + 解析 bug + ccc-docs 补采）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp016` | 治理一致性 | — | `docs/dispatch/hp/hp016-collector-pipeline-repair.md:1` | 卡 hp016 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp015` | 治理一致性 | — | `docs/dispatch/hp/hp015-frontend-page-test-coverage.md:3` | 卡 hp015 的关联字段 'ccc-plan: HP 前端测试覆盖补齐（页面渲染 + 关键交互，目标测试评分 4→7）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp015` | 治理一致性 | — | `docs/dispatch/hp/hp015-frontend-page-test-coverage.md:1` | 卡 hp015 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp014` | 治理一致性 | — | `docs/dispatch/hp/hp014-backend-export-library-count.md:3` | 卡 hp014 的关联字段 'ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp014` | 治理一致性 | — | `docs/dispatch/hp/hp014-backend-export-library-count.md:1` | 卡 hp014 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp013` | 治理一致性 | — | `docs/dispatch/hp/hp013-library-doc-activity-notes-real-data.md:3` | 卡 hp013 的关联字段 'ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp013` | 治理一致性 | — | `docs/dispatch/hp/hp013-library-doc-activity-notes-real-data.md:1` | 卡 hp013 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp012` | 治理一致性 | — | `docs/dispatch/hp/hp012-dashboard-search-real-data.md:3` | 卡 hp012 的关联字段 'ccc-plan: HP 前端里程碑开发（真数据接入/后端接口/空态/测试，目标 75+ 分）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp012` | 治理一致性 | — | `docs/dispatch/hp/hp012-dashboard-search-real-data.md:1` | 卡 hp012 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp011` | 治理一致性 | — | `docs/dispatch/hp/hp011-qb-docs-ownership-fix.md:3` | 卡 hp011 的关联字段 'ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp011` | 治理一致性 | — | `docs/dispatch/hp/hp011-qb-docs-ownership-fix.md:1` | 卡 hp011 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp010` | 治理一致性 | — | `docs/dispatch/hp/hp010-collector-multisource-fix.md:3` | 卡 hp010 的关联字段 'ccc-plan: HP 知识底座落地推进（存量落库/采集管道固化/qb 归属修正）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp010` | 治理一致性 | — | `docs/dispatch/hp/hp010-collector-multisource-fix.md:1` | 卡 hp010 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp008` | 治理一致性 | — | `docs/dispatch/hp/hp008-project-id-mapping-plan.md:3` | 卡 hp008 的关联字段 'ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp008` | 治理一致性 | — | `docs/dispatch/hp/hp008-project-id-mapping-plan.md:1` | 卡 hp008 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp007` | 治理一致性 | — | `docs/dispatch/hp/hp007-cli-fulltext-and-short-chunk-gate.md:3` | 卡 hp007 的关联字段 'ccc-plan: HP 知识底座评估整改（CLI 检索复活/短 chunk 闸门/口径映射/文档回填）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp007` | 治理一致性 | — | `docs/dispatch/hp/hp007-cli-fulltext-and-short-chunk-gate.md:1` | 卡 hp007 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp006` | 治理一致性 | — | `docs/dispatch/hp/hp006-search-quality-short-chunks.md:3` | 卡 hp006 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp006` | 治理一致性 | — | `docs/dispatch/hp/hp006-search-quality-short-chunks.md:1` | 卡 hp006 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp006` | 治理一致性 | — | `docs/roadmap.md:221` | 路线图状态 '已回写 (外仓 main 未含，在 codex/hp006-search-quality-short-chunks 分支)' (期望 已回写) 与卡真实状态 '已关闭' 漂移。 |
| 🟡 黄旗 | `hp005` | 治理一致性 | — | `docs/dispatch/hp/hp005-frontend-fake-data-contract.md:3` | 卡 hp005 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp005` | 治理一致性 | — | `docs/dispatch/hp/hp005-frontend-fake-data-contract.md:1` | 卡 hp005 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp005` | 治理一致性 | — | `docs/roadmap.md:220` | 路线图状态 '已回写 (外仓 main 未含，在 codex/hp005-frontend-fake-data-contract 分支)' (期望 已回写) 与卡真实状态 '已关闭' 漂移。 |
| 🟡 黄旗 | `hp004` | 治理一致性 | — | `docs/dispatch/hp/hp004-collector-source-expansion.md:3` | 卡 hp004 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp004` | 治理一致性 | — | `docs/dispatch/hp/hp004-collector-source-expansion.md:1` | 卡 hp004 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp004` | 治理一致性 | — | `docs/roadmap.md:219` | 路线图状态 '已回写 (外仓 main 未含，在 codex/hp004-collector-source-expansion 分支)' (期望 已回写) 与卡真实状态 '已关闭' 漂移。 |
| 🟡 黄旗 | `hp003` | 治理一致性 | — | `docs/dispatch/hp/hp003-backup-alignment.md:3` | 卡 hp003 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp003` | 治理一致性 | — | `docs/dispatch/hp/hp003-backup-alignment.md:1` | 卡 hp003 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp002` | 治理一致性 | — | `docs/dispatch/hp/hp002-monitoring-git-probe.md:3` | 卡 hp002 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp002` | 治理一致性 | — | `docs/dispatch/hp/hp002-monitoring-git-probe.md:1` | 卡 hp002 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `hp001` | 治理一致性 | — | `docs/dispatch/hp/hp001-recon-baseline-roadmap.md:3` | 卡 hp001 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `hp001` | 治理一致性 | — | `docs/dispatch/hp/hp001-recon-baseline-roadmap.md:1` | 卡 hp001 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `clw008` | 治理一致性 | — | `docs/dispatch/clw/clw008-package-acceptance.md:3` | 卡 clw008 的关联字段 'ccc-plan: clw006 打包 + 全链路验收' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `clw007` | 治理一致性 | — | `docs/dispatch/clw/clw007-resume-cwd-fix.md:3` | 卡 clw007 的关联字段 'ccc-plan: clw007 会话恢复工作目录 + 小缺陷修复' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `clw001` | 逆向巡查 | — | `docs/projects/clw/plans/001-clwarp-tauri-skeleton.md:1` | 开发卡 clw001 已关闭，但其关联方案 clw-plan-001 的状态仍为 '部分执行' (未完成)。 |
| 🟡 黄旗 | `clw` | 治理一致性 | — | `docs/roadmap.md:1` | 项目 clw 缺失对应的 业务线路（clw）段落。 |
| 🟡 黄旗 | `cd` | 治理一致性 | — | `docs/roadmap.md:1` | 项目 cd 缺失对应的 业务线路（cd）段落。 |
| 🟡 黄旗 | `ccc020` | 治理一致性 | — | `docs/dispatch/ccc/ccc020-prompt-injection-dashboard.md:3` | 卡 ccc020 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc020` | 治理一致性 | — | `docs/dispatch/ccc/ccc020-prompt-injection-dashboard.md:1` | 卡 ccc020 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc019` | 治理一致性 | — | `docs/dispatch/ccc/ccc019-engine-gate-skip-metrics.md:3` | 卡 ccc019 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc019` | 治理一致性 | — | `docs/dispatch/ccc/ccc019-engine-gate-skip-metrics.md:1` | 卡 ccc019 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc018` | 治理一致性 | — | `docs/dispatch/ccc/ccc018-task.md:3` | 卡 ccc018 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc018` | 治理一致性 | — | `docs/dispatch/ccc/ccc018-task.md:1` | 卡 ccc018 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc017` | 治理一致性 | — | `docs/dispatch/ccc/ccc017-prompt.md:3` | 卡 ccc017 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc017` | 治理一致性 | — | `docs/dispatch/ccc/ccc017-prompt.md:1` | 卡 ccc017 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc016` | 治理一致性 | — | `docs/dispatch/ccc/ccc016-t73-t70-p1-11.md:3` | 卡 ccc016 的关联字段 'INT-129' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc016` | 治理一致性 | — | `docs/dispatch/ccc/ccc016-t73-t70-p1-11.md:1` | 卡 ccc016 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc015` | 治理一致性 | — | `docs/dispatch/ccc/ccc015-gate-audit-separation.md:3` | 卡 ccc015 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc015` | 治理一致性 | — | `docs/dispatch/ccc/ccc015-gate-audit-separation.md:1` | 卡 ccc015 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc014` | 治理一致性 | — | `docs/dispatch/ccc/ccc014-converge-stale-remote-branches.md:3` | 卡 ccc014 的关联字段 'CCC 治理' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc014` | 治理一致性 | — | `docs/dispatch/ccc/ccc014-converge-stale-remote-branches.md:1` | 卡 ccc014 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc013` | 治理一致性 | — | `docs/dispatch/ccc/ccc013-flow-verify-pipeline.md:3` | 卡 ccc013 的关联字段 'CCC 系统化升级' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc013` | 治理一致性 | — | `docs/dispatch/ccc/ccc013-flow-verify-pipeline.md:1` | 卡 ccc013 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc012` | 治理一致性 | — | `docs/dispatch/ccc/ccc012-48-codex.md:3` | 卡 ccc012 的关联字段 '升级批次 3 生命周期' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc012` | 治理一致性 | — | `docs/dispatch/ccc/ccc012-48-codex.md:1` | 卡 ccc012 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc010` | 治理一致性 | — | `docs/dispatch/ccc/ccc010-roadmap-business-track-xy.md:3` | 卡 ccc010 的关联字段 'ccc-plan: 文档卫生与业务总线路图' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc010` | 治理一致性 | — | `docs/dispatch/ccc/ccc010-roadmap-business-track-xy.md:1` | 卡 ccc010 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc009` | 治理一致性 | — | `docs/dispatch/ccc/ccc009-stale-docs-archive-cleanup.md:3` | 卡 ccc009 的关联字段 'ccc-plan: 文档卫生与业务总线路图' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc009` | 治理一致性 | — | `docs/dispatch/ccc/ccc009-stale-docs-archive-cleanup.md:1` | 卡 ccc009 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc008` | 治理一致性 | — | `docs/dispatch/ccc/ccc008-ready-probe-script.md:3` | 卡 ccc008 的关联字段 'ccc-plan: M7 ready-probe dogfood' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc008` | 治理一致性 | — | `docs/dispatch/ccc/ccc008-ready-probe-script.md:1` | 卡 ccc008 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc007` | 治理一致性 | — | `docs/dispatch/ccc/ccc007-m5-audit-dogfood-rebase-hint.md:3` | 卡 ccc007 的关联字段 'M5 真机审狗粮' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc007` | 治理一致性 | — | `docs/dispatch/ccc/ccc007-m5-audit-dogfood-rebase-hint.md:1` | 卡 ccc007 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc006` | 治理一致性 | — | `docs/dispatch/ccc/ccc006-engine-audit-auto-backfill.md:3` | 卡 ccc006 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc006` | 治理一致性 | — | `docs/dispatch/ccc/ccc006-engine-audit-auto-backfill.md:1` | 卡 ccc006 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc005` | 治理一致性 | — | `docs/dispatch/ccc/ccc005-registry-single-source.md:3` | 卡 ccc005 的关联字段 '文档与项目注册统一治理' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc005` | 治理一致性 | — | `docs/dispatch/ccc/ccc005-registry-single-source.md:1` | 卡 ccc005 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc004` | 治理一致性 | — | `docs/dispatch/ccc/ccc004-register-ccc-demo-prefix.md:3` | 卡 ccc004 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc004` | 治理一致性 | — | `docs/dispatch/ccc/ccc004-register-ccc-demo-prefix.md:1` | 卡 ccc004 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc003` | 治理一致性 | — | `docs/dispatch/ccc/ccc003-engine-anti-fake-success-and-template-align.md:3` | 卡 ccc003 的关联字段 'E2E联调技术债 2026-08-06' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc003` | 治理一致性 | — | `docs/dispatch/ccc/ccc003-engine-anti-fake-success-and-template-align.md:1` | 卡 ccc003 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc002` | 治理一致性 | — | `docs/dispatch/ccc/ccc002-e2e-smoke-opencode.md:3` | 卡 ccc002 的关联字段 'E2E联调 OpenCode 2026-08-06' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc002` | 治理一致性 | — | `docs/dispatch/ccc/ccc002-e2e-smoke-opencode.md:1` | 卡 ccc002 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc001` | 治理一致性 | — | `docs/dispatch/ccc/ccc001-e2e-smoke-engine-dirty.md:3` | 卡 ccc001 的关联字段 'E2E联调 2026-08-06' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `ccc001` | 治理一致性 | — | `docs/dispatch/ccc/ccc001-e2e-smoke-engine-dirty.md:1` | 卡 ccc001 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `ccc-plan-009` | 逆向巡查 | — | `docs/projects/ccc/plans/009-plans-page-implementation.md:1` | 方案 ccc-plan-009 处于已完成状态，但没有关联任何开发卡。 |
| 🟡 黄旗 | `ccc-plan-002` | 逆向巡查 | — | `docs/projects/ccc/plans/002-arch-roadmap-upgrade.md:1` | 方案 ccc-plan-002 处于已完成状态，但没有关联任何开发卡。 |
| 🟡 黄旗 | `ccc` | 治理一致性 | — | `docs/roadmap.md:1` | 项目 ccc 缺失对应的 业务线路（ccc）段落。 |
| 🟡 黄旗 | `T9` | 治理一致性 | — | `docs/dispatch/T9-kb-seed.md:3` | 卡 T9 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T9` | 治理一致性 | — | `docs/dispatch/T9-kb-seed.md:1` | 卡 T9 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T8-X` | 治理一致性 | — | `docs/dispatch/T8-X-execute-switch.md:3` | 卡 T8-X 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T8-X` | 治理一致性 | — | `docs/dispatch/T8-X-execute-switch.md:1` | 卡 T8-X 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T8` | 治理一致性 | — | `docs/dispatch/T8-switch-checklist.md:3` | 卡 T8 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T8` | 治理一致性 | — | `docs/dispatch/T8-switch-checklist.md:1` | 卡 T8 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T76` | 治理一致性 | — | `docs/dispatch/T76-conversation-base-hardening.md:3` | 卡 T76 的关联字段 '对话大底座加固（F16）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T76` | 治理一致性 | — | `docs/dispatch/T76-conversation-base-hardening.md:1` | 卡 T76 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T72` | 治理一致性 | — | `docs/dispatch/T72-fix-desktop-p0.md:3` | 卡 T72 的关联字段 'T70 审计 P0（F18 workspace 传路径 / F19 Kanban 英文旧列 / F20 流式缺 thread_id/model）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T72` | 治理一致性 | — | `docs/dispatch/T72-fix-desktop-p0.md:1` | 卡 T72 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T71` | 治理一致性 | — | `docs/dispatch/T71-fix-server-p0.md:3` | 卡 T71 的关联字段 'T70 审计 P0（F01 卡头替换误改正文 / F02 非 UTF-8 卡拖垮扫描 / F11 SSE 断流不 settle）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T71` | 治理一致性 | — | `docs/dispatch/T71-fix-server-p0.md:1` | 卡 T71 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T70` | 治理一致性 | — | `docs/dispatch/T70-code-audit.md:3` | 卡 T70 的关联字段 '老板 2026-08-06 指示「Cursor 做一次全部 CCC 项目检查，主要做代码 bug 检查」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T70` | 治理一致性 | — | `docs/dispatch/T70-code-audit.md:1` | 卡 T70 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T7` | 治理一致性 | — | `docs/dispatch/T7-ops-timer-p4.md:3` | 卡 T7 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T7` | 治理一致性 | — | `docs/dispatch/T7-ops-timer-p4.md:1` | 卡 T7 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T69` | 治理一致性 | — | `docs/dispatch/T69-release-engine-plist-rebuild.md:3` | 卡 T69 的关联字段 'T68 部署事故（2026-08-05：start_engine 遇 plist 缺失仅 WARN，Engine 掉线未恢复，Codex 现场重建恢复）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T69` | 治理一致性 | — | `docs/dispatch/T69-release-engine-plist-rebuild.md:1` | 卡 T69 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T68` | 治理一致性 | — | `docs/dispatch/T68-http-resource-resilience.md:3` | 卡 T68 的关联字段 'T48 审计 P0（M1→2017 静态资源并发 ERR_CONNECTION_RESET 41%，SPA 白屏根因，前端侧）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T68` | 治理一致性 | — | `docs/dispatch/T68-http-resource-resilience.md:1` | 卡 T68 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T67` | 治理一致性 | — | `docs/dispatch/T67-deploy-race-guard.md:3` | 卡 T67 的关联字段 'T60 误派复盘（2026-08-05 部署窗口：已验收卡因卡头未同步被 Engine 重新拉起）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T67` | 治理一致性 | — | `docs/dispatch/T67-deploy-race-guard.md:1` | 卡 T67 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T66` | 治理一致性 | — | `docs/dispatch/T66-card-format-debt.md:3` | 卡 T66 的关联字段 '任务卡体系规则（旧卡 69 处格式偏差规范化）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T66` | 治理一致性 | — | `docs/dispatch/T66-card-format-debt.md:1` | 卡 T66 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T65` | 治理一致性 | — | `docs/dispatch/T65-dual-shell-align.md:3` | 卡 T65 的关联字段 '前端四板块架构（T-B5 双壳对齐）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T65` | 治理一致性 | — | `docs/dispatch/T65-dual-shell-align.md:1` | 卡 T65 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T64` | 治理一致性 | — | `docs/dispatch/T64-engine-auto-worktree.md:3` | 卡 T64 的关联字段 'T59 并行派发发现——每卡需独立 worktree，当前靠卡内续作指令手动建' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T64` | 治理一致性 | — | `docs/dispatch/T64-engine-auto-worktree.md:1` | 卡 T64 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T63` | 治理一致性 | — | `docs/dispatch/T63-nginx-entry.md:3` | 卡 T63 的关联字段 '阶段 3（Nginx 统一入口）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T63` | 治理一致性 | — | `docs/dispatch/T63-nginx-entry.md:1` | 卡 T63 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T62` | 治理一致性 | — | `docs/dispatch/T62-archive-review.md:3` | 卡 T62 的关联字段 '阶段 3（T-A5）+ T50 联调发现（/cards 缺索引返回空，需兜底）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T62` | 治理一致性 | — | `docs/dispatch/T62-archive-review.md:1` | 卡 T62 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T61` | 治理一致性 | — | `docs/dispatch/T61-task-flow-linked.md:3` | 卡 T61 的关联字段 '前端四板块架构（T-B4）+ T49 对话即工作' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T61` | 治理一致性 | — | `docs/dispatch/T61-task-flow-linked.md:1` | 卡 T61 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T60` | 治理一致性 | — | `docs/dispatch/T60-console-cockpit.md:3` | 卡 T60 的关联字段 '前端四板块架构（T-B3）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T60` | 治理一致性 | — | `docs/dispatch/T60-console-cockpit.md:1` | 卡 T60 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T6` | 治理一致性 | — | `docs/dispatch/T6-roadmap-p3.md:3` | 卡 T6 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T6` | 治理一致性 | — | `docs/dispatch/T6-roadmap-p3.md:1` | 卡 T6 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T59` | 治理一致性 | — | `docs/dispatch/T59-engine-parallel-relay-guard.md:3` | 卡 T59 的关联字段 '过夜任务发现——① Engine 串行派发（同步等执行体完成才派下一张）；② 上游中继多次波动导致执行卡死/超时' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T59` | 治理一致性 | — | `docs/dispatch/T59-engine-parallel-relay-guard.md:1` | 卡 T59 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T58` | 治理一致性 | — | `docs/dispatch/T58-board-refactor.md:3` | 卡 T58 的关联字段 '阶段 3（T-B2，过夜任务前端链 2/2）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T58` | 治理一致性 | — | `docs/dispatch/T58-board-refactor.md:1` | 卡 T58 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T57` | 治理一致性 | — | `docs/dispatch/T57-big-small-cards.md:3` | 卡 T57 的关联字段 '阶段 3（T-A4，过夜任务后端链 2/3）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T57` | 治理一致性 | — | `docs/dispatch/T57-big-small-cards.md:1` | 卡 T57 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T56` | 治理一致性 | — | `docs/dispatch/T56-card-components.md:3` | 卡 T56 的关联字段 '阶段 3（T-B1 统一卡片组件，过夜任务前端链 1/2）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T56` | 治理一致性 | — | `docs/dispatch/T56-card-components.md:1` | 卡 T56 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T55` | 治理一致性 | — | `docs/dispatch/T55-index-layer.md:3` | 卡 T55 的关联字段 '阶段 3（T-A2 索引层，过夜任务后端链 1/3）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T55` | 治理一致性 | — | `docs/dispatch/T55-index-layer.md:1` | 卡 T55 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T54` | 治理一致性 | — | `docs/dispatch/T54-auto-naming-migration.md:3` | 卡 T54 的关联字段 '阶段 3（T-A1 命名规则落地，Codex 决策 2026-08-04）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T54` | 治理一致性 | — | `docs/dispatch/T54-auto-naming-migration.md:1` | 卡 T54 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T53` | 治理一致性 | — | `docs/dispatch/T53-console-roadmap-fix.md:3` | 卡 T53 的关联字段 '阶段 3（控制台/线路图修复，老板 2026-08-04）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T53` | 治理一致性 | — | `docs/dispatch/T53-console-roadmap-fix.md:1` | 卡 T53 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T52` | 治理一致性 | — | `docs/dispatch/T52-automation-base.md:3` | 卡 T52 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T52` | 治理一致性 | — | `docs/dispatch/T52-automation-base.md:1` | 卡 T52 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T51` | 治理一致性 | — | `docs/dispatch/T51-knowledge-mcp-optimize.md:3` | 卡 T51 的关联字段 '阶段 3 P1' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T51` | 治理一致性 | — | `docs/dispatch/T51-knowledge-mcp-optimize.md:1` | 卡 T51 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T50` | 治理一致性 | — | `docs/dispatch/T50-dual-shell-e2e-acceptance.md:3` | 卡 T50 的关联字段 '业务流程打通收口' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T50` | 治理一致性 | — | `docs/dispatch/T50-dual-shell-e2e-acceptance.md:1` | 卡 T50 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T5` | 治理一致性 | — | `docs/dispatch/T5-board-schedule.md:3` | 卡 T5 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T5` | 治理一致性 | — | `docs/dispatch/T5-board-schedule.md:1` | 卡 T5 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T49` | 治理一致性 | — | `docs/dispatch/T49-conversation-as-workflow.md:3` | 卡 T49 的关联字段 '老板指示「站在业务流程梳理高度，前端界面与后端功能业务打通」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T49` | 治理一致性 | — | `docs/dispatch/T49-conversation-as-workflow.md:1` | 卡 T49 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T48` | 治理一致性 | — | `docs/dispatch/T48-shell-problem-audit.md:3` | 卡 T48 的关联字段 '老板反馈「桌面端和 HTTP 页面小问题非常多」+「展示逻辑借鉴 Codex/Cursor 成熟工具」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T48` | 治理一致性 | — | `docs/dispatch/T48-shell-problem-audit.md:1` | 卡 T48 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T47` | 治理一致性 | — | `docs/dispatch/T47-project-thread-sidebar.md:3` | 卡 T47 的关联字段 '老板指出「左侧栏展示逻辑错误——应该项目+对话，用项目区分，不是任务分组；展示逻辑借鉴 Codex/Cursor 成熟工具」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T47` | 治理一致性 | — | `docs/dispatch/T47-project-thread-sidebar.md:1` | 卡 T47 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T46` | 治理一致性 | — | `docs/dispatch/T46-conversation-stability-sse.md:3` | 卡 T46 的关联字段 '老板实测反馈（2026-08-04）「对话过程中切换界面就中断」「思考过程/思考文字没展示」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T46` | 治理一致性 | — | `docs/dispatch/T46-conversation-stability-sse.md:1` | 卡 T46 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T45` | 治理一致性 | — | `docs/dispatch/T45-user-centric-ux-overhaul.md:3` | 卡 T45 的关联字段 '老板实测强烈反馈（2026-08-04）——「登录脱裤子放屁」「发一次就断」「无流式无工具卡」「界面一堆 bug」；Codex 真机取证逐项定位根因' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T45` | 治理一致性 | — | `docs/dispatch/T45-user-centric-ux-overhaul.md:1` | 卡 T45 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T44` | 治理一致性 | — | `docs/dispatch/T44-shell-ux-optimization.md:3` | 卡 T44 的关联字段 '老板实测反馈「问题太多」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T44` | 治理一致性 | — | `docs/dispatch/T44-shell-ux-optimization.md:1` | 卡 T44 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T43` | 治理一致性 | — | `docs/dispatch/T43-conversation-long-poll.md:3` | 卡 T43 的关联字段 '新阶段「对话壳感知 + 增量同步」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T43` | 治理一致性 | — | `docs/dispatch/T43-conversation-long-poll.md:1` | 卡 T43 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T42` | 治理一致性 | — | `docs/dispatch/T42-dual-shell-e2e-acceptance.md:3` | 卡 T42 的关联字段 '新阶段「双壳可用 + 心智升级」收口' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T42` | 治理一致性 | — | `docs/dispatch/T42-dual-shell-e2e-acceptance.md:1` | 卡 T42 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T41` | 治理一致性 | — | `docs/dispatch/T41-brain-mind-streaming.md:3` | 卡 T41 的关联字段 '新阶段「双壳可用 + 心智升级」' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T41` | 治理一致性 | — | `docs/dispatch/T41-brain-mind-streaming.md:1` | 卡 T41 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T40` | 治理一致性 | — | `docs/dispatch/T40-shell-base-3col-ui.md:3` | 卡 T40 的关联字段 '新阶段「双壳可用 + 心智升级」（老板 2026-08-03 指示）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T40` | 治理一致性 | — | `docs/dispatch/T40-shell-base-3col-ui.md:1` | 卡 T40 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T4-R` | 治理一致性 | — | `docs/dispatch/T4-R-deploy-hardcode-fix.md:3` | 卡 T4-R 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T4-R` | 治理一致性 | — | `docs/dispatch/T4-R-deploy-hardcode-fix.md:1` | 卡 T4-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T4` | 治理一致性 | — | `docs/dispatch/T4-relay-mac2017.md:3` | 卡 T4 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T4` | 治理一致性 | — | `docs/dispatch/T4-relay-mac2017.md:1` | 卡 T4 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T39` | 治理一致性 | — | `docs/dispatch/T39-engine-dispatch-by-binding.md:3` | 卡 T39 的关联字段 'INT-120 关闭后新阶段' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T39` | 治理一致性 | — | `docs/dispatch/T39-engine-dispatch-by-binding.md:1` | 卡 T39 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T38` | 治理一致性 | — | `docs/dispatch/T38-m4-handoff-acceptance.md:3` | 卡 T38 的关联字段 'INT-120（M4 知识移植/独立移交' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T38` | 治理一致性 | — | `docs/dispatch/T38-m4-handoff-acceptance.md:1` | 卡 T38 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T37` | 治理一致性 | — | `docs/dispatch/T37-m4-brain-kb.md:3` | 卡 T37 的关联字段 'INT-120（M4 知识移植/独立移交' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T37` | 治理一致性 | — | `docs/dispatch/T37-m4-brain-kb.md:1` | 卡 T37 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T36` | 治理一致性 | — | `docs/dispatch/T36-m4-kb-seed-refresh.md:3` | 卡 T36 的关联字段 'INT-120（M4 知识移植/独立移交' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T36` | 治理一致性 | — | `docs/dispatch/T36-m4-kb-seed-refresh.md:1` | 卡 T36 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T35` | 治理一致性 | — | `docs/dispatch/T35-refactor-closeout-hangover-regression.md:3` | 卡 T35 的关联字段 'INT-120（CCC 重构收口）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T35` | 治理一致性 | — | `docs/dispatch/T35-refactor-closeout-hangover-regression.md:1` | 卡 T35 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T34` | 治理一致性 | — | `docs/dispatch/T34-refactor-closeout-deadcode-dual-shell.md:3` | 卡 T34 的关联字段 'INT-120（CCC 重构收口）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T34` | 治理一致性 | — | `docs/dispatch/T34-refactor-closeout-deadcode-dual-shell.md:1` | 卡 T34 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T33` | 治理一致性 | — | `docs/dispatch/T33-refactor-closeout-hardcode-cluster.md:3` | 卡 T33 的关联字段 'INT-120（CCC 重构收口）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T33` | 治理一致性 | — | `docs/dispatch/T33-refactor-closeout-hardcode-cluster.md:1` | 卡 T33 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T32` | 治理一致性 | — | `docs/dispatch/T32-refactor-closeout-engine-real-dispatch.md:3` | 卡 T32 的关联字段 'INT-120（CCC 重构收口）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T32` | 治理一致性 | — | `docs/dispatch/T32-refactor-closeout-engine-real-dispatch.md:1` | 卡 T32 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T31` | 治理一致性 | — | `docs/dispatch/T31-refactor-closeout-docs-baseline.md:3` | 卡 T31 的关联字段 'INT-120（CCC 重构收口）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T31` | 治理一致性 | — | `docs/dispatch/T31-refactor-closeout-docs-baseline.md:1` | 卡 T31 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T30` | 治理一致性 | — | `docs/dispatch/T30-http-refactor.md:3` | 卡 T30 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T30` | 治理一致性 | — | `docs/dispatch/T30-http-refactor.md:1` | 卡 T30 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T3-R` | 治理一致性 | — | `docs/dispatch/T3-R-board-state-normalize.md:3` | 卡 T3-R 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T3-R` | 治理一致性 | — | `docs/dispatch/T3-R-board-state-normalize.md:1` | 卡 T3-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T3` | 治理一致性 | — | `docs/dispatch/T3-board-web.md:3` | 卡 T3 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T3` | 治理一致性 | — | `docs/dispatch/T3-board-web.md:1` | 卡 T3 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T29` | 治理一致性 | — | `docs/dispatch/T29-chat-brain-agent.md:3` | 卡 T29 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T29` | 治理一致性 | — | `docs/dispatch/T29-chat-brain-agent.md:1` | 卡 T29 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T28` | 治理一致性 | — | `docs/dispatch/T28-desktop-repackage.md:3` | 卡 T28 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T28` | 治理一致性 | — | `docs/dispatch/T28-desktop-repackage.md:1` | 卡 T28 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T27` | 治理一致性 | — | `docs/dispatch/T27-relay-2017-restart.md:3` | 卡 T27 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T27` | 治理一致性 | — | `docs/dispatch/T27-relay-2017-restart.md:1` | 卡 T27 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T26-R` | 治理一致性 | — | `docs/dispatch/T26-R-self-audit-cleanup.md:3` | 卡 T26-R 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T26-R` | 治理一致性 | — | `docs/dispatch/T26-R-self-audit-cleanup.md:1` | 卡 T26-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T26` | 治理一致性 | — | `docs/dispatch/T26-desktop-backend-refactor.md:3` | 卡 T26 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T26` | 治理一致性 | — | `docs/dispatch/T26-desktop-backend-refactor.md:1` | 卡 T26 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T25` | 治理一致性 | — | `docs/dispatch/T25-restore-legacy-chat.md:3` | 卡 T25 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T25` | 治理一致性 | — | `docs/dispatch/T25-restore-legacy-chat.md:1` | 卡 T25 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T24-R` | 治理一致性 | — | `docs/dispatch/T24-R-desktop-protocol-align.md:3` | 卡 T24-R 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T24-R` | 治理一致性 | — | `docs/dispatch/T24-R-desktop-protocol-align.md:1` | 卡 T24-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T24` | 治理一致性 | — | `docs/dispatch/T24-desktop-repackage-web-chat.md:3` | 卡 T24 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T24` | 治理一致性 | — | `docs/dispatch/T24-desktop-repackage-web-chat.md:1` | 卡 T24 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T23` | 治理一致性 | — | `docs/dispatch/T23-http-direct-open.md:3` | 卡 T23 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T23` | 治理一致性 | — | `docs/dispatch/T23-http-direct-open.md:1` | 卡 T23 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T22` | 治理一致性 | — | `docs/dispatch/T22-deploy-2017.md:3` | 卡 T22 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T22` | 治理一致性 | — | `docs/dispatch/T22-deploy-2017.md:1` | 卡 T22 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T21` | 治理一致性 | — | `docs/dispatch/T21-ops-shell-migration.md:3` | 卡 T21 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T21` | 治理一致性 | — | `docs/dispatch/T21-ops-shell-migration.md:1` | 卡 T21 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T20` | 治理一致性 | — | `docs/dispatch/T20-board-shell-migration.md:3` | 卡 T20 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T20` | 治理一致性 | — | `docs/dispatch/T20-board-shell-migration.md:1` | 卡 T20 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T2` | 治理一致性 | — | `docs/dispatch/T2-engine-core.md:3` | 卡 T2 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T2` | 治理一致性 | — | `docs/dispatch/T2-engine-core.md:1` | 卡 T2 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T19` | 治理一致性 | — | `docs/dispatch/T19-shell-migration.md:3` | 卡 T19 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T19` | 治理一致性 | — | `docs/dispatch/T19-shell-migration.md:1` | 卡 T19 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T18` | 治理一致性 | — | `docs/dispatch/T18-phase2-retire-exec.md:3` | 卡 T18 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T18` | 治理一致性 | — | `docs/dispatch/T18-phase2-retire-exec.md:1` | 卡 T18 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T17` | 治理一致性 | — | `docs/dispatch/T17-full-acceptance.md:3` | 卡 T17 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T17` | 治理一致性 | — | `docs/dispatch/T17-full-acceptance.md:1` | 卡 T17 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T16` | 治理一致性 | — | `docs/dispatch/T16-shell-integration-api.md:3` | 卡 T16 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T16` | 治理一致性 | — | `docs/dispatch/T16-shell-integration-api.md:1` | 卡 T16 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T15` | 治理一致性 | — | `docs/dispatch/T15-legacy-retire-exec.md:3` | 卡 T15 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T15` | 治理一致性 | — | `docs/dispatch/T15-legacy-retire-exec.md:1` | 卡 T15 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T14-R` | 治理一致性 | — | `docs/dispatch/T14-R-e2e-new-stack.md:3` | 卡 T14-R 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T14-R` | 治理一致性 | — | `docs/dispatch/T14-R-e2e-new-stack.md:1` | 卡 T14-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T14` | 治理一致性 | — | `docs/dispatch/T14-e2e-pipeline-test.md:3` | 卡 T14 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T14` | 治理一致性 | — | `docs/dispatch/T14-e2e-pipeline-test.md:1` | 卡 T14 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T13` | 治理一致性 | — | `docs/dispatch/T13-server-http-api.md:3` | 卡 T13 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T13` | 治理一致性 | — | `docs/dispatch/T13-server-http-api.md:1` | 卡 T13 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T12-R` | 治理一致性 | — | `docs/dispatch/T12-R-legacy-2017-audit.md:3` | 卡 T12-R 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T12-R` | 治理一致性 | — | `docs/dispatch/T12-R-legacy-2017-audit.md:1` | 卡 T12-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T12` | 治理一致性 | — | `docs/dispatch/T12-legacy-retire-list.md:3` | 卡 T12 的关联字段 'INT-120（CCC 重构收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T12` | 治理一致性 | — | `docs/dispatch/T12-legacy-retire-list.md:1` | 卡 T12 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T11-R` | 治理一致性 | — | `docs/dispatch/T11-R-kb-closeout.md:3` | 卡 T11-R 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T11-R` | 治理一致性 | — | `docs/dispatch/T11-R-kb-closeout.md:1` | 卡 T11-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T11` | 治理一致性 | — | `docs/dispatch/T11-kb-mcp-semantic.md:3` | 卡 T11 的关联字段 'INT-120（CCC 重构，D3 收尾）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T11` | 治理一致性 | — | `docs/dispatch/T11-kb-mcp-semantic.md:1` | 卡 T11 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T10` | 治理一致性 | — | `docs/dispatch/T10-kb-init.md:3` | 卡 T10 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T10` | 治理一致性 | — | `docs/dispatch/T10-kb-init.md:1` | 卡 T10 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T1-R` | 治理一致性 | — | `docs/dispatch/T1-R-server-skeleton-deep.md:3` | 卡 T1-R 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T1-R` | 治理一致性 | — | `docs/dispatch/T1-R-server-skeleton-deep.md:1` | 卡 T1-R 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |
| 🟡 黄旗 | `T1` | 治理一致性 | — | `docs/dispatch/T1-server-skeleton.md:3` | 卡 T1 的关联字段 'INT-120（CCC 重构）' 不是有效的方案编号 (形如 <prefix>-plan-<NNN>)。 |
| 🟡 黄旗 | `T1` | 治理一致性 | — | `docs/dispatch/T1-server-skeleton.md:1` | 卡 T1 处于已关闭/已回写状态，但缺失 ## 维护区 章节。 |

---
*本报告由 CCC 逆向巡查 Agent 自动生成并输出。只读，仅记录状态，不修改任何项目数据文件。*
