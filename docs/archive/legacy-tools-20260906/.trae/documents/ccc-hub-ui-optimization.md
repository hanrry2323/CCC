# CCC Hub 页面 UI 优化方案

## 概述

解决 Hub 页面导航断裂和四页视觉割裂问题。已完成 P0 导航修复和部分 P1 UI 统一，剩余 P1 卡片化和按钮统一。

**重要决定：** 暗色模式已取消（2026-08-01），移除全部 `[data-theme="dark"]` CSS 代码和相关 JS 逻辑，仅保留 light 主题。

---

## 当前状态分析

### 导航问题（✅ 已修复）

1. **Dialogue 模式（:7788）导航栏被隐藏** → 已恢复，隐藏编排口专用元素而非导航栏
2. **Hub 模式（:7777）"对话"链接跳转外部** → 已改为内联提示，不强制跳转

### UI 风格问题

1. ✅ **四页容器不一致** → 已修复，新增 `.hub-page` 统一类，board/ops/console 三页共用
2. ✅ **Console 页 banner 用内联样式** → 已修复，改为 `.console-banner` CSS 类
3. ✅ **看板工作区按钮视觉过重** → 已简化（1px 边框、药丸形激活态、绿色小圆点）
4. ✅ **看板页标题含"停更"** → 已清除
5. ✅ **Ops 页恢复** → mountOps/unmountOps 已恢复，事件绑定正常
6. ⬜ **Ops 页信息密度高** → 部分段落未用 `.ops-card` 包裹，需卡片化
7. ⬜ **按钮样式不统一** → `.board-toolbar button` 与 `.hub-btn` 未完全对齐
8. ✅ **暗色模式** → 已取消，移除全部相关代码

---

## 变更清单

### P0：导航修复（✅ 已完成）

#### 1. 恢复 Dialogue 模式导航栏
- **文件：** `frontend/css/shell.css`
- 删除 `#hub-nav` 的 `display: none`，改为隐藏编排口专用元素

#### 2. Hub 模式"对话"链接改为内联提示
- **文件：** `frontend/js/router.js`
- 新增 `showHubChatNotice()`，不再强制跳转

#### 3. 更新页面标题
- **文件：** `frontend/js/app.js`
- 看板页标题去掉"停更"

---

### 暗色模式移除（✅ 已完成）

#### 4. 删除暗色 CSS 变量
- **文件：** `frontend/css/themes.css`
- 删除整个 `[data-theme="dark"]` 块

#### 5. 简化 JS 主题逻辑
- **文件：** `frontend/js/theme.js`
- `applyTheme()` 始终设置 `data-theme="light"`
- `toggleLightDark()` 始终返回 light
- `setThemeScheme()` 不再接受 'dark' 作为有效值

#### 6. 简化主题初始化
- **文件：** `frontend/js/theme-init.js`
- 删除 `prefers-color-scheme` 检测，始终设置 light

#### 7. 设置面板移除深色选项
- **文件：** `frontend/js/components/settings.js`
- 主题选择下拉框移除"深色"选项

#### 8. 移除系统主题监听
- **文件：** `frontend/js/components/titlebar.js`
- 删除 `prefers-color-scheme: dark` 的 `change` 事件监听

---

### P1：UI 统一（部分完成，剩余 ⬜）

#### 9. 统一页面容器（✅ 已完成）
- **文件：** `frontend/css/shell.css`, `boardPage.js`, `opsPage.js`, `consolePage.js`
- 新增 `.hub-page` / `.hub-page-header` 类，三页统一使用

#### 10. Console 页 banner 改用 CSS 类（✅ 已完成）
- **文件：** `frontend/css/shell.css`, `consolePage.js`
- 新增 `.console-banner` 类，使用 CSS 变量

#### 11. 简化看板工作区按钮（✅ 已完成）
- **文件：** `frontend/css/shell.css`
- 1px 边框、药丸形、绿色小圆点

#### 12. Ops 页信息卡片化（⬜ 待完成）

**现状：** 以下段落未用 `.ops-card` 包裹：
- `#ops-alerts`（行 85）— 风险卡片列表
- `#ops-workspaces`（行 114）— 工作区 Diff 表格
- `#ops-docs`（行 138）— 文档债
- `#ops-quality`（行 142）— 质量日摘要
- `#ops-risks-low`（行 147）— 其它风险
- `#ops-auto`（行 155）— 弹药队列
- `#ops-adoptables`（行 169）— 可采纳项

**方案：** opsPage.js `html()` 中，为上述段落容器添加 `class="ops-card"`。注意：
- `#ops-alerts` 当前是裸 `div`，加 `class="ops-card"` 使其与周边视觉一致
- `#ops-workspaces` 同理
- `#ops-docs` / `#ops-quality` / `#ops-risks-low` / `#ops-auto` / `#ops-adoptables` 均加 `class="ops-card"`
- `#ops-quality` 内已有 `.ops-card` 子元素，但容器本身无卡片，需统一

#### 13. 统一 Hub 按钮样式（⬜ 待完成）

**现状：** 存在多套按钮定义：
- `.hub-btn`（shell.css 通用，ops/console 使用）
- `.board-toolbar button`（行 274-286）— 与 `.hub-btn` 视觉接近但独立定义
- `.board-toolbar button.primary` / `.hub-btn.primary`（行 288-295）

**方案：**
- 将 `.board-toolbar button` 的选择器依赖改为 `.hub-btn`，删除重复定义
- 确保所有页面按钮使用同一套尺寸/圆角/悬停态

---

## 实施步骤

### 步骤 1：暗色模式移除（✅ 已完成）
见变更清单 4-8。

### 步骤 2：Ops 页信息卡片化（⬜）
| 文件 | 改动 |
|------|------|
| `frontend/js/pages/opsPage.js` | 为 `#ops-alerts`、`#ops-workspaces` 等段落容器添加 `class="ops-card"` |

### 步骤 3：统一 Hub 按钮样式（⬜）
| 文件 | 改动 |
|------|------|
| `frontend/css/shell.css` | 删除 `.board-toolbar button` 重复定义，统一使用 `.hub-btn` |

---

## 验证方法

1. ⬜ **暗色模式彻底移除**：检查无 `data-theme="dark"` 引用，主题切换仅 light/system（均解析为 light）
2. ⬜ **Ops 页卡片化**：所有信息段落都有 `.ops-card` 包裹，视觉一致
3. ⬜ **按钮统一**：board/ops/console 三页按钮尺寸/圆角/悬停态一致