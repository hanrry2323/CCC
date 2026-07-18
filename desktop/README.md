# CCC Desktop（SwiftUI）

主产品客户端：三栏 = **项目** / **方案对话** / **编排流程**。  
连中心 Server（`CCC_SERVER`，默认 `http://192.168.3.116:7777`）。

架构 SSOT：[`../docs/product/ccc-desktop-architecture.md`](../docs/product/ccc-desktop-architecture.md)

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
