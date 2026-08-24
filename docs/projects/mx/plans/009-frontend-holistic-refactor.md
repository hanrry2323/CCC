# 方案 · medio-0 前端整体重构

> 项目：mx · 编号：mx-plan-009 · 状态：部分执行 · 作者：DSH · 工具：ccc-plan（受老板临时授权项目制直接执行）
> 创建：2026-08-24 · 更新：2026-08-24
> 批准：老板逐条批准全部核心条目 · 2026-08-24（会话内 ask-user 多选确认）
> 关联卡：按批次出卡或直执（直执批次在 state.md 留痕）
> 进度：批次 1/2/3 完成（批次 1 老板真机确认解决）；批次 4 待推进
> 工作底稿：medio-0 `.ccc/plans/frontend-refactor-draft.md`

## 目标

系统性解决前端三类问题：①各页面风格不统一（376 处内联样式、2578 行单文件 CSS）②手机/平板/PC 三端适配缺陷（5 种断点混用、RSS 移动端遮挡）③死代码与老代码干扰；并建立"每阶段部署 HP + 真机抽查"的流程保障。

## 背景（调查结论）

3 路子代理并行审计 + DSH 一手快扫交叉验证：
- 手机 RSS 列表遮挡：已修一处真 bug（`.sidebar:not(.rss-sidebar)` 漏排除列表根元素，
  模拟视口 57px→604px），但 HP 未重新部署导致修复未达真机（生产 CSS 指纹不一致实锤）；
  真机叠加因素（safe-area/dvh/SW 缓存）Phase 1 继续取证。
- 颜色令牌化较好（硬编码色 ≤3 处/文件）；碎片化主力=间距/字号/布局魔法数内联。
- 死代码：桶文件 index.ts 在用但含死转口行；粗 grep 误报率高，清理必须
  import-graph 工具（knip 6.32.2 已验证可用）+人工双验。

## 方案内容（4 批次）

### 批次 1 · 部署验证 + 真机取证
deploy.sh 部署 main 到 HP → 老板真机复测遮挡 → 仍存在则按根因清单继续排查。

### 批次 2 · 断点与视口体系统一 + RSS 移动端专项（范围按三端适配审计细化）
- **TabBar 覆盖修复【高置信度】**：`.page:has(.rss-pane)` 高度公式只减顶栏未减
  BottomTabBar(56px)，文档总高=100dvh+56px，列表最后一行被固定底栏盖住；
  RssReader 有底部补偿而 RssArticleList 没有——修复不对称。
  方向：公式补减 tabbar 或给列表滚动容器补 padding-bottom
- **通知横幅驻留【中高】**：iOS<16.4 无 Notification API → 横幅永不消失且无
  flex-shrink:0，恒吃 ~41px；需加 API 存在性守卫或可关闭状态
- 断点单一源：CSS ≤768 与 JS useIsMobile 对齐；PlayerPage 的 1023/1024 主断层
  与其他页 769/768 分裂统一；useMediaQuery 冗余子集段清理；空 `.rss-list {}`
  死规则清除（index.css:1483-1485）
- 兼容兜底：`:has()`/dvh 不支持时的回落路径明确化（iOS<15.4）
- 真机回归清单 5 场景（含横竖屏对照、无痕模式对照实验）

### 附：三端适配审计其他确认缺陷（并入对应批次）
- MetadataEditDialog 内联 minWidth:400 在 375px 屏横向溢出（→批次 4 内联治理）
- TokenPromptDialog minWidth:360 同类（→批次 4）
- LibrariesPage 硬编码 calc(100vh - 120px) 同款顶栏假设问题（→批次 2）
- viewport-fit=cover 未设置：全站 safe-area 代码恒 0（当前浏览器形态无害，
  主屏 PWA 化前必须补 meta，否则 TabBar/Sheet 撞 Home 指示条）

### 批次 3 · 死代码速删
桶文件死转口行修剪（knip 报 13 条逐一复核）；index.css 死类抽查清理；
bundle 主 chunk 328KB → ≤300KB。

### 批次 4 · 设计令牌补全 + 内联样式治理 + 同类组件归一
间距/字号/圆角令牌补全；376 处内联样式分页处置（纯展示迁移类/
动态值保留注释/重复删除）；按钮/badge/loading 多套实现归一。

## 验收标准

- [ ] 批次 1：HP 生产 CSS 指纹更新；老板真机复测有明确结论
- [ ] 批次 2：JS 与 CSS 断点一致；真机回归清单全过
- [ ] 批次 3：主 chunk ≤300KB；vitest 全绿零回归
- [ ] 批次 4：内联样式较基线下降 ≥50%；页面结构模板化文档落地
- [ ] 全程：vitest ≥70% 覆盖率门禁不降；clippy/fmt 后端门禁不受影响

## 验收记录

### 批次 3 · 2026-08-24
- [x] index.css 两族弹窗死样式 ~287 行 + 零散死类 13 项删除
- [x] PlayerPage.css 旧桌面布局 19 规则删除（904→767 行）
- [x] 桶文件 11 条死转口行修剪
- [x] vitest 381 全绿；播放页双视口渲染正常；已部署 HP（CSS DvLgw5CJ）
- 备注：bundle 主 chunk 328→321KB，≤300KB 目标顺延批次 4；
  孤儿端点 2 个待排除多端调用后处理

### 批次 2 · 2026-08-24
- [x] ≤768 sidebar 规则链合并（删 200px/180px 两套打架限高与空死规则）
- [x] RssArticleList 移动端 TabBar 底部补偿（对齐 RssReader 做法，审计 #1）
- [x] 通知横幅 Notification API 守卫（审计 #2）
- [x] useMediaQuery 冗余段清理 + 测试断言同步
- [x] vitest 381 全绿；Playwright 三视口回归符合预期
- [ ] HP 部署收尾验证

### 批次 1 · 2026-08-24
- [x] deploy.sh 全量部署：生产 CSS 指纹 DLJPXQhH → **D3RizBE5**（移动端遮挡修复上线）
- [x] 后端新二进制 05:32 重启，health ok，回滚备份在位
- [ ] 老板真机复测遮挡（验证步骤见 mx-plan-009 会话记录/draft 附录 D）——待老板反馈
