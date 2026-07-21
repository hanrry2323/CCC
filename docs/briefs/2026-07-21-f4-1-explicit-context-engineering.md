# Brief F4-1 · 显式 Context Engineering

| 字段 | 值 |
|------|-----|
| brief_id | `F4-20260721-explicit-context-engineering` |
| 波次 | F4 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | 流畅基线已达成 |
| 模型提示 | **编排窗用高级模型**（涉及角色 prompt 重构 + 边界） |

## 1. 目标

把各角色 prompt 的「该看什么」从**每角色 ad-hoc 拼装**升级为**显式 manifest 驱动**：每阶段声明它需要的 context 项（profile / baseline / SKILL / ref_plans / recent_lessons / current_epic / verdict 等），由统一 helper 按声明注入。让「信息分配」可审计、可复用、可压缩。

## 2. 非目标

- 不改角色职责边界（红线 6 不动）  
- 不改 transfer/flow 契约  
- 不改 Desktop / SSE  
- 不引入向量库 / RAG（文件 manifest 即可）  
- 不强制所有角色一次性迁移（先 product / dev / reviewer；tester / kb / ops / regress 标记 TODO）  
- 不改 Engine 主循环调度  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| flow-events | 无 | |
| hub-api-v1 | 无 | |
| 其它 docs | **有** | 新 `docs/product/context-manifest.md`（SSOT）；`architecture-core.md` 加一行链 |

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| `board/context.py`（workspace ctx） | 无 per-role context manifest |
| product.py 拼 SKILL + profile + baseline + code_ctx + ref_plans + recent_lessons | 拼装逻辑埋在 `_build_prompt`，不可复用、不可审计 |
| reviewer.py / dev.py 各自拼装 | 同上；每角色重复实现 |
| `_lessons.get_recent_lessons` | 注入逻辑分散 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/board/context.py`（加 `build_role_context(role, task) -> dict` + per-role manifest）· `scripts/board/roles/product.py` · `scripts/board/roles/dev.py` · `scripts/board/roles/reviewer.py`（改用 helper；tester/kb/ops/regress 标 TODO 不强制改）· `tests/scripts/test_context_manifest.py`（新）· `docs/product/context-manifest.md`（新）· `docs/architecture-core.md`（加一行链）· 本 brief §8 | 改 Engine 主循环、改 SSE、改 Desktop、改 transfer/flow、改角色职责 |
| 过桥 / 壳 | 否 | — | |
| 架构 | 验收 | 本 brief · `context-manifest.md` 审阅 | 代写实现 |

## 6. 行为规格

1. 在 `board/context.py` 加 `ROLE_CONTEXT_MANIFEST: dict[str, list[str]]`，每角色声明所需 context 项（字符串 key，如 `profile` / `baseline` / `skill` / `ref_plans` / `recent_lessons` / `current_epic` / `verdict` / `phases`）。  
2. 加 `build_role_context(role: str, task: dict | None = None) -> dict[str, str]`：按 manifest 收集各项内容（复用既有 `_load_product_skill` / `collect_baseline` / `get_recent_lessons` 等），返回 `{"profile": "...", "skill": "...", ...}`。  
3. product / dev / reviewer 改为：`ctx = build_role_context("product", task)` → 在 prompt 模板里插 `ctx["profile"]` 等；保留既有过滤（stub lessons 过滤等）。  
4. tester / kb / ops / regress：在文件顶部加 `# TODO F4-1: migrate to build_role_context` 注释，不强制改。  
5. manifest 项可声明为 `"optional"`（缺则空串，不报错）。  
6. 不引入新依赖；不破坏既有 prompt 输出（product 产 plan/phases 格式不变）。  
7. `docs/product/context-manifest.md`：列 manifest 项定义 + 每角色声明表 + 「如何加新项」说明。  

## 7. 验收清单

- [x] `docs/product/context-manifest.md` 落地（manifest 项 + 每角色声明 + 扩展指南）
- [x] `board/context.py` 加 `ROLE_CONTEXT_MANIFEST` + `build_role_context`
- [x] product / dev / reviewer 改用 `build_role_context`；既有输出不变
- [x] tester / kb / ops / regress 加 TODO 注释
- [x] `tests/scripts/test_context_manifest.py` 绿（断言每角色 manifest 含必需项；build_role_context 返回结构正确）
- [x] `pytest tests/scripts/ -q` 仍绿
- [x] 白名单外无改动

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 编排 | `ROLE_CONTEXT_MANIFEST` + `build_role_context`；product/dev/reviewer 改用；tester/kb/ops/regress TODO；`context-manifest.md` + architecture-core 链；`test_context_manifest.py` | `pytest tests/scripts/ -q` 绿；py_compile 绿 | 是 |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | （待填） |
| 缺口 | |
| 验收日 | |
