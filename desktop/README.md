# CCC Desktop（SwiftUI）

主产品客户端：

| 区 | 内容 |
|----|------|
| 极左图标栏 | 对话 / **Hub** / **运维**（后两者开浏览器，对齐 Cursor Automations·Customize） |
| 左树 | **项目 ▸ 对话**（嵌套，非上下两截） |
| 中 | 方案 Agent |
| 右 | 活动编排图（Epic/Work 卡片） |

连中心 Server（`CCC_SERVER`，默认 `http://192.168.3.116:7777`）。

架构：[`../docs/product/ccc-desktop-architecture.md`](../docs/product/ccc-desktop-architecture.md)  
右栏 UX：[`../docs/product/desktop-flow-rail-ux.md`](../docs/product/desktop-flow-rail-ux.md)

## 要求

- macOS 13+
- Xcode 15+ / Swift 5.9+

## 运行

```bash
cd desktop
swift build
swift run CCCDesktop
```

或用 Xcode：`open Package.swift` → 选 CCCDesktop scheme → Run。

## 设置

菜单 **CCC → Settings…**：

| 键 | 默认 |
|----|------|
| Server | `http://192.168.3.116:7777` |
| 用户/密码 | `ccc` / `ccc` |

环境变量等价：启动前可设 `CCC_SERVER`（应用内 `@AppStorage` 优先）。

## 打包基线（P4）

```bash
swift build -c release
# 产物：.build/release/CCCDesktop
# 正式 .app / 签名 / notarize 可后置
```

## 非目标

- 不嵌网页 Hub SPA
- 无双对话分屏
- 不把 OpenCode 嵌进 Desktop 进程
