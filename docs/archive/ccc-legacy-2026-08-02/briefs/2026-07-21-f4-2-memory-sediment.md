# Brief F4-2 · Memory 沉淀（成功 lessons + 主题注入）

| 字段 | 值 |
|------|-----|
| brief_id | `F4-20260721-memory-sediment` |
| 波次 | F4 |
| 状态 | `accepted` |
| 定稿人 | 架构 |
| 日期 | 2026-07-21 |
| 依赖 | F4-1（build_role_context）已合入 |
| 模型提示 | **编排窗用 Auto**（既有 `_lessons.py` 扩展，边界清楚） |

## 1. 目标

把 Memory 从「只记失败」扩到「也记成功 + 按主题沉淀」：kb 角色在归档时产 `lessons/<topic>.md`（人可读 + 机可注入）；product 角色按当前 epic 主题匹配注入相关 lessons。让「反复验证过的经验」跨任务复用。

## 2. 非目标

- 不引入向量库 / 语义检索（文件名 + 简单关键词匹配即可）  
- 不改失败 lessons 既有路径（`_lessons.record_failure` 不动）  
- 不改 transfer/flow 契约  
- 不改 Desktop / SSE  
- 不强制所有 epic 都产 lesson（kb 按门禁判断）  

## 3. 契约变更

| 项 | 有无 | 说明 |
|----|------|------|
| flow-events | 无 | |
| 其它 docs | **有** | `docs/product/context-manifest.md` 加 `success_lessons` 项；`docs/architecture-core.md` 已有链 |

## 4. 现状与缺口

| 已有 | 缺口 |
|------|------|
| `_lessons.record_failure` / `get_recent_lessons`（v0.31） | 只记失败；成功经验不沉淀 |
| product 注入 recent lessons（stub 过滤） | 无主题匹配；无成功 lessons |
| kb 角色归档 + tag + CHANGELOG | 不产 lessons 文件 |

## 5. 分工白名单

| 面 | 参与 | 路径 | 禁止 |
|----|------|------|------|
| **编排** | **是（主责）** | `scripts/_lessons.py`（加 `record_success(ws, task_id, topic, summary)` + `get_lessons_by_topic(ws, topic)`）· `scripts/board/roles/kb.py`（归档时调 `record_success`，topic 从 epic title 关键词或 tag）· `scripts/board/roles/product.py`（注入时调 `get_lessons_by_topic`，topic 从当前 task title 提取）· `tests/scripts/test_lessons_success.py`（新）· `docs/product/context-manifest.md`（加 `success_lessons` 项）· 本 brief §8 | 改 Engine 主循环、改 SSE、改 Desktop、改 transfer/flow、改失败 lessons 路径 |
| 过桥 / 壳 | 否 | — | |
| 架构 | 验收 | 本 brief | 代写实现 |

## 6. 行为规格

1. `_lessons.record_success(ws_path, task_id, topic, summary)`：写 `.ccc/lessons/<topic>.md`（人可读 markdown：含 task_id / topic / summary / timestamp）；同名 topic 追加段。  
2. `_lessons.get_lessons_by_topic(ws_path, topic, count=5) -> list[dict]`：按文件名 / 段落关键词匹配；返回最近 count 条。  
3. kb 角色在归档 released 时：从 epic title 提取主题词（如「断线恢复」「投递三态」）或用 tag；调 `record_success`。失败 epic 不记 success。  
4. product 角色在 `_build_prompt` 里：从当前 task title 提取主题词；调 `get_lessons_by_topic`；注入「## 同主题经验」段（在 recent lessons 之后）。  
5. 主题词提取：简单关键词匹配（如 title 含「断线」→ topic="disconnect"）；不做 NLP。  
6. 不破坏既有 `get_recent_lessons`（失败 lessons 路径保留）。  
7. `context-manifest.md` 加 `success_lessons` 项定义。  

## 7. 验收清单

- [x] `_lessons.record_success` + `get_lessons_by_topic` 实现
- [x] kb 归档时调 `record_success`（失败 epic 不调）
- [x] product 注入 `get_lessons_by_topic` 结果
- [x] `context-manifest.md` 加 `success_lessons` 项
- [x] `tests/scripts/test_lessons_success.py` 绿（record → read → topic match）
- [x] `pytest tests/scripts/ -q` 仍绿
- [x] 白名单外无改动

## 8. 执行回贴（执行面填）

| 面 | 摘要 | 自检结果 | 完成 |
|----|------|----------|------|
| 编排 | `record_success` / `get_lessons_by_topic` / `extract_topic`；kb verified→released 沉淀；product「## 同主题经验」；失败 json 路径未改 | `test_lessons_success` + `pytest tests/scripts/ -q` 绿 | 是 |

## 9. 架构验收

| 项 | 结果 |
|----|------|
| 结论 | **通过** `4ed4774` |
| 缺口 | 无 |
| 验收日 | 2026-07-21 |

**审阅：** `record_success`/`get_lessons_by_topic`/`extract_topic` 落 `_lessons.py`；kb 归档时调 `record_success`（异常 warning 不阻塞）；product 注入 `_success_lessons_block`；失败 lessons 路径不动；测绿；白名单内。
