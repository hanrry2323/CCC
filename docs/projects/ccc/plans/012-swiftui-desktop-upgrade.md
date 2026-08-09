# 方案 · CCC Desktop 前端高质量组件升级（SwiftUI 组件库接入）

> 项目：ccc · 编号：ccc-plan-012 · 状态：已完成 · 作者：OpenCode · 工具：OpenCode
> 创建：2026-08-09 · 更新：2026-08-10
> 关联卡：ccc033 ccc034 ccc035 ccc036 ccc037 ccc038 ccc039
> 关联方案：无（新建专项）

## 目标

把 CCC Desktop（SwiftUI 原生 macOS 应用）从「全手写零依赖」升级为「高质量组件库支撑」，消除每天手写小组件（Markdown 渲染、通用控件、进度条、图表、loading、动效）的重复劳动。配套：部署目标 macOS 13 → 15（解锁 Textual / .glassEffect / 系统 Charts 全量能力），Desktop 主对话面解冻恢复可开发。

## 背景

- CCC Desktop = 纯 SPM 可执行（desktop/Package.swift，swift-tools 5.9，macOS 13+），**零外部依赖**，22 个 Swift 文件全手写（2026-08-09 取证）。
- 痛点轮子（重复造轮子清单，Sub-Agent 取证）：`MarkdownText.swift`（360 行自写 Markdown 解析器，含表格，刻意拒绝系统 AttributedString）、`ToolProgressRail.swift`（手绘分段进度条）、`ComposerTextView.swift`（手写 NSTextView 包装）、`Theme.swift`（手绘 hairline）、`BoardView/TaskCardPanel`（手写卡片/看板）、`ProjectCard.swift`（死代码 stub 未清）。
- 组件库选型（2026-08-09 实测 GitHub API + 本地验证）：SwiftUIX（macOS 11，活跃）、swiftui-introspect（macOS 12，活跃）、textual（macOS 15，活跃，MarkdownUI 继任者）、Pow（macOS 12，活跃）、DynamicColor、SFSafeSymbols、SkeletonUI、SwiftUI-Shimmer、FluidGradient；系统内置 **Swift Charts**（macOS 13+）。
- **排除**：STTextView（GPL 双许可，商用风险）、lottie-ios（127MB，暂不需要）。
- 10 库已存 HP 参考库 `hp@192.168.3.131:/data/projects/reference/swiftui-libs/`（2026-08-09）。
- **决策（老板拍板）**：部署目标升 macOS 15；Desktop 主对话面解冻；参考库存精简集 10 个。
- **工具链**：本机 Xcode 26.6 / Swift 6.3.3，支持 macOS 15 SDK 与 tools 6.x，升目标无环境障碍。

## 方案内容

分 6 卡推进，每卡独立门禁（构建 + 测试 + 冒烟 + UI 视觉验收，按 2026-08-09 前端 UI 验收教训）：

1. **卡0**：部署目标 13→15（Package.swift platforms 升级；swift-tools 若 5.9 不识别 v15 升 6.0）；roadmap 冻结清单解冻声明。
2. **卡1**：SPM 引入 SwiftUIX + swiftui-introspect + textual（纯依赖引入，零业务代码改动，构建/测试/冒烟兜底）。
3. **卡2**：MarkdownText → Textual 渲染（保留公共 API，专项回归：聊天流式/方案卡/表格/代码块/单换行行为）。
4. **卡3**：OpsView 指标可视化改系统 Swift Charts。
5. **卡4**：质感接入 Pow（动效）+ DynamicColor（主题色，硬编码色值清零）+ Shimmer/Skeleton（loading）+ `.glassEffect`/FluidGradient（材质）。
6. **卡5**：清理 ProjectCard 死代码 stub 与失效 TimelineView。

## 验收标准

- [ ] 6 卡全部完成：deployment target 15、3 库 SPM 引入、Markdown 换 Textual、OpsView 用 Charts、质感库接入、死代码清零。
- [ ] 每卡 `swift build` / `swift test` / 冒烟（smoke-ui-chat.sh）全绿；UI 视觉验收（深浅色 + 两档宽度 + 硬编码色值清零）随卡打回机制执行。
- [ ] Markdown 换库后「单换行行为」与自写渲染器一致（原刻意决策项不回归）。
- [ ] 全量完成后 `scripts/package-baseline.sh` 出包正常，版本号按 CCC 规则递增。

## 转卡计划

```ccc-plan
title: CCC Desktop 前端高质量组件升级（SwiftUI 组件库接入）
project: ccc
slices:
  - title: Desktop 部署目标升级 macOS 15 + 解冻声明
    slug: desktop-target-macos15
    acceptance:
      - Package.swift platforms 由 [.macOS(.v13)] 改为 [.macOS(.v15)]；swift-tools-version 若 5.9 不识别 v15 则升 6.0，Xcode 26.6 下 swift build 通过
      - swift build 与 swift test 全绿，无新增编译警告
      - desktop/scripts/package-baseline.sh 可产出 CCCDesktop.app（或注明未跑原因）
      - docs/roadmap.md 冻结清单「Desktop/Hub 主对话面：暂缓维持」更新为解冻声明并引用 ccc-plan-012
    whitelist:
      - desktop/Package.swift
      - desktop/Tests/**
      - docs/roadmap.md
      - desktop/scripts/package-baseline.sh
    executor: OpenCode
  - title: Desktop 引入 SwiftUIX / swiftui-introspect / textual（纯依赖，零代码改动）
    slug: desktop-spm-deps
    acceptance:
      - desktop/Package.swift dependencies 增加 SwiftUIX、swiftui-introspect、textual，版本与 HP 参考库 /data/projects/reference/swiftui-libs/ 快照（2026-08-09）对应
      - swift build / swift test / desktop/scripts/smoke-ui-chat.sh 全绿
      - 业务代码零改动（diff 仅 Package.swift 与锁文件）
      - scripts/package-baseline.sh 出包正常
    whitelist:
      - desktop/Package.swift
      - desktop/Package.resolved
      - desktop/.build/**
    executor: OpenCode
  - title: MarkdownText 改用 Textual 渲染（聊天/方案卡 Markdown）
    slug: desktop-markdown-textual
    acceptance:
      - MarkdownText.swift 渲染核心换 Textual（或二次封装），对外公共 API 不变，调用方零改动
      - 专项回归清单逐项通过：聊天流式消息、方案卡正文、表格、代码块、行内 **bold**/`code`/斜体、单换行行为（原刻意决策项）
      - 深浅色两档 + 两档窗口宽度无溢出
      - swift build / swift test / smoke-ui-chat.sh 全绿
    whitelist:
      - desktop/Sources/CCCDesktop/Components/MarkdownText.swift
      - desktop/Sources/CCCDesktop/**/*.swift
    executor: OpenCode
  - title: OpsView 指标可视化改用系统 Swift Charts
    slug: desktop-ops-charts
    acceptance:
      - OpsView 关键 KPI（集群/资源/心跳趋势等）用 import Charts 呈现，替换纯手写 Gauge 堆叠
      - 深浅色 + 窄窗无溢出，数据刷新（15s 轮询）正常
      - swift build / swift test 全绿
    whitelist:
      - desktop/Sources/CCCDesktop/OpsView.swift
      - desktop/Sources/CCCDesktop/Components/**
    executor: OpenCode
  - title: 质感接入 Pow / DynamicColor / Shimmer / Skeleton / glassEffect
    slug: desktop-polish-libs
    acceptance:
      - Theme.swift 色板迁移 DynamicColor 深浅色自适应，硬编码色值清零（grep 验收）
      - 卡片/按钮接 Pow 动效（弹簧/悬停）
      - 加载态用 Shimmer 或 SkeletonUI；关键面板 .glassEffect（macOS 15+）或 FluidGradient
      - 视觉验收：深浅色、两档宽度、动效流畅无卡顿
      - swift build / swift test 全绿
    whitelist:
      - desktop/Sources/CCCDesktop/**/*.swift
    executor: OpenCode
  - title: 清理 ProjectCard 死代码 stub 与失效 TimelineView
    slug: desktop-projectcard-cleanup
    acceptance:
      - ProjectCard 移除 primaryKind/statusLine 恒值 stub（原 L189-199）与失效 TimelineView 齿轮动画
      - 侧栏项目卡片显示行为不变
      - swift build / swift test 全绿
    whitelist:
      - desktop/Sources/CCCDesktop/Components/ProjectCard.swift
    executor: OpenCode
```

## 备注

- **风险**：Markdown 换库回归（卡2 单独验收守住单换行行为）；首次引外部依赖（卡1 纯引入不换码，构建门禁兜底）；升 15 影响桌面用户门槛（已获老板批准）。
- **依赖**：卡0 → 卡1 → 卡2 严格串行；卡3/4/5 可并行。
- **参考库**：10 库存 HP `/data/projects/reference/swiftui-libs/`，SPM 引用走远程仓库版本 tag，本地参考库仅备查。
- **巡检**：本方案转卡后挂每 20 分钟巡检（OpenCode 出卡跟踪），直至全部卡关闭或老板手动停止。
