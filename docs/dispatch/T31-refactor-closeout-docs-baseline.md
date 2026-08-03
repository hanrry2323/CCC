# 任务卡 T31 · 重构收口：文档基线切到新架构（版本叙事 + 权威链）（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§1 任务卡 / §9 全局红线）
> 依据：Codex 2026-08-03 全新取证重评——T0–T30 已闭环，但仓内权威文档（CLAUDE.md / STARTUP-BRIEF.md / docs/INDEX.md / docs/roadmap.md / server/ 各 README / pyproject.toml）仍描述旧架构（Hub :7777、scripts/ 热路径、能力包、M1 Desktop+sidecar），部分命令指向已退役路径
> 执行体：Trae · 验收：Codex · 状态：待分派 · 日期：2026-08-03

## 目标

让 CCC 仓内全部现行文档只描述一套事实：2026-08-02 重构定稿的新架构（薄驱动 Engine + 文档流转 + 看板/HTTP + 2017 单端 + 任意设备壳）；旧口径只允许存在于归档区/历史条目。

## 红线（先看）

1. **只改文档与配置**：零改动 server/ 运行代码行为、desktop/ 代码、2017 运行面。
2. 不物理删除：旧文档如需降级，标「史/已归档」并放 docs/archive/，禁止 rm。
3. 不改 qx-map 内容、不读写外脑；提交必须是真实 commit，message 含 T31。
4. 验收标准不可自行解释；拿不准的旧文档保留并标注「待核」，不要擅自扩写新方案。

## 范围

CLAUDE.md、STARTUP-BRIEF.md、VERSION、CHANGELOG.md、docs/INDEX.md、docs/roadmap.md（仅「当前方向」索引节）、docs/architecture.md（架构树）、server/README.md、server/engine/README.md、server/board/README.md、server/web/README.md、pyproject.toml。

## 步骤

1. 通读权威基线：qx-map `__archive__/decisions/ccc-refactor-方案-定稿-2026-08-02.md`（D1–D10）与 `command-post/ccc-refactor-contract-v1-2026-08-02.md`；再读 docs/archive/ccc-legacy-2026-08-02/RETENTION-LIST.md 确认哪些根文档是保留项（CLAUDE.md/STARTUP-BRIEF 是保留项，只允许改内容口径，不允许删文件）。
2. CLAUDE.md：删除对 scripts/、Hub、control.json、能力包、角色分层的现行口径；改为「新架构 + server/ 新栈 + 开发命令指向 server/ 与 pytest server/tests」；开发命令必须真实可执行。
3. STARTUP-BRIEF.md：按终态重写——2017 唯一服务端 :7788、HTTP 直连、账号密码+token、大脑 Agent、看板/运维/线路图视图、Desktop 壳指向 2017。
4. docs/INDEX.md §0：权威链顶部加入「重构决策定稿 + 契约 v1」（最高优先级），旧 loop-engineer-authority.md 等标注「已被重构方案取代（史）」或降级；冲突裁决顺序同步更新。
5. docs/roadmap.md「当前方向」索引节改为重构后方向（P0–P5 完成度 + M1–M4 现状），历史正文不动。
6. VERSION 升为 v0.70.0；CHANGELOG 顶部补「2026-08-02 架构重构」章节（一句话：薄 Engine + 文档流转 + 2017 单端 + HTTP/桌面壳；T0–T30 摘要）。
7. docs/architecture.md 架构树更新：scripts/ 移除（已退役）、server/ 展开、src-tauri 标「历史遗留（待 T34 归档）」。
8. server/ 各 README 与 engine main.py docstring：删「T4 前不真拉执行体」「desktop/ 零改动」「本服务仅只读」等过时句，按 T32 目标写「Engine 负责真实派发/收单」口径（代码实现在 T32，文档口径先到位）。
9. pyproject.toml：删除指向已退役 scripts/*.py 的 per-file-ignores（改为 server/ 相关路径）；确认 ruff 检查范围含 server/（W292 清零在 T35，先保证配置就位不误伤）。
10. 全仓 grep 自检（见验收）后提交。

## 验收标准

1. 全仓 grep（排除 docs/archive/ 与 CHANGELOG 历史条目）零命中旧口径：`scripts/ccc-engine`、`Hub :7777`、`6+1 列`、`能力包`、`M1 Desktop + sidecar`、`角色分层`。
2. CLAUDE.md / STARTUP-BRIEF.md 中出现的每一条命令真实可执行（不存在指向已删路径的命令）。
3. VERSION = v0.70.0 且 CHANGELOG 有对应章节；docs/INDEX.md §0 含重构决策+契约且排序正确。
4. server/ 各 README 无「不真拉/零改动/只读」过时口径。
5. `pytest server/tests -q` 全绿；工作树仅剩许可预存项；真实提交。

## 回写要求

卡头状态更新为「已回写」；回写区填：文档清单与每份的改动一句话、grep 自检输出摘要、pytest 结果、commit hash。

## 回写区

**执行体**：Trae · 日期：

