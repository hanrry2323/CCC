# PASTE-OPS · 工厂派单板（用户只复制）

> 架构窗维护本文件。用户：**不讨论、不加需求**，按序把「粘贴包」贴进对应窗。  
> 模型路由：[`../product/cursor-model-routing.md`](../product/cursor-model-routing.md)

## 流水线状态

| 序号 | brief | 状态 | 窗 |
|------|-------|------|-----|
| F0 | 建制 | done `94da446` | — |
| F1 | 断线恢复 | done `eeaf388` | — |
| F1-2 | 投递三态零谎报 | done `578e7fe` | — |
| F2-1 | soak N=5 + orphan=0 | done `9af1fb4` | — |
| F2-2 | 双机版本对齐核对 | done `555b9bc` | — |
| F3-1 | qb 业务向闭环 | done `327fd86` | — |
| F3-2 | hp 业务向闭环 | done `6523330` | — |
| F3-3 | xianyu 业务向闭环 | done `1526ca1` | — |

**✅ 流畅基线达成** — [`../product/fluency-baseline-achieved.md`](../product/fluency-baseline-achieved.md)

---

## 下一步候选（按需，无活跃 brief）

| ID | 项 | 窗 | 模型 | 状态 |
|----|----|----|------|------|
| H-1 | `epic_done` 流事件补齐 | 编排 | Auto | **done `461f021`** |
| 版本 bump | v0.52.2 → 流畅基线签 | 架构 | 高级 | queued |
| F4-1 | 显式 Context Engineering | 编排 | 高级 | **accepted · 现在开工** |
| F4-2 | Memory 沉淀（lessons） | 编排 | Auto | accepted（F4-1 后接） |
| F4-3 | Proactive 触发（CI/hook） | 编排 | 高级 | accepted（可与 F4-1 并行） |
| H-2 | `work_status` 后续阶段流事件 | 编排 | Auto | queued |

用户点哪条，架构出 brief；否则流水线休眠。

---

## 粘贴包 B · 编排窗

```
H-1 已合入 461f021。F4-1/F4-2/F4-3 三 brief 已 accepted，按序贴下方粘贴包。
```

---

## 粘贴包 B1 · 编排窗 · F4-1 开工（先贴这个 · 高级模型）

```
模型：高级
只认 brief：docs/briefs/2026-07-21-f4-1-explicit-context-engineering.md
白名单：scripts/board/context.py
        scripts/board/roles/product.py · dev.py · reviewer.py（改用 build_role_context）
        tests/scripts/test_context_manifest.py（新）
        docs/product/context-manifest.md（新）
        docs/architecture-core.md（加一行链）
        docs/briefs/2026-07-21-f4-1-explicit-context-engineering.md（填 §8）
禁止：改 Engine 主循环、改 SSE、改 Desktop、改 transfer/flow、改角色职责、改无关文件。
做完：填 brief §8 → commit → 回复「F4-1 done <hash>」
提交说明建议：
refactor(board): explicit per-role context manifest (F4-1)
```

---

## 粘贴包 B2 · 编排窗 · F4-2 开工（F4-1 done 后贴 · Auto）

```
模型：Auto
只认 brief：docs/briefs/2026-07-21-f4-2-memory-sediment.md
白名单：scripts/_lessons.py
        scripts/board/roles/kb.py
        scripts/board/roles/product.py
        tests/scripts/test_lessons_success.py（新）
        docs/product/context-manifest.md（加 success_lessons 项）
        docs/briefs/2026-07-21-f4-2-memory-sediment.md（填 §8）
禁止：改 Engine 主循环、改 SSE、改 Desktop、改 transfer/flow、改失败 lessons 既有路径、改无关文件。
做完：填 brief §8 → commit → 回复「F4-2 done <hash>」
提交说明建议：
feat(lessons): sediment success lessons by topic (F4-2)
```

---

## 粘贴包 B3 · 编排窗 · F4-3 开工（可与 F4-1 并行 · 高级模型）

```
模型：高级
只认 brief：docs/briefs/2026-07-21-f4-3-proactive-triggers.md
白名单：scripts/chat_server/routers/desktop.py
        scripts/chat_server/app.py（若需注册）
        scripts/ccc-ingest-ci-failure.sh（新）
        tests/scripts/test_proactive_epic.py（新）
        docs/product/hub-api-v1.md（先改）
        docs/product/proactive-triggers.md（新）
        docs/briefs/2026-07-21-f4-3-proactive-triggers.md（填 §8）
禁止：改 Engine 主循环、改 Desktop、改 transfer 字段、改 flow-events、改无关文件。
做完：填 brief §8 → commit → 回复「F4-3 done <hash>」
提交说明建议：
feat(hub): proactive epic ingest for CI/git-hook signals (F4-3)
```
