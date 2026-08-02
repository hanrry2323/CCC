# 任务书 J · 看板 + 运维交互优化（窗口 2）

> 本文件是给 Claude Code 的整段指令，复制全部内容到窗口 2 即可。  
> 依据：`docs/dispatch/2026-08-01-http-chat-optimization-review.md` 第一批「看板/运维」部分。

## 0. 先读

1. `CLAUDE.md`
2. `docs/dispatch/2026-08-01-http-chat-optimization-review.md`
3. 现有实现：`frontend/js/pages/boardPage.js`、`opsPage.js`、`boardSigs.js`、`opsSelectors.js`
4. `docs/dispatch/2026-08-01-squad-dispatch-plan.md`（硬规则必须遵守）

## 1. 任务目标

1. **看板筛选/排序 UI**：状态/关键词筛选 + 排序控件（A2 已有底层透传与测试锁，补页面入口）；不破坏 ←/→ 移卡与 epic 进度刷新
2. **轮询竞态**：15s 轮询与移卡操作冲突 → 移卡 in-flight 期间挂起重绘（或请求序列化），消除闪回/旧 from 404
3. **运维「只看红灯」**：聚合视图/筛选开关——只显示告警与红灯项；保持既有各域渲染与降级行为
4. **测试**：行为测试 + 结构锁（沿用 `scripts/tests/test_web_*` 基建）

## 2. 允许范围

- `scripts/chat_server/frontend/` 下看板/运维域：`js/pages/boardPage.js`、`opsPage.js`、`boardSigs.js`、`opsSelectors.js`、相关 CSS（shell.css / components.css 的 board/ops 区块）、对应测试

## 3. 红线（禁止）

- **chat 域不动**（窗口 1 的活）；后端零改动
- 4000/4100 relay 相关、DRY_RUN、产线启动
- 不破坏 Desktop/sidecar 链路；不删文件（除非计划说明）；提交 main 禁止

## 4. 流程（spec-first 门）

第一轮：`/plan` 输出「三项设计 + 涉及文件清单（明确不与窗口 1 重叠）+ 测试方案」，**不写代码**。  
确认后实现，测试全绿再提交。

## 5. 验收标准

- 筛选/排序入口可用（有测试）；移卡/进度不回归
- 轮询与移卡竞态有锁（快速操作不闪回，有测试或结构锁）
- 「只看红灯」聚合可用，各域降级行为不变
- 提交在 `codex/ws-8-board-ops` 分支

## 6. 完成报告格式

发现 → 动作 → 证据 → 移交项
