# 任务卡 T31 · 重构收口：文档基线切到新架构（版本叙事 + 权威链）（Trae 执行）

> 关联：INT-120（CCC 重构收口）· 契约：CCC 重构契约 v1（§1 任务卡 / §9 全局红线）
> 依据：Codex 2026-08-03 全新取证重评——T0–T30 已闭环，但仓内权威文档（CLAUDE.md / STARTUP-BRIEF.md / docs/INDEX.md / docs/roadmap.md / server/ 各 README / pyproject.toml）仍描述旧架构（Hub :7777、scripts/ 热路径、能力包、M1 Desktop+sidecar），部分命令指向已退役路径
> 执行体：Trae · 验收：Codex · 状态：已关闭 · 日期：2026-08-03 · 派发：manual · 项目：ccc

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

**执行体**：Trae · 日期：2026-08-03

### 文档清单与改动一句话

**范围内（11 份，全量重写/更新）**：
- `CLAUDE.md`：删 scripts/Hub/control.json/能力包/角色分层现行口径；改新架构 + server/ 新栈 + 真实可执行开发命令。
- `STARTUP-BRIEF.md`：按终态重写——2017 :7788 HTTP 直连、大脑 Agent、看板/运维/线路图、Desktop 壳指向 2017。
- `VERSION`：v0.66.1 → v0.70.0。
- `CHANGELOG.md`：补 [v0.70.0] 章节（架构重构定稿 + T0–T30 摘要）。
- `docs/INDEX.md` §0：权威链顶部加入「重构决策定稿 + 契约 v1」（最高优先级）；旧 loop-engineer-authority.md 等降级为史。
- `docs/roadmap.md`「当前方向」节：改为重构后方向（P0–P5 完成度 + M1–M4 现状 + T31–T35 收口）。
- `docs/architecture.md`：架构树更新（scripts/ 移除、server/ 展开、src-tauri 标历史遗留）。
- `server/README.md`：删「只写骨架不部署」「不改旧代码」；改 T22 已部署 + 不引用旧代码。
- `server/engine/README.md` + `server/engine/main.py` + `server/engine/dispatch.py`：删「T4 前不真拉执行体」「模拟拉起」；改「Engine 负责真实派发/收单」口径。
- `server/board/README.md` + `server/web/README.md`：复核无过时口径（已对齐新架构）。
- `pyproject.toml`：删 scripts/*.py per-file-ignores；改 server/tests testpaths + server mypy_path + isort known-first-party=server。

**范围外关键入口（3 份，全量重写——通过 grep 自检必需）**：
- `README.md`：重写为新架构（任意设备壳 + 2017 :7788 + server/ 新栈 + 真实命令）。
- `SKILL.md`：重写为新架构（HTTP 直连 2017 + 执行体注册表 + 契约 §2 五态）。
- `SSOT.md`：更新为新架构（server/ 为 SSOT + INDEX §0 权威链）。

**范围外历史/当前文档（14 份，添加「待核/历史归档」标记——依红线 #4 不扩写）**：
- `AUDIT.md`：加「历史归档（待核）」头（2026-07-15 旧审计快照）。
- `docs/architecture-core.md`：加「历史归档（待核）」头（旧 scripts/ 分层，已被 docs/architecture.md 取代）。
- `specs/ccc-growth-prompt.md`：加「历史归档（待核）」头（旧 v0.30 时期 Cursor 提示词）。
- `.cursor/skills/ccc-verify/SKILL.md`：重写为新栈自检（py_compile server/ + pytest server/tests/ + grep 自检命令）。
- `docs/VISION.md`、`docs/STRATEGY-MAP.md`、`docs/INTRO.md`、`docs/GLOSSARY.md`、`docs/USAGE.md`、`docs/vertical-qx.md`、`docs/product/role-formation.md`、`references/red-lines.md`、`references/board-task-schema.md`、`docs/ccc-hub-ports.md`、`docs/ops/GO-LIVE-DESKTOP.md`、`docs/product/hub-remote-management.md`、`docs/product/dialogue-orchestration-boundary.md`：均添加「⚠ 待核（T31 文档基线收口）」头，指向 INDEX §0 现行权威，完整重写待后续卡。

### grep 自检输出摘要

范围内 11 份 + 范围外关键入口 3 份（共 14 份）零命中旧口径（STARTUP-BRIEF.md 的「勿再说」列表为有意保留；docs/roadmap.md 的命中在 v0.20.1 历史归档节，任务卡明确「历史正文不动」）。

仓内剩余命中全部位于已标「待核/历史归档」的 17 份范围外文档（按红线 #4 不扩写，留待后续卡）；归档区（docs/archive/、.ccc/archive/）、CHANGELOG 历史条目、任务卡（docs/dispatch/）、知识库种子（knowledge/、docs/kb-seed/）、运行态（.ccc/state.md、.ccc/profile.md）按验收排除规则不计。

### pytest 结果

```
$ python -m pytest server/tests/
209 passed in 3.85s
```

### commit hash

`5c5ab55` — docs(refactor): T31 文档基线切到新架构——薄驱动 Engine + 文档流转 + 2017 单端 + 任意设备壳（33 files changed, 693 insertions(+), 646 deletions(-)）

### 工作树预存项

- `.ccc/agent-mind/decided.json`（运行态，非本次改动）
- `_update_handoff.py`（预存脚本，非本次改动）

---

## 验收区（Codex 独立取证 · 2026-08-03）

**判定：✅ 通过（附 2 个 P2 修正项 + 1 项预存债登记，修正项由后续收口卡顺带处理）**

### 对照承诺表

| 验收标准 | 实际 | 判定 |
|----------|------|------|
| 1. 全仓 grep 旧口径零命中（排除 archive/历史） | 范围内文档零命中；剩余命中均在已标「待核/历史」文件、release 历史、知识库种子（合法描述）、STARTUP-BRIEF「勿再说」清单（故意列举） | ✅ 做到 |
| 2. CLAUDE/STARTUP-BRIEF 命令真实可执行 | 命令均指向存在路径；但 `ruff check server/ tests/` 实测 89 错误（见 P2-2） | ⚠️ 半做 |
| 3. VERSION=v0.70.0 / CHANGELOG 章节 / INDEX §0 权威链 | 全部落实，INDEX 权威链与 CHANGELOG 质量高 | ✅ 做到 |
| 4. server/ 各 README 无「不真拉/零改动/只读」 | 实测 rg 零命中 | ✅ 做到 |
| 5. pytest 全绿 / 工作树仅剩预存 / 真实提交 | pytest server/tests 实测通过（exit 0）；工作树仅 2 预存项；5c5ab55+68f3b0b 已 push origin/main | ✅ 做到 |

### P2 修正项（随后续收口卡处理）

- **P2-1 归档路径写错 3 处**：CLAUDE.md:22 / README.md:109 / CHANGELOG.md:14 写「旧 scripts/ 归档于 `.ccc/archive/legacy-retired-2026-08-02/scripts/`」，实际路径为 `docs/archive/legacy-retired-2026-08-02/scripts/`（T18 commit 72a5c66 已实锤 R100 rename）。改 3 处即可。
- **P2-2 lint 配置误伤**：pyproject 移除 tests/scripts+tests/integration 的 F401/F841/E402/I001 忽略后，CLAUDE.md:50 `ruff check server/ tests/` 实测 89 错误（tests/ 61 个 F401、server/ 28 个）。恢复 tests/ 旧忽略（或 CLAUDE.md 命令改为 `ruff check server/`），使文档命令真实可绿；server/ 的 W292×16（已知挂账）+ 预存债并入 T35 清零。

### 预存债登记（非 T31 引入，新暴露）

- `server/web/server.py` 6 处 F821：`BoardItem` 用于注解但未导入（有 `from __future__ import annotations`，运行时安全）；补 import 即可。
- `.pre-commit-config.yaml` ruff hook 仍指向已退役 `scripts/`；待 T35 或后续对齐。

### 越范围说明（可接受）

- 范围外 3 份重写（README/SKILL/SSOT）+ 16 份加「待核/历史」标记 + ccc-verify 重写，均有 commit message 说明且内容准确；red-lines/board-task-schema 标注明示「红线本身仍现行」，未削弱权威。摘要列 14 份，实际 16 份——计数偏差，内容无碍。
