# XY 项目「待验收」方案证据分级 · 2026-08-22

> 审计员：CCC 验收证据审计 · 只读审计，未改动任何源码/方案/派发文件
> 项目位置：2017 生产机 `/Users/fan/program/apps/xianyu`（SSH fan@192.168.3.116）
> CCC 仓：`/Users/fan/program/CCC`
> 方法：`git reflog refs/heads/main` 合入事件 + `git merge-base --is-ancestor <commit> origin/main` + `git cherry origin/main <commit>`（patch 等效）+ `git ls-tree/git grep` 交付物文件在 main 树存在性 + 派发文件验收区/债务清理标注。

## 0. 现状勘误：当前无字面「待验收」方案

- 状态枚举（`/Users/fan/program/CCC/server/board/plans.py` `VALID_STATES`）：已确定/待排期/部分执行/**待验收**/已完成/作废/已覆盖。
- 按看板权威（`list_plans`）：**001-007 = 已完成 · 009 = 执行中 · 008/010 = 待排期**。没有任何方案处于字面「待验收」。
- **但**：001-007 全部**无「老板验收拍板」批准行**（`> 批准：老板确认转卡` 是转卡批准，非验收拍板；001 甚至无批准行）。按状态机（033 M4：部分执行→待验收→老板/验收席拍板→已完成），这批方案**跳过了验收拍板直接标已完成**，实质处于「待验收」语义。009 卡已全关但状态仍「执行中」（未推进到待验收）。
- 因此本审计覆盖：**001-007（已完成但缺验收拍板）+ 009（卡全关未推进）**；008/010 无卡不适用。

## 1. 逐方案证据表

| 方案 | 标题 | 关联卡 | 卡状态 | 分支合入main? | 交付报告? | 功能可复现证据 | 档位(A/B/C) | 缺什么 |
|------|------|--------|--------|--------------|-----------|----------------|-------------|--------|
| xy-plan-001 | 视频里程碑推进（M1） | xy001-023, xy025-032（31卡，xy024不在方案） | 31/31 已关闭 | **仅 12/31 确认在 main**（xy002,xy012,xy014,xy015,xy017-023,xy032）；**19/31 代码不在 main** | ✅ xy-delivery-001.md（08-19，引用本方案） | `video-pipeline/` 框架在 main；pytest 65 测试文件；CLI `xianyu`(run/agent/worker/health/status/thumbnail)。但 video-script CLI、cookie_collector、build_plugin.sh、pexels、karaoke、channels 桥接、encoding progress、recon HTML **不在 main** → M1 交付物不可从 main 完整复现 | **C** | 老板验收拍板；19 卡代码合入 main 的证据；交付报告与 git 现状不符 |
| xy-plan-002 | 测试基线绿（M2-2.1） | xy033-036 | 4/4 已关闭 | ✅ xy034/035/036 已合入（reflog 08-17）；xy033 环境卡（chromium 补装，无代码） | ❌ 无 | pytest 套件在 main（65 测试文件） | **A** | 交付报告；老板验收拍板 |
| xy-plan-003 | 断裂点修复（M2-2.2） | xy037-039 | 3/3 已关闭 | ✅ xy037/038/039 全部合入（reflog 08-17） | ❌ 无 | pytest 套件 | **A** | 交付报告；老板验收拍板 |
| xy-plan-004 | 运行方式重建（M2-2.3） | xy049-051 | 3/3 已关闭 | ✅ xy049/050/051 全部合入（reflog 08-17） | ❌ 无 | pytest 套件 | **A** | 交付报告；老板验收拍板 |
| xy-plan-005 | 视觉模板库（M3-3.1） | xy040-042 | 3/3 已关闭 | ✅ xy040/041/042 全部合入（reflog 08-17） | ❌ 无 | pytest 套件 | **A** | 交付报告；老板验收拍板 |
| xy-plan-006 | 质量量化加固（M3-3.2） | xy043-045 | 3/3 已关闭 | ✅ xy043/044/045 全部合入（reflog 08-17） | ❌ 无 | pytest 套件 + `scripts/check_video_quality.py` | **A** | 交付报告；老板验收拍板 |
| xy-plan-007 | 渲染引擎升级（M3-3.3） | xy046-048 | 3/3 已关闭 | ✅ xy046/047/048 全部合入（reflog 08-17） | ❌ 无 | pytest 套件 + hyperframes 渲染器在 main | **A** | 交付报告；老板验收拍板 |
| xy-plan-009 | 前端展示台（M6） | xy052,xy053,xy054,xy055 | 4/4 已关闭 | ✅ xy052/053/054/055 全部合入（reflog 08-20/21） | ❌ 无 | pytest 套件 + admin 页面/API 在 main | **A**（按三判据） | 交付报告；**方案状态仍「执行中」未推进到待验收/已完成**；验收拍板 |
| xy-plan-008 | 视频高表现力二期（M5） | （待出） | — | — | — | — | N/A | 未转卡 |
| xy-plan-010 | 发布闭环（M7） | （待出） | — | — | — | — | N/A | 未转卡 |

## 2. C 档明细：xy-plan-001 未合入 main 的 19 张卡

### 2a. 显式标注「未合入」的 7 张卡（派发文件含：2026-08-16 债务清理（老板定「不确定的全砍」）：本卡代码**未合入业务 main**，悬空分支已删——卡保持已关闭留痕，工作未并入主线）

| 卡 | 标题 | 证据 |
|----|------|------|
| xy025 | 成片质量验收联测（P0-MEDIA） | commit 26477c6 悬空；卡内标注未合入 |
| xy026 | 测试门禁修复（P0-FLOW 前置） | commit 1f764da 悬空；卡内标注未合入 |
| xy027 | xianyu 里程碑推进：环境恢复+HyperFrames 样片 | 分支 codex/xy027 被 87af075 删；卡内标注未合入 |
| xy028 | 修复 pytest 3 个失败用例 | commit b87cc94 悬空；卡内标注未合入 |
| xy029 | 清理文档中过期工具引用 | commit df67495 悬空；卡内标注未合入 |
| xy030 | video encoding progress log | commit 79c192d 悬空；卡内标注未合入 |
| xy031 | config path resolution fix | commit 43aaec2 悬空；卡内标注未合入 |

### 2b. 标「合入批准」但 commit 悬空、未验证进 main 的 12 张卡（git cherry 判 NOT-IN-MAIN）

| 卡 | 标题 | 现状核实 |
|----|------|---------|
| xy001 | 一键生成短视频脚本命令 | CLI `video-script` 不在 main（main 仅有 run/agent/worker/health/status/thumbnail）；`video_script.py` prompt 模块在，但命令未接入 |
| xy003 | 接入 2pass VBR 编码到生产链路 | `encoding.py` 有 VBR_2PASS 模式（来自 xy002 已合入），但本卡「接入生产」改动（7951c32）未合入 |
| xy004 | 修复语音闪避(ducking) | `bgm.py` ducking 为卡前 work（fe8925b）已有；本卡修复（c5710d5）未合入 |
| xy005 | 重构 BGM 自动混音与音量标准化 | `bgm.py` loudnorm 为卡前 work 已有；本卡改动（d66e961）未合入 |
| xy006 | 快手/视频号发布通道 | `sau_bridge.py` 无 `channels` 映射（仅 kuaishou:4）；56a6262 未合入 |
| xy007 | B 站/头条 Cookie 扫码抓取 | `scripts/cookie_collector.py` **不在 main**；eb0d3b5 未合入 |
| xy008 | 自动构建 openclaw-plugin | `scripts/build_plugin.sh` **不在 main**；320a9a9 未合入 |
| xy009 | Pexels/Pixabay 素材下载 | pexels 仅见于历史文档，源码**无** |
| xy010 | 全链路高码率 CRF 编码 | 高码率 CRF-5 由直提 main 的 73854f5 实现（未带卡号）；本卡分支 commit 49a0980 未合入 |
| xy011 | 卡拉OK高亮 ASS 字幕 | karaoke **不在 main**；a221df2 未合入 |
| xy013 | Hyperframes 玻璃模板 | 分支 backup-xy013 被 87af075 删；9a6f6e9 未合入（后续 M3 xy047 重新实现了 hyperframes 渲染） |
| xy016 | 视频链路摸底与架构图 HTML | recon HTML **不在 main**；0ebe597 未合入 |

> 注：2b 中 xy004/005/010/003 的功能在 main 有**等价物**（卡前 work 或直提 main），但卡的特定改动未合入，故不能凭卡标「合入批准」认定代码在 main。

## 3. 系统性发现

1. **验收拍板缺失（全方案）**：001-007 全部「已完成」但无「老板验收拍板」批准行——状态机要求 待验收→拍板→已完成，本批跳过了验收门。009 卡全关但方案状态未推进。
2. **plan-001 交付报告与 git 现状不符**：`xy-delivery-001.md`（08-19）声称「31 卡全部关闭、M1 完成即生产就绪」，但 19/31 卡代码不在 main，其中 7 卡在 08-16 债务清理中已被老板下令砍掉。交付报告未反映代码未合入的事实。
3. **plan 001 早期卡（xy001-011 等）合入流程断裂**：卡标「合入批准 08-12」但 main reflog 无对应 merge 事件、commit 悬空、`git cherry` 判无等效补丁——合入批准与代码落 main 脱节。
4. **plan 002-009 合入健康**：全部走「codex/<卡> 分支 → rebase → fast-forward 合入 main → 删分支」，代码确认在 main。档位 A 但均缺交付报告与验收拍板（交付报告 Gate P1-2 仅对 001 有，002-009 均为存量方案未追溯）。

## 4. 统计

- 待验收方案数（含 009 语义）：**9**（001-007 + 009；008/010 无卡不计）
- A 档：**7**（002,003,004,005,006,007,009）
- B 档：**0**
- C 档：**1**（001）
- 未评估（N/A）：2（008,010 待排期无卡）
