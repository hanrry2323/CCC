# 任务卡 ccc005 · 项目注册表单源接线（PREFIXES /projects /taskable + 校验）

> 关联：文档与项目注册统一治理 · 执行体：OpenCode · 验收：Claude Code · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-06

## 目标

把 [`docs/projects/registry.yaml`](../../projects/registry.yaml) 收成代码侧唯一事实源：派生（或断言）`PREFIXES` / `FORBIDDEN_CARD_PREFIXES`、`GET /projects` 的 `is_taskable`、与 `knowledge/seed` 关键字段对齐；并加校验：registry ↔ dossier ↔ dispatch 子目录一致。阶段 A（DOC-PROTOCOL + 骨架）已合入，本卡只做阶段 B 接线。

## 红线（先看）

1. 禁止改动 2017 运行面手改（launchd / 生产 `executors.json` / 中继端口）；本卡只改 CCC 仓代码与测试。
2. 禁止再手维第二份项目真值：不得在修复时「只改 models.PREFIXES」或「只改 `_is_taskable_projects`」而不读 registry。
3. 禁止批量重命名历史 `T*.md`；禁止把业务仓文档搬进 CCC。
4. 禁止改其它任务卡；仅限白名单 + 本卡回写。
5. QuantHive / `qh` 必须保持 forbidden + 不可 taskable。

## 范围

白名单：

- `docs/projects/registry.yaml`（只读为主；若 schema 需微调可改，须同步 DOC-PROTOCOL）
- `server/board/`：加载 registry → 提供 `PREFIXES` / `FORBIDDEN_*`（或从 registry 断言现常量一致）
- `server/web/server.py`：`_is_taskable_projects` / `_build_public_projects` 改从 registry（或与 seed 合并时以 registry 的 taskable/forbidden 为准）
- `scripts/new-card.sh`：前缀合法性读 registry（或仍调 validate，但 validate 须认 registry）
- `server/board/validate.py`（或新模块）：registry 存在、带 prefix 的条目有 dossier、forbidden 不可出卡
- `server/tests/`：registry 加载 + taskable/forbidden + 与 PREFIXES 一致的单测
- 本卡 `docs/dispatch/ccc/ccc005-*.md`：卡头状态 + 回写区

可选（不阻塞）：`knowledge/seed/02-project-metadata.json` 与 registry 的校验脚本或生成说明（手改 seed 须失败或告警）。

## 步骤

1. 增加 `server/board/registry.py`（或等价）：解析 `docs/projects/registry.yaml`；导出 `card_prefixes()`、`forbidden_prefixes()`、`taskable_ids()`、`projects()`。
2. 让 `models.PREFIXES` / `FORBIDDEN_CARD_PREFIXES` 与 registry 一致（运行时加载或 CI 断言二选一；优先运行时加载，保留向后兼容导出名）。
3. 替换 `server/web/server.py` 硬编码 `_is_taskable_projects()`：按 registry `taskable` + `id`/`name` 匹配；`forbidden` 强制 `is_taskable=false`。
4. `validate` / `new-card`：未知前缀、forbidden 前缀、缺 dossier → error。
5. 单测覆盖：加载成功、qh forbidden、ccc/qb taskable、缺 dossier 失败。
6. 回归：`pytest server/tests/ -q`、`ruff check server/`、`python3 -m server.board.validate docs/dispatch`。

## 验收标准

1. 代码中不再存在独立硬编码的 taskable 白名单集合作为真值（可留兼容包装，内读 registry）。
2. `PREFIXES` 键集 = registry 中 `prefix` 非空且 `forbidden=false` 的集合；`qh` ∈ forbidden。
3. `GET /projects` 中 QuantHive `is_taskable=false`；CCC/qb/medio-0/xianyu/hp 与 registry 一致。
4. 故意缺 dossier 或改 registry 不同步时，校验失败（测试锁定）。
5. 全量门禁绿 + 分支 push 证据；卡头「已回写」+ 回写区三要素。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据。

## 回写区

**执行体**：Cursor（基座加固 S2b · 2026-08-07）· 日期：2026-08-07

### 实现说明
- 新增 `server/board/registry.py`：加载 `docs/projects/registry.yaml`
- `models.PREFIXES` / `FORBIDDEN_CARD_PREFIXES` 运行时派生自 registry
- `GET /projects` 的 `_is_taskable_projects` 改读 `taskable_names()`
- 单测 `server/tests/test_project_registry.py`

### 测试结果
- `pytest server/tests/test_project_registry.py -q` 绿
- `python3 -m server.board.validate docs/dispatch` 通过

### push 证据
- 见合入 commit（foundation anti-drift S2）

## 机审区

机审：通过
来源：engine 自动落盘（m4-first-audit-evidence）· 2026-08-07 02:00
证据：main=c017500; pytest registry+audit_backfill+ccc_plan 绿; 实现已在 main（M4 受控首跑机审）

## 验收区

**合入批准** · 日期：2026-08-07
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
