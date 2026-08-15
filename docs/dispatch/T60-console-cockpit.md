# 任务卡 T60 · T-B3 控制台驾驶舱对齐统一组件（Claude Code 执行）

> 关联：ccc-plan-001· 执行体：Claude Code · 验收：Codex · 状态：已关闭 · 派发：engine · 项目：ccc · 日期：2026-08-05
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t60-console-cockpit`（先 `git fetch origin main && git checkout -b codex/t60-console-cockpit origin/main`）
> **分步提交纪律（硬）**：每块完成立即 commit+push；超时 7200s。与 T61 并行，文件所有权见下。

## 目标

控制台 = 驾驶舱：状态计数（真实）+ 需注意清单（打回/执行中/待验收）+ 后台任务进程面板（T53 已有），全部对齐 T56 统一组件（TaskCard/TaskCardList），去重看板。

## 具体项

1. 状态计数接 cardApi（/cards 聚合或 /board/states），真实状态（无假执行中）。
2. 需注意清单：打回 / 执行中 / 已回写待验收，每类 ≤10 条，复用 TaskCard/TaskCardList（点击进看板详情）；「去看板看全部」入口。
3. 后台任务进程面板（T53）保留并统一样式（TaskCard 风格 + 已用时/日志尾/进度指示）。
4. 删除控制台旧的自拼 DOM 渲染（与看板重复的部分）。
5. headless 实测：计数真实、清单正确、空态/加载态、零 console error。

## 红线

1. 只改 server/web/legacy-chat/（js/pages/consolePage.js、js/components/、css/）+ tests；**禁止改 boardPanel.js/app.js（T61 所有权）**。
2. 复用 T56 组件，禁止再拼 DOM；与桌面端 StateTone 色板一致。
3. 回写前 push 成功并附证据。

## 验收标准

1. 控制台三区块（计数/注意清单/后台进程）全用统一组件；无假执行中；注意清单 ≤10/类。
2. headless：计数与 /board/states 一致、清单点进看板、空态正常、零 console error。
3. pytest 全绿（如涉）、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、headless 实测、旧渲染清零清单、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：


---

## 验收区（Codex 独立取证 · 2026-08-05）

**判定：✅ 通过。** 控制台驾驶舱（计数/注意清单/后台进程）对齐 TaskCard 组件（c7d6c54c，pytest 全绿）。

> 复盘（T67 · 2026-08-05）：T60 验收后卡头未同步「已关闭」，部署窗口被 Engine 当新卡重新拉起（误派）。T67 三条防线：卡头纪律校验（验收区+状态一致性）、Engine 验收区预检不派发、放行窗口先停 Engine 再 checkout。

## 机审区

**机审：通过**
- 说明：历史卡，无存档证据，按看板已关闭态标注

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]
   - 说明：历史卡，无需额外同步方案状态。
2. **教训沉淀**：本卡是否产出可复用教训？[无]
   - 说明：历史归档，未记录额外复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]
   - 说明：历史完成，未改变项目架构。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：历史结束，不涉及线路图更新。
