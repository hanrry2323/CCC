# CCC 文档仓盘点表（只读分析席产出）

> 范围：`docs/projects/` 检出的 2 个项目（hp、mx）+ 根 `meta/last-commits.txt`
> 分级：现行 / 史实 / 作废 / 待核（不确定一律待核，不硬判）
> 证据来源：① `meta/last-commits.txt` 各文件最后实质改动时间 ② plans 正文自报状态/进度/勾选 ③ 与 README/roadmap 声称进度对照
> 盘点日：2026-09-13（「近 30 天」窗口 = 2026-08-14 ~ 2026-09-13）
> 只读边界：本文件为唯一写入物；未修改任何检出文件；检出非 git 仓（`git rev-parse` 失败），未执行任何 git 写操作

---

## hp / 知识库

### 1) 项目目标（出处：`docs/projects/hp/README.md`）

HP 个人 AI agent 的**中央知识库基础设施 + 教训沉淀平台**：PG18+pgvector 存储 documents/chunks/memory_store，Ollama 本地嵌入，提供全文知识底座与语义检索，并以 HP 为主库、ccc-kb 为离线降级副本的主备分层（README「## 是什么」+「## 线路 / 近况」+「附 A 技术栈表」+「附 C 业务线路梳理」）。

### 2) plans/ 逐篇定级

| plans 文件 | 方案自报 | 定级 | 证据 |
|---|---|---|---|
| 001-knowledge-base-milestone.md | 已完成，进度 21/21 | 史实 | 验收 4 项全 `[x]`；roadmap M1「已完成」并列 hp-plan-001（`docs/projects/hp/roadmap.md`「### M1」）；delivery-001「关联任务卡全关闭 hp001-022」 |
| 002-merge-close-branches.md | 已完成，进度 20/20 | 史实 | 验收 5 项全 `[x]`；README「M1 底座固化（已完成）：hp-plan-001/002」（README「## 线路 / 近况」） |
| 003-hp-plan-002.md | 作废 | 作废 | 备注「重构遗留空壳方案标记作废…2026-08-14 老板确认按最佳方案处理」；meta 条目 `docs(hp): hp-plan-003 重构遗留空壳方案标记作废` |
| 004-stability-and-recovery.md | 作废 | 作废 | 头部「⚠️ 2026-08-15 流程改造收回…作废收回；M2 子项目内容（2.1-2.7）待新模型下重新按子项目立项」；7 个验收项全部 `- [ ]`；内容已由 008~014 承接 |
| 005-observability-and-alerting.md | 作废 | 作废 | 同 08-15 收回语；5 个验收项全部 `- [ ]`；内容已由 015~019 承接 |
| 006-data-freshness-and-quality.md | 作废 | 作废 | 同 08-15 收回语；5 个验收项全部 `- [ ]`；内容已由 020~024 承接 |
| 007-ecosystem-consumption.md | 作废 | 作废 | 同 08-15 收回语；6 个验收项全部 `- [ ]`；内容已由 025~029 承接 |
| 008-pipeline-ssot-backfill.md | 已完成，1/1 | 史实 | `[x]` 已勾；roadmap M2 / 2.1「已完成」（roadmap「### M2」） |
| 009-dual-repo-merge.md | 已完成，1/1 | 史实 | 同上，roadmap 2.2「已完成」 |
| 010-runtime-ssot-align.md | 已完成，1/1 | 史实 | roadmap 2.3「已完成」 |
| 011-fulltext-ingest.md | 已完成，1/1 | 史实 | roadmap 2.4「已完成」 |
| 012-dual-db-primary-backup.md | 已完成，1/1 | 史实 | roadmap 2.5「已完成」 |
| 013-credential-governance.md | 已完成，1/1 | 史实 | roadmap 2.6「已完成」 |
| 014-rebuildable-verification.md | 已完成，1/1 | 史实 | roadmap 2.7「已完成」；README「可重建验证（hp037/M2.7）…已圆满收口，M2『稳控与可恢复』里程碑完美闭环」 |
| 015-health-triple-probe.md | 已完成，2/2 | 史实 | roadmap 3.1「已完成」；README「健康三态探针（hp030/M3.1）🚀 已回写」 |
| 016-pg-health-frontend.md | 已完成，1/1 | 史实 | roadmap 3.2「已完成」 |
| 017-alert-channel.md | 已完成，1/1 | 史实 | roadmap 3.3「已完成」 |
| 018-orphan-cron-cleanup.md | 已完成，1/1 | 史实 | roadmap 3.4「已完成」 |
| 019-health-report-auto.md | 已完成，1/1 | 史实 | roadmap 3.5「已完成」 |
| 020-collector-harden.md | 已完成，1/1 | 史实 | roadmap 4.1「已完成」 |
| 021-stale-data-reingest.md | 已完成，1/1 | 史实 | roadmap 4.2「已完成」 |
| 022-short-chunk-governance.md | 已完成，1/1 | 史实 | roadmap 4.3「已完成」 |
| 023-relevance-optimize.md | 已完成，1/1 | 史实 | roadmap 4.4「已完成」 |
| 024-ingest-monitor.md | 已完成，1/1 | 史实 | roadmap 4.5「已完成」 |
| 025-mx-integration.md | 已完成，1/1 | 史实 | roadmap 5.1「已完成」 |
| 026-qb-deepen.md | 已完成，1/1 | 史实 | roadmap 5.2「已完成」 |
| 027-xy-integration.md | 已完成，1/1 | 史实 | roadmap 5.3「已完成」 |
| 028-flow-integration.md | 已完成，1/1 | 史实 | roadmap 5.4「已完成」 |
| 029-quality-feedback.md | 已完成，1/1 | 史实 | roadmap 5.5「已完成」 |

**汇总**：hp 29 篇 = 史实 24 篇（001、002、008~029）+ 作废 5 篇（003、004~007）。无「现行」。
> 008~029 在 meta 中的最后改动均为 2026-09-03 02:22:29 的 `chore(plans)` 悬空旧卡引用清理（仅归档标注、非内容推进），方案级「最后实质改动」为 2026-08-16 立项 / 2026-08-17 批准转卡；与 roadmap（meta 2026-08-19，M2~M5 全「已完成」）一致，故判史实。

### 3) 未闭环事项

1. **hp-plan-003**（`docs/projects/hp/plans/003-hp-plan-002.md`）：验收标准为「`[ ] 待定义`」。方案已作废、工作已由真 `hp-plan-002`（`002-merge-close-branches.md`）完成，仅作历史空壳留存。
2. **hp-plan-005**（`docs/projects/hp/plans/005-observability-and-alerting.md`）：3.2「`consolePage.js 渲染 renderPg`（核查确认：后端已合入，前端无 commit，**待办**）」。方案作废后由 `016-pg-health-frontend.md` 承接，roadmap 3.2 记「已完成」→ 已闭环。
3. **hp-plan-004~007 作废收回的「待重构立项」**（`004~007-*.md`）：头部注明「M2/M3/M4/M5 子项目内容待新模型下重新按子项目立项」。已由 008~014 / 015~019 / 020~024 / 025~029 承接且 roadmap 记「已完成」→ 已闭环。
4. **README 未闭环项（陈述滞后）**（`docs/projects/hp/README.md`「## 线路 / 近况」）：「M2-M5 方案已落库（hp-plan-004~007，**状态已确认，待排期**）」与「M6 演进（待定）」——roadmap（2026-08-19）已记 M2~M5「已完成」、M6「待启动（内容待定）」，故该「待排期」表述滞后。M6 演进（多模态知识图谱/高维向量微调/高可用多副本）方向仍**未定**（README「## 线路 / 近况」+ roadmap「### M6」）。
5. **hp009 幽灵卡分支**（`docs/projects/hp/roadmap.md`「## 草案池」）：「`codex/hp009-stock-short-chunk-and-rss-backfill` 未合入 hp main、教训库仍引用——**待裁决**（归 M2 治理或单独处理）」。M1「遗留：hp009 分支未合入 → 转 M2 治理」——M2 已「已完成」，是否已收口**待核**。
6. **README 未闭环项（陈述滞后）**：「向量检索与数据质量（hp006）…下一阶段（hp007）对新入库短 chunk 进行硬拦截」——短 chunk 治理已由 `022-short-chunk-governance.md` 记「已完成」（roadmap 4.3），属陈述滞后。
7. **README 未闭环项（归属待核）**（README「附 C 业务线路梳理」）：「Phase 2 采集器重建（hp004）🚀 已回写（**外仓 main 未含**，在 `codex/hp004-collector-source-expansion` 分支）」「Phase 5 备份对齐（hp003）✅ **已完成并合入（外仓 main 已含）**」「前端治理与合约对齐（hp005）🚀 已回写（外仓 main 未含）」「向量检索与数据质量（hp006）🚀 已回写（外仓 main 未含）」——「外仓 main 未含/已含」口径互相矛盾，且与 roadmap M1~M5 全「已完成」不一致，合入现状**待核**。
8. **delivery 挂账**（`docs/projects/hp/deliveries/hp-delivery-001.md`「## 7. 后续」）：「M2-M5 方案均已验收已完成，交付物在业务仓但未 CCC 侧登记，建议后续合并补 hp-delivery-002（M2-M5 综合）」——**delivery-002 未见检出**（`docs/projects/hp/deliveries/` 仅 hp-delivery-001.md）→ 未闭环；另有「tag v0.1.1 落后 VERSION v0.1.2，**待补 v0.1.2 tag**」。

### 4) 重新纳入判定建议（移植令口径）

| 门槛 | 判定 | 证据 / 说明 |
|---|---|---|
| ① 项目真实存续（近 30 天有实质动静或 owner 明示在做） | 待核（擦边） | 末次实质改动 2026-08-19（delivery-001、roadmap 状态回写，`meta/last-commits.txt`），距盘点日 25 天、落在窗口内；但此后零实质推进（09-03 仅 `chore(plans)` 元数据清理），无现行方案、无 owner 明示在做，M6「内容待定」（`roadmap.md`「### M6」）→ 僵尸风险，判待核 |
| ② 业务仓可达且有有效 git 状态 | 待核 | 业务仓 `/Users/fan/program/apps/hp`（Mac2017 SSOT）+ HP 节点双 clone（`hp-delivery-001.md`「## 4」）；检出内无 git 仓（`git rev-parse` 失败）不可核；且 README 附 C 自陈「外仓 main 未含」hp004/hp005/hp006 三处已回写工作 → 合入状态存疑，判待核 |
| ③ 目标一句话与现状对得上 | ✅ | 目标「中央知识库基础设施 + 教训沉淀平台」（README「## 是什么」）↔ 现状 M1~M5 全部交付、5267 docs 在线、可重建验证闭环（delivery-001 + roadmap）→ 对得上 |
| ④ plans 完成度与 roadmap/看板声称一致 | ✅（看板面待核） | plans 29 篇（24 已完成 + 5 作废）↔ roadmap M1~M5 全「已完成」、M6「待启动」→ 一致；roadmap 草案池 13 条 2026-08-18 Loop 巡查「进度不一致（声明 0/1 实际 1/1）」记录未销账（plan 文件现已 1/1，属当时级联滞后）；看板 UI（192.168.3.116:7788）不可达不可核 |
| ⑤ 卡头规范兼容（plans 关联卡是六态口径即兼容） | 待核 | plan 头字段结构齐全（项目/编号/状态/作者/工具/创建/更新/关联卡/关联方案/进度，如 `014-rebuildable-verification.md` 头部）；但检出内无六态定义文档，plans 自报状态仅出现 4 值（已完成/作废/待验收/部分执行）；关联卡 31 处标「已归档（见 docs/archive 与 RETIRED 记录）」而**检出内无 docs/archive 目录** → 卡状态与六态口径均不可核 |

**综合建议**：🔧**整改后可入**。门槛③④可核且过关，但①②⑤共三处待核构成进入障碍——需补齐：a) owner 明示承接方向 + M6 立项（消①僵尸风险）；b) 业务仓 git 合入核对，尤其 README 附 C「外仓 main 未含」的 hp004/hp005/hp006 三处与 hp009 幽灵分支裁决（消②，兼销未闭环 5/7）；c) 恢复卡归档证据或确认六态口径（消⑤）。未闭环事项 1~4/6 多为陈述滞后与历史空壳，不构成进入障碍；事项 8（delivery-002 缺、v0.1.2 tag 未补）属收口债，建议并入整改项。

---

## mx / medio-0

### 1) 项目目标（出处：`docs/projects/mx/README.md`）

Mac2017 上的**全栈媒体管理应用**：Rust（axum + SQLite/sqlx）后端 + React/TypeScript 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发（README「## 是什么」+「附 A：技术栈」）。

### 2) plans/ 逐篇定级

| plans 文件 | 方案自报 | 定级 | 证据 |
|---|---|---|---|
| 001-rss-polish-milestone.md | 已完成，进度 29/29 | 史实 | 验收 5 项全 `[x]`；roadmap M2/M3/M4 均「已完成」并关联 mx-plan-001（`docs/projects/mx/roadmap.md`「### M2」「### M3」「### M4」） |
| 002-closure-and-security-hardening.md | 已完成，进度 6/6 | 史实 | 验收 5 项全 `[x]`；roadmap M5「已完成 · 版本 v0.9.0」；README「2026-08-12 mx-plan-002 收口与安全加固完成」 |
| 003-base-decoupling-and-arch-upgrade.md | 已完成，进度 6/6 | 史实 | 验收 6 项全 `[x]`；roadmap M6「已完成」关联 mx-plan-003；delivery-003（`mx-delivery-003.md`，meta 2026-08-19） |
| 004-public-migration-and-multitarget-cicd.md | **待验收**，进度 3/3 | **现行（挂账）** | meta 条目 `docs(mx): mx-plan-004 挂老板决策`（2026-08-24）；验收行「**不通过，维持待验收**」，2 项 `- [ ]` 未满足；老板拍板「不做历史重写（影响面过大），鸿蒙开发线冻结」，路线改为新仓无历史路径 → 未闭环、未作废、仍现行。roadmap M7「状态：**待启动**」亦一致 |
| 005-opml-import-fix.md | 已完成，1/1 | 史实 | 验收 3 项全 `[x]`；验收席 DSH 代行，`cargo test --workspace 578` 全绿；roadmap 8.1「已完成」 |
| 006-opml-export-auth.md | 已完成，1/1 | 史实 | 验收 2 项全 `[x]`；验收席 DSH 代行，前端 vitest 381 全绿；roadmap 8.2「已完成」 |
| 007-rss-stats-aggregation.md | 已完成，1/1 | 史实 | 验收 3 项全 `[x]`；roadmap 8.3「已完成」 |
| 008-coverage-expansion.md | 已完成，1/1 | 史实 | 验收 2 项全 `[x]`（「≥80% 当前值未本地复跑 tarpaulin，以 CI 门禁为准」）；roadmap 8.4「已完成」 |
| 009-frontend-holistic-refactor.md | **部分执行** | **现行（进行中）** | 进度「批次 1/2/3 完成…批次 4 待推进」；meta 条目 `mx-plan-009 批次 4 两轮完成回写`（2026-08-24 13:17:39）；「## 验收标准」5 项**全部 `- [ ]` 未勾**（验收记录却记批次 1/2/3/4 已执行）；roadmap 未收录 mx-plan-009 |

**汇总**：mx 9 篇 = 史实 7 篇（001、002、003、005、006、007、008）+ 现行 2 篇（004、009）。无作废。

### 3) 未闭环事项

1. **mx-plan-004**（`docs/projects/mx/plans/004-public-migration-and-multitarget-cicd.md`）：验收 2 项 `- [ ]` 未满足——①「公开仓库可访问，Actions CI/CD 全绿（后端/前端/HarmonyOS 三端）」（仓库仍 private）②「历史敏感 commit（含 `medio.p7b.pem`）已 filter-repo 抹除」（fresh fetch 后 origin/main 仍可达 3 个签名材料 blob）。老板 2026-08-24 拍板不做历史重写、鸿蒙开发线冻结，远端历史残留登记为「已知接受风险」（issues.jsonl wontfix）；Phase 2 敏感清零、LICENSE/README、CI 补齐已落地。**公开化路线待新仓无历史导入路径**。
2. **鸿蒙证书换发独立挂账**（`002-closure-and-security-hardening.md`「## 方案内容」）：鸿蒙签名私钥泄露处置——换证 + `git filter-repo` 历史清洗，「涉及密钥与远端重写，**老板确认后独立执行**」。随 mx-plan-004 拍板不重写历史，本项仍**未闭环**（鸿蒙线冻结）。
3. **mx-plan-009 验收标准未勾**（`009-frontend-holistic-refactor.md`「## 验收标准」）：5 项全部 `- [ ]`——批次 1「HP 生产 CSS 指纹更新；老板真机复测有明确结论」、批次 2「JS 与 CSS 断点一致；真机回归清单全过」、批次 3「主 chunk ≤300KB；vitest 全绿零回归」、批次 4「内联样式较基线下降 ≥50%；页面结构模板化文档落地」、全程「vitest ≥70% 覆盖率门禁不降」。验收记录显示批次 1/2/3/4 已执行，复选框未同步（治理债）。
4. **mx-plan-009 批次 1 待反馈**（同文件「### 批次 1」）：「`[ ]` 老板真机复测遮挡——**待老板反馈**」。
5. **mx-plan-009 批次 2 部署收尾**（同文件「### 批次 2」）：「`[ ]` HP 部署收尾验证」。
6. **mx-plan-009 批次 3 顺延项**（同文件「### 批次 3」）：「bundle 主 chunk 328→**321KB**，≤300KB 目标**顺延批次 4**」「孤儿端点 2 个**待排除多端调用后处理**」。
7. **mx-plan-009 批次 4 余第三轮**（同文件「### 批次 4」）：「Radix 弹层整迁（MetadataEditDialog/TokenPromptDialog/SearchOverlay）、徽章 6 类收敛」——**待推进**。
8. **M7 公开化搬迁与多端 CI/CD「待启动」**（`docs/projects/mx/roadmap.md`「### M7」）：关联 mx-plan-004，时间线「待排期」——与 mx-plan-004 现行/挂账状态一致。
9. **治理债（待核）**（`docs/projects/mx/roadmap.md`「## 草案池」）：2026-08-18「[Loop巡查] mx-plan-005 已完成但**验收标准 3 项未勾选**（033 验收归属：拍板前须勾选）」——现方案文件已 `[x]` 勾选、roadmap 滞后，是否已销账**待核**；另有 mx-plan-004「声明 2/3，实际 3/3」、mx-plan-005「声明 0/1，实际 1/1」、M8「声明进行中，实际完成率 100%」三条进度不一致记录（同为巡查债，**待核**）。
10. **草案池未立项条目**（`docs/projects/mx/roadmap.md`「## 草案池」）：【性能】大媒体库（万级文件）多级预缓存与磁盘 I/O 避让、【移动端】HarmonyOS 极简高保真 UI 与系统层常驻推送、【离线】Tauri/Native 双端离线阅读与增量数据离线保存——均未立项、未排期。
11. **README 未闭环项（陈述滞后）**（`docs/projects/mx/README.md`「## 线路 / 近况」）：「mx-plan-003 底座解耦与中长期架构升级（**待起草**）」（实际已 6/6 完成、roadmap M6「已完成」）、「mx-plan-004：目标转 GitHub Public，前提=清签名私钥历史…**待单独人工确认后推进，不急执行**」（实际已转卡执行并经 2026-08-24 验收）——README 最后改动 2026-08-14 18:25:01，早于 roadmap（2026-08-26），整体滞后于 mx-plan-003~009 实际进度。

### 4) 重新纳入判定建议（移植令口径）

| 门槛 | 判定 | 证据 / 说明 |
|---|---|---|
| ① 项目真实存续（近 30 天有实质动静或 owner 明示在做） | ✅ | 末次实质改动 2026-08-26（roadmap 进度级联回写）、2026-08-24（mx-plan-009 批次 4 回写、mx-plan-004 挂老板决策，`meta/last-commits.txt`），均在窗口内；且有 2 篇现行方案在手（004 挂账、009 进行中）→ 非僵尸。注：距盘点日已 18 天无新实质推进，续存性需持续观察 |
| ② 业务仓可达且有有效 git 状态 | 待核 | 业务仓 `/Users/fan/program/apps/medio-0`（Mac2017，README「## 路径」）；检出内无 git 仓不可核；README 附 C 给出分支合入 main 的 commit hash（`5991b25`/`dc94998`/`6c73e01`）与 `codex/mx002` 待合入、mx-plan-004 验收引用 `git rev-list origin/main` 结果 → 业务仓 git 状态存在且曾被核验，但本检出内无法复核 → 判待核 |
| ③ 目标一句话与现状对得上 | ✅（鸿蒙线张力） | 目标「Mac2017 全栈媒体管理应用：Rust+React+Tauri+HarmonyOS」（README「## 是什么」）↔ 现状 v0.9.0、35 卡全关、M1~M6/M8 已完成（roadmap）→ 大体对得上；但「HarmonyOS 移动端」与老板 2026-08-24 拍板「鸿蒙开发线冻结」（`mx-plan-004.md` 验收注）存在张力，移动端目标现实性需 owner 确认 |
| ④ plans 完成度与 roadmap/看板声称一致 | ❌ | mx-plan-009「部分执行、验收 5 项全未勾」**未被 roadmap 收录**（M1~M8 均无 mx-plan-009，`mx/roadmap.md`）；roadmap 草案池 4 条 Loop 巡查进度不一致治理债（mx-plan-004 声明 2/3 实际 3/3、mx-plan-005 0/1 vs 1/1、M8 声明进行中实际 100%）未销账 → plans 与 roadmap 声称不一致 |
| ⑤ 卡头规范兼容（plans 关联卡是六态口径即兼容） | 待核 | plan 头字段结构齐全；但检出内无六态定义文档，plans 自报状态含「部分执行」（非标准态值？不可核）；mx-plan-009 无卡号（「按批次出卡或直执」，`009-frontend-holistic-refactor.md` 头部）、mx-plan-004 活卡引用 mx045/046/047 但卡状态不可核、其余 7 篇关联卡标「已归档」而检出内无 docs/archive → 六态口径不可核 |

**综合建议**：🔧**整改后可入**。①②③大体成立，但④为硬性 ❌、⑤待核——需补齐：a) mx-plan-009 补录 roadmap（或明确为 roadmap 之外的在飞方案并同步看板），验收 5 项复选框按验收记录勾选销账（消④，兼销未闭环 3~7）；b) 业务仓 git 复核（消②，含 mx004 验收引用的 origin/main 对象核验与 `codex/mx002` 合入）；c) 鸿蒙线冻结与目标张力由 owner 决策（消③注）；d) 卡六态口径与归档证据核认（消⑤）。未闭环 1/2/8（公开化待新仓路径、鸿蒙证书挂账、M7 待排期）为老板既定决策的挂账项，不构成进入障碍；事项 9~11 为治理债与陈述滞后，建议并入整改清单。

---

## 附：跨项目观察

- `docs/projects/hp/README.md`（meta 2026-08-17 05:48:38）与 `docs/projects/mx/README.md`（meta 2026-08-14 18:25:01）均为陈旧叙述，滞后于各自 `roadmap.md`（hp 2026-08-19、mx 2026-08-26）与 plans 实际状态；「现行」判断以 roadmap + plans 自报状态为准，README 仅作对照证据。
- 2026-09-03 02:22:29 `chore(plans)` 批量清理（悬空旧卡引用归档标注）覆盖 hp 001/002/008~029 与 mx 001~003/005~008，属元数据操作，不代表内容推进；据此不能反推「现行」。
- hp 存在唯一「现行」缺口为 M6 演进方向（内容待定，roadmap 草案池）；mx 的现行项为 mx-plan-004（待验收挂账）与 mx-plan-009（前端整体重构，批次 4 第三轮待推进）。
- **移植令五条门槛执行情况（两项目共同项）**：门槛②（业务仓 git 状态）与门槛⑤（卡六态口径）在本次检出内**均不可核**——检出非 git 仓、`docs/archive`/RETIRED 归档目录不在检出内、无六态定义文档；两项目均判「🔧整改后可入」而非「✅合格」，正因这两个系统性待核项。门槛①上 hp 擦边（25 天无实质推进）而 mx 过关（18 天前仍有实质推进 + 现行方案在手）；门槛④ hp 可核部分一致而 mx 因 mx-plan-009 未入 roadmap 判 ❌。
- 两项目的「重新纳入」建议（🔧整改后可入）所需整改项高度同构：owner 承接确认 → 业务仓 git 复核 → 卡归档/六态口径核认；差异仅在 hp 另需 M6 立项方向、mx 另需 mx-plan-009 收口与 roadmap 同步。
