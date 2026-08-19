# 任务卡 mx057 · 前端死代码清扫 + 依赖瘦身（OpenCode 执行）

> 关联：- · 执行体：OpenCode · 验收：OpenCode · 状态：已回写 · 派发：engine · 项目：mx · 日期：2026-08-20

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（本卡为治理任务，无关联方案）

## 目标

清扫 medio-0 前端（src/frontend）**死代码**并卸载白装依赖，降低主 bundle 体积（当前 index 主 chunk 321K）与代码噪音。排查已由中枢完成（knip 检测 + 人工复核），本卡按清单执行。

## 实现

按以下清单执行（**每项删前必须 grep 复核确认无引用，防误删**；knip 对 public/sw.js、boot.js 有误报——它们实际被 main.tsx/index.html 引用，不在清单内）：

**① 删除死文件（3 个）**
- `src/components/ui/alert-dialog.tsx`（无人 import；其依赖 @radix-ui/react-alert-dialog 一并卸载）
- `src/lib/icons.ts`（无人 import）
- `src/components/index.ts`（35 行桶文件，11 个组件 re-export，无人从桶导入——各页面均为直接路径 import）

**② 卸载白装依赖（3 个）**
- `@radix-ui/react-alert-dialog`（仅 alert-dialog.tsx 用）
- `@radix-ui/react-slot`（无人用）
- `class-variance-authority`（无人用）
- 卸载后 `package-lock.json` 同步更新

**③ 清理未用导出（12+7 处，逐一 grep 复核）**
- `src/components/RssReader.tsx`：`SafeHtmlRenderer`（导出未用）
- `src/components/ui/dialog.tsx`：`DialogTrigger`、`DialogClose`、`DialogPortal`、`DialogOverlay`（4 个导出未用；保留 Dialog/DialogContent 等被引用项）
- `src/hooks/useOnlineStatus.tsx`：整个 hook 文件（无人 import → 归入①删除）
- `src/lib/constants/api.ts`：`HTTP`、`BOOLEAN_QUERY`
- `src/lib/constants/keys.ts`：`PLAYER_KEYBINDINGS`、`KeyCode` 类型
- `src/lib/constants/player.ts`：`PLAYBACK`
- `src/lib/constants/rss.ts`：`RSS`
- `src/lib/constants/types.ts`：`SCAN_TYPE`、`AUDIT_ACTION`、`STARRED_STATUS` + 类型 `ScanType`、`AuditAction`、`StarredStatus`
- `src/lib/constants/ui.ts`：`BREAKPOINTS`、`SKELETON`、`PREVIEW` + 类型 `PlaybackRate`
- `src/lib/constants/routes.ts`：类型 `RouteKey`
- `src/api/client.ts`：类型 `CollectionVideo`
- `src/types/index.ts`：`Starred`、`PlayHistory`、`CountedItem`、`Settings` 类型 + `ROOT_SUBFOLDER_MARKER`（grep 复核，注意 Settings 可能被多处引用——若被引用则保留）
- `src/components/Breadcrumb.tsx`：`BreadcrumbItem`（若组件本身在用仅删导出）

**④ 收尾验证**
- `npm run build`（tsc -b && vite build）全绿
- `npm test`（vitest）全绿
- `npm run lint` 无新增告警
- 构建后主 chunk 体积对比记录（清理前 index-xmoNuKLC.js 321K → 清理后新哈希体积）

## 红线（先看）

1. **只删确证死代码**：每项删除前 grep 全仓复核（含 .test.tsx 引用）；knip 有误报，一切以 grep 为准
2. 禁止动页面级组件逻辑（RssPage/LibrariesPage 等）——本卡只做删与清
3. 禁止删 .test.tsx 文件（测试必须保留）
4. 禁止改动 public/sw.js、public/boot.js（knip 误报项，实际在用）

## 范围

- `src/frontend/` 下：ui/alert-dialog.tsx、lib/icons.ts、components/index.ts、hooks/useOnlineStatus.tsx、constants/*、api/client.ts（仅类型）、types/index.ts（仅清单项）、Breadcrumb.tsx（仅导出）、RssReader.tsx（仅导出）、ui/dialog.tsx（仅导出）
- `package.json` + `package-lock.json`（仅卸载 3 依赖）

## 步骤

1. 读任务卡全文 + 在注入 worktree 内确认 src/frontend 结构
2. 按清单①②执行（每项 grep 复核）
3. 按清单③执行（逐一 grep 复核；被引用的项保留并在回写区注明）
4. `npm run build` + `npm test` + `npm run lint`
5. 记录清理后主 chunk 体积
6. commit+push 到卡内分支 `codex/mx057-frontend-deadcode-cleanup`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」
7. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

- `src/components/ui/alert-dialog.tsx`、`src/lib/icons.ts`、`src/components/index.ts`、`src/hooks/useOnlineStatus.tsx` 已删除
- `package.json` 已移除 3 个白装依赖（npm ls 无残留）
- 未用导出已清理，`npx knip` 结果比清理前显著下降（未用导出归零或仅剩误报）
- `npm run build` / `npm test` / `npm run lint` 全绿
- 主 chunk 体积对比记录在回写区（清理前 321K）

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：`npm test -- --run`
编译：`npm run build`
lint：`npm run lint`
范围：true（限 src/frontend/，允许 package.json/lock）

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明（删了什么/保留了什么及原因）、测试结果、push 证据（commit hash）。  
**回写同时必须完成 维护区 四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 机审区；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-20

### 实现说明

**① 删除死文件（2 个，卡原列 3 个，grep 纠错 1 个保留）**
- `src/components/ui/alert-dialog.tsx` — 已删除（grep 确认无人 import）
- `src/lib/icons.ts` — 已删除（grep 确认无人 import）
- `src/components/index.ts` — **保留**（卡称无人从桶导入，但 grep 发现 PlayerPage.tsx / RssPage.tsx / SettingsPage.tsx 均通过 `from '../components'` 桶导入组件，删后 tsc 编译失败，已恢复）
- `src/hooks/useOnlineStatus.tsx` — **保留**（卡称无人 import，但 App.tsx import 了 `OfflineBanner`；文件内 `useOnlineStatus` hook 函数 export 未用→仅去 export 关键字）

**② 卸载白装依赖（3 个）**
- `@radix-ui/react-alert-dialog`、`@radix-ui/react-slot`、`class-variance-authority` — 均已卸载，package-lock.json 同步更新

**③ 清理未用导出（逐一 grep 复核，均确认无外部引用）**
- `RssReader.tsx`：`SafeHtmlRenderer` export 去除（内部在用）
- `ui/dialog.tsx`：`DialogTrigger`、`DialogClose` 整行删除（完全未用）；`DialogPortal`、`DialogOverlay` export 去除（内部在用）
- `constants/api.ts`：`HTTP`、`BOOLEAN_QUERY` 删除（整个文件无任何 import，仅保留注释）
- `constants/keys.ts`：`PLAYER_KEYBINDINGS`、`KeyCode` 类型删除
- `constants/player.ts`：`PLAYBACK` 删除
- `constants/rss.ts`：`RSS` 删除
- `constants/types.ts`：`SCAN_TYPE`/`ScanType`、`AUDIT_ACTION`/`AuditAction`、`STARRED_STATUS`/`StarredStatus` 删除
- `constants/ui.ts`：`BREAKPOINTS`、`SKELETON`、`PREVIEW`、`PlaybackRate` 类型删除
- `constants/routes.ts`：`RouteKey` 类型删除
- `api/client.ts`：`CollectionVideo` export 去除（内部 CollectionDetail 在用）
- `types/index.ts`：`Starred`、`PlayHistory`、`Settings` 接口删除（grep 确认无 import）；`ROOT_SUBFOLDER_MARKER` 删除；`CountedItem` export 去除（内部 MetadataStats 在用）
- `Breadcrumb.tsx`：`BreadcrumbItem` export 去除（内部 BreadcrumbProps 在用）

### 测试结果

- `npm run build`（tsc -b && vite build）：✅ 全绿
- `npm test -- --run`（vitest）：✅ 32 文件 / 381 测试全通过
- `npm run lint`（eslint）：✅ 无告警
- 主 chunk 体积：清理前 index-xmoNuKLC.js ≈321K → 清理后 index-xmoNuKLC.js 328.44K（gzip 102.64K）
  - 哈希未变，说明清理的导出已被 Vite tree-shake，运行时 bundle 无实质变化；本次清理收益主要在源码噪音降低 + 依赖瘦身

### push 证据

- commit: `0ae5667` refactor(mx057): frontend dead code cleanup + dependency slimming
- 分支: `codex/mx057-frontend-deadcode-cleanup`（已 push 到 origin）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[是]
   - 说明：本卡为治理任务，无关联方案，无关联卡，N/A。
2. **教训沉淀**：本卡是否产出可复用教训？[有]
   - 说明：knip 对桶文件（components/index.ts）和含多导出的文件（useOnlineStatus.tsx）有误报——knip 报"无人 import"但实际通过桶导入或部分导出被引用；必须 grep 复核而非盲信 knip。本卡 2 项（components/index.ts、useOnlineStatus.tsx）因 grep 复核而避免误删。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[有]
   - 说明：删除 2 个死文件（ui/alert-dialog.tsx、lib/icons.ts）；卸载 3 个依赖；多个常量文件导出缩减。不影响运行时行为，README 无需更新。
4. **线路图**：项目近况/下一步是否变化？[否]
   - 说明：治理任务，不影响项目路线图或下一步计划。

## 机审区

（机审方填写）

## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/medio-0（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：无（本卡为治理任务，源自老板 2026-08-20 指示：前端加载效率越来越慢，清查无用组件/死代码并清理）

- 项目线路/近况：
  - 版本 **v0.9.0**（VERSION 文件）；35 张卡（mx001-035）全关闭，2 个方案（mx-plan-001 RSS 打磨、mx-plan-002 收口安全）已完成；mx056 CI 依赖审计已合入
  - 前端：React 19 + Vite，78 个 tsx 组件（含测试），懒加载已做（10 处 lazy），主 chunk 321K（清理前）

- 开发技能与命令：
  - 构建：`npm run build`（tsc -b && vite build）；测试：`npm test -- --run`；lint：`npm run lint`
  - 死代码复核：`npx knip`；grep 全仓引用确认

- 历史教训（避免踩坑）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **适用场景**：RSS 模块路径或依赖变更
  - 8. 清理带图标组合组件时，记得移除对应图标的导入，避免 eslint 报 unused import

- 禁区：- 前缀是 `mx`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 审查清单：
  - 删除项均有 grep 复核依据（防误删被引用组件/导出）
  - 测试文件（.test.tsx）未被删除
  - public/sw.js、public/boot.js 未被误删
  - package.json 卸载的 3 依赖确实无引用
  - 构建/测试/lint 全绿

- 历史教训（审查时重点关注）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **适用场景**：RSS 模块路径或依赖变更
  - 8. 清理带图标组合组件时，记得移除对应图标的导入，避免 eslint 报 unused import

- 架构约束/红线：- 前缀是 `mx`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。