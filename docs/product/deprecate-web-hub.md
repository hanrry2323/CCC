# 网页 Hub 降级与废弃项

> 2026-07-19 · 产品主入口已切换为 **CCC Desktop（SwiftUI）**。

---

## 主入口

| 面 | 状态 |
|----|------|
| [`desktop/`](../../desktop/) SwiftUI | **主产品** |
| 网页 Hub `:7777/` | **运维 / 兼容**（看板观察、急救） |
| Tauri WebView 壳 | 非主线；可用但不再作为产品叙事 |

---

## 废弃（勿再对外宣传）

| 项 | 说明 |
|----|------|
| **双对话分屏** | `dualPane.js` / `?desktop=1` 分屏 — 实验功能，产品上废弃 |
| **Hub / Claude 双源历史** | Desktop Thread API 仅统一会话；旧 `/api/history?source=all` 仅网页兼容 |
| **网页当最终产品** | VISION / topology 已改口 |

网页 UI 可保留分屏按钮供内部调试，但 README / 对外材料不得再写「双会话分屏是 Desktop MVP」。

---

## Desktop 打包基线

见 [`desktop/README.md`](../../desktop/README.md)：

```bash
cd desktop && swift build -c release
# 产物 .build/release/CCCDesktop；.app 签名 / notarize 后置
```

---

## 运维仍用网页时

- 看看板列、timeline、ops
- Basic Auth 同 Desktop
- 业务转任务请走 Desktop 或 `POST /api/desktop/transfer`
