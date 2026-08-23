# 方案 · 视频高表现力二期（M5）

> 项目：xy · 编号：xy-plan-008 · 状态：待验收 · 作者：OpenCode（集群架构） · 工具：OpenCode
> 批准：老板定里程碑 · 2026-08-20
> 创建：2026-08-20 · 更新：2026-08-24
> 关联卡：xy059（html-preview CLI · 已回写）；其余功能卡待出, xy059
> 关联方案：无（承接 M3 xy-plan-005/006/007 已落地部分）
> 进度：2/2 (100%)
> 里程碑：M5 · 视频高表现力二期
> 子项目：5.1 帧渲染器 / 5.2 模板库规模化 / 5.3 A-B 质量评估
> 环境准备：mac2017 xianyu 业务仓可写；Hyperframes 引擎已集成（xy047/xy048）；html_scene 骨架已存在（agent/schema/renderer）；Playwright 需安装验证

## 目标

补齐 HTML→Video 主链路缺失段：**Playwright 帧渲染器**（HTML 场景→帧序列→视频合成，缺 frame_capture/html_composer）——目前场景生成（html_scene）与 Hyperframes 渲染已落地，但 HTML→帧→视频的稳定管线缺失；模板库规模化 + **A/B 质量评估闭环**（多模板同主题对比 + 人工打分 + 质量报告）；`xianyu html-preview` 预览命令。M7 之前的质量优化主线。

## 背景

M3 已交付：视觉模板库（xy-plan-005）、质量量化（xy-plan-006，码率 0.12→3.7 Mbps）、渲染引擎升级（xy-plan-007，Hyperframes 集成 + PIL 线程池回退 + glass-card/dark-tech 风格）。但 v2-plan 的 Phase 3（Playwright 帧渲染器）与 Phase 5（模板+A/B 评估）未落地：`frame_capture.py`/`html_composer.py` 不存在，模板未规模化，无 A/B 对比流程，无 `html-preview` CLI。

## 方案内容

三块：

1. **Playwright 帧渲染器**：`video-pipeline/stages/scene/` 扩展 HTML 场景→帧序列→视频合成（1920×1080/1080×1920 竖屏为主，30fps，场景按口播时长计算帧数，CSS 动画自动执行）；Playwright 不可用自动降级现有管线。
2. **模板库规模化 + html-preview**：预设模板扩充（≥3 套新风格，承接 glass-card/dark-tech），写 `xianyu html-preview <task_id>` CLI 预览 HTML 场景。
3. **A/B 质量评估**：同主题多模板出片对比 + 人工打分流程 + 质量报告产出（复用 check_video_quality 量化标准）。

## 验收标准

- [ ] HTML 场景可经帧渲染器产出成片，质量量化达标（复用 xy-plan-006 标准）
- [ ] Playwright 不可用/失败时自动降级，生产不中断
- [ ] ≥3 套新模板入库，`html-preview` CLI 可预览任意任务场景
- [ ] A/B 对比可产出结构化报告（同主题 ≥2 模板出片 + 量化指标 + 人工打分）

## 功能卡

### Playwright 帧渲染器

目标：HTML 场景→帧序列→视频合成稳定管线。

实现：`video-pipeline/stages/scene/` 新增 frame capture（Playwright headless 截帧，按口播时长定帧数，CSS 动画等待）+ 帧序列 FFmpeg 合成；异常降级现有渲染；补测试。

验收：任一样片经帧渲染器出片且质量量化达标；模拟 Playwright 不可用验证降级路径。

颗粒度：渲染管线新模块 + 降级，多文件。

依赖：无（承接已落地 Hyperframes）

架构位置：video-pipeline/stages/scene/（frame_capture + html_composer）

### 模板库规模化 + html-preview

目标：模板扩充 + 场景预览命令。

实现：新增 ≥3 套模板（风格承接 glass-card/dark-tech 方向）；CLI 子命令 `xianyu html-preview <task_id>` 渲染 HTML 场景并本地打开/输出预览图。

验收：模板库 ≥6 套（现有 3+新 3），preview 命令对任意已生成场景可用。

颗粒度：模板文件 + CLI 子命令，多文件。

依赖：无

架构位置：templates/ + src/xianyu/cli 或等价入口

### A-B 质量评估

目标：多模板同主题对比 + 人工打分 + 报告。

实现：`render_all_templates.py`（已有）扩展为 A/B 模式：同主题用 ≥2 模板出片，`check_video_quality.py` 量化 + 人工打分表（结构/画面/文案适配/整体），产出对比报告入库。

验收：A/B 报告结构化可复现（量化 + 打分），≥1 组对比完成。

颗粒度：评估脚本 + 报告模板，多文件。

依赖：模板库规模化

架构位置：video-pipeline/scripts/ + samples/

## 转卡计划

Playwright 帧渲染器 → 模板库规模化 + html-preview → A-B 质量评估（M6 全部卡验收后开始）

### 依赖链与并行关系（2026-08-20 定稿）

```
xy056 (5.1 Playwright 帧渲染器)  ← 无依赖，M6 全部验收后启动
xy057 (5.2 模板库规模化 + html-preview) ← 无依赖，M6 全部验收后启动
  └── xy058 (5.3 A-B 质量评估)   ← 依赖 xy057 合入（评估依赖模板库规模化）

并行规则：
- xy056 与 xy057 代码无交集（video-pipeline/stages/scene/ vs templates/+CLI），理论可并行
- **但 xy 业务仓 isolation.max_concurrent=1（registry.yaml）**，同仓禁止并发执行——实际全部顺序出卡：xy056 → xy057 → xy058
- xy058 必须等 xy057 合入后才能开发
- M5 与 M6 不并行：方案定序 M6 优先（展示台先让产出可见），M5 在 M6 全部卡验收后开始
- 每张卡独立验收：一张合入后再出下一张（禁止批量建卡）
```

## 备注

- 执行顺序：M6（展示台）优先，M5 随后——展示台先让产出可见，M5 再提升产出质量。
- 帧渲染器为 html_scene（已有）+ Hyperframes（已集成）之间的缺失段，合拢后 HTML→Video 主链路完整。
- Playwright 安装为环境前置（2017 需 `pip install playwright` + chromium），卡内自验证。