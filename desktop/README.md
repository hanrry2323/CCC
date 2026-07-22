# CCC Desktop（SwiftUI）

主产品客户端：

| 区 | 内容 |
|----|------|
| **左（Codex）** | 新对话 · 项目 · **看板/运维（顶部）** · 会话列表；底栏 **用户/设置**（预留） |
| **中（Codex）** | 居中对话主舞台 + 底部 composer |
| **右** | 活动动画流程图（差异化） |

连中心 Hub（`CCC_SERVER`，**默认** `http://127.0.0.1:17777` 本机 SSH 隧道；LAN `:7777` 仅排障，不作 Desktop/sidecar 默认）。

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
bash desktop/scripts/package-baseline.sh
# 产物（版本读仓库 VERSION）：
#   desktop/.build/release/CCCDesktop
#   desktop/.build/CCCDesktop.app
rm -rf /Applications/CCCDesktop.app
cp -R desktop/.build/CCCDesktop.app /Applications/
```

LAN 上线卡：[`../docs/ops/GO-LIVE-DESKTOP.md`](../docs/ops/GO-LIVE-DESKTOP.md)

## 真闭环冒烟

```bash
# 连 Mac2017（Hub 需在线）
CCC_SERVER=http://192.168.3.116:7777 bash scripts/smoke-desktop-e2e.sh

# Hub 不可达时：本地 fanout + pytest
CCC_DESKTOP_SMOKE_LOCAL=1 bash scripts/smoke-desktop-e2e.sh
```

## 非目标

- 不嵌网页 Hub SPA
- 无双对话分屏
- 不把 OpenCode 嵌进 Desktop 进程
