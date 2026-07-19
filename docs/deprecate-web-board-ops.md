# 网页 Hub `#/board` `#/ops` 退役计划

> 架构对齐 2026-07-19。  
> 边界基线：[`product/dialogue-orchestration-boundary.md`](product/dialogue-orchestration-boundary.md)。  
> 拓扑：[`deploy/topology.md`](deploy/topology.md)。

## 背景

CCC 主产品入口 = **M1 Desktop**（SwiftUI）。看板/运维已原生内嵌 Desktop（`BoardView.swift` / `OpsView.swift`），直接读 Mac2017 编排层（Hub `/api/board` `/api/ops/*`）。  
网页 Hub 的 `#/board` `#/ops` 是历史过渡面，功能将不再演进，最终下线。

## 现状

| 面 | 状态 | 数据源 |
|----|------|--------|
| Desktop 看板 | 原生 SwiftUI，W2-W3 补到 SPA 功能对齐 | Hub `/api/board` `/api/board/summaries` |
| Desktop 运维 | 原生 SwiftUI，W3 补到 SPA 功能对齐 | Hub `/api/ops/summary` `/api/ops/overview` `/api/ops/risks` |
| 网页 `#/board` | 仍可用，**冻结** | 同上 |
| 网页 `#/ops` | 仍可用，**冻结** | 同上 |
| 网页 `#/console` | 保留为 SSH-only 运维兜底 | `/api/dashboard` `/api/failures` |

## 退役步骤

1. **W2-W3**：Desktop 看板/运维功能对齐 SPA（拖拽 / 多 workspace / adopt / daily-review / quality / docs-debt）
2. **W3 末**：网页 `router.js` 把 `#/board` `#/ops` 重定向到「请在 Desktop 中查看」提示页
3. **W4**：保留 `#/console` 作为 SSH-only 运维兜底；其余网页 SPA 入口降级为「运维/兼容」
4. **远期**：网页 SPA 仅保留 `#/console`；其余代码可清理

## 不退役的部分

- `#/console`：纯运维兜底（无 Desktop 时 SSH 端口转发查看）
- Hub 后端 API（`/api/board` `/api/ops/*` `/api/desktop/*`）：Desktop 仍通过 LAN 调用，**不删**

## 验收

- Desktop 看板拖拽移动可用（`POST /api/tasks/move`）
- Desktop 运维 adopt / daily-review / quality 段可见
- 网页 `#/board` `#/ops` 显示重定向提示
- Desktop 对话 + 右栏编排不受影响
