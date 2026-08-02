# 任务卡 T5 · 看板产物定时化 + Engine 定时驱动起点（D4）

> 关联：INT-120（CCC 重构）· 契约：CCC 重构契约 v1（D4 定时任务 / §4 看板）
> 管理席：Claude Code（调度窗口）· 执行体：Trae · 验收：Codex + Claude Code 双验证
> 状态：待分派 · 日期：2026-08-02
> 前置：T3（已验收通过）；解决 T3 遗留 3（board.js 重导出定时化）

## 目标

把手工 `python3 -m server.board.export` 变成**定时任务**（任务卡变更后自动重导出 `web/data/board.js`），并为 D4「Engine 承担定时任务」铺路：定时巡检**默认只读**，变更类走正常任务卡并保留确认。

## 红线（先看）

1. 不碰旧代码（`scripts/`、`app/`、`desktop/`、`lib/`、`db/` 零改动）；不碰运行面；不读不写 qx-map / 外脑。
2. **定时任务默认只读**：重导出只写 `server/web/data/board.js`，不产生任何业务动作/派发。
3. 只改 `server/`（board/engine 相关）与部署配置；验收标准不可自行解释；完成必须提交。
4. 工作树只允许预存 2 个无关改动（`scripts/.ccc/agent-mind/decided.json`、`_update_handoff.py`）。

## 范围

- `server/`：新增看板定时重导出入口（或复用 engine 定时框架，见 D4）。
- 部署：launchd / cron 配置模板（沿用 CCC 现有进程管理惯例）。
- **不动**：`server/board/` 数据模型、`server/web/` 页面、`server/relay/`、2017 中转站（T4）。

## 步骤

1. 新增看板定时重导出脚本/entry：扫描 `docs/dispatch/` → 聚合 → 写 `web/data/board.js`（复用 T3 `board.export`）。
2. 定时调度：launchd（或 engine 内定时），按需频率（任务卡变更后 / 每日）；默认只读。
3. 失败处理：重导出失败**保留旧 board.js** + 记日志，不中断、不产生脏数据。
4. 测试：定时入口冒烟（一次 + 定时两种模式）+ 既有 67 用例不回归；硬编码扫描零字面量。
5. 提交 `chore(board):`，回写真实 commit hash。

## 验收标准（Codex + Claude Code 按此验收）

1. 定时重导出可独立运行（`--once` 一次 + 定时两种模式）。
2. board.js 在任务卡变更后自动更新；失败时旧版保留 + 日志。
3. 既有 67 用例不回归；硬编码扫描零字面量；提交真实。
4. 定时默认只读，无业务动作、不派发任务。

## 回写要求

结果摘要（人话一句）、测试输出、定时验证输出、commit hash、验收自检对照表。

## 回写区

（Trae 回写）
