# 方案 · 视觉模板库（M3-3.1）

> 项目：xy · 编号：xy-plan-005 · 状态：已完成 · 作者：Claude（中枢） · 工具：Claude Code
> 批准：老板确认转卡 · 2026-08-17
> 创建：2026-08-17 · 更新：2026-08-17
>  关联卡：已归档（原引用 xy040, xy041, xy042 随 8-24 治理归档，见 docs/archive 与 RETIRED 记录）
> 关联方案：无
> 进度：3/3 (100%)
> 里程碑：M3 · 视频高表现力
> 子项目：3.1 视觉模板库
> 环境准备：mac2017 xianyu 业务仓可写；video-pipeline 可渲染（ffmpeg 在机）

## 目标

把 video-pipeline 的视觉模板从「3 场景 + 2 平台 + 4 prompt」扩成一套可复用、可区分、参数化的视觉模板库，让不同内容类型能产出不同视觉风格的竖屏视频。

## 背景

摸底确认 video-pipeline 已有模板基础：`templates/scenes/{minimal,vibrant,tech}.json`、`templates/platform/{douyin,xiaohongshu}.json`、`templates/prompts/{tool-tutorial,product-promo,project-story,tech-popular-science}.json`；hyperframes 试用骨架另有 `{minimal-white,glass-card,dark-tech}.html`。但模板集偏薄、风格区分度有限，且未参数化（一套模板难以适配多种内容）。M3 高表现力主线之一就是把视觉表现力做厚。

## 方案内容

三块：

1. **模板扩展**：把 hyperframes 已有的 glass-card/dark-tech 等视觉风格迁入/桥接到 video-pipeline 模板体系（或作为 scene 模板变体），扩充到目标模板集（≥6 套视觉风格，每套有明确风格标签）。
2. **模板参数化**：scene 模板支持参数化（配色/字号/动效强度/转场），同一模板可适配不同内容类型与平台；配置项进 `config.json`。
3. **模板测试**：每套模板产出一条样片，确认可渲染、风格可区分（视觉抽检），并纳入质量基线。

## 验收标准

- [x] ≥6 套视觉模板可渲染出样片，每套风格可区分（视觉抽检通过）
- [x] 模板参数化落地：同一模板可配置不同配色/动效产出不同效果
- [x] 每套模板样片纳入 `check_video_quality.py` 基线（码率/时长/分辨率达标）
- [x] 管线接口不破坏（`contracts.py` 四组 dataclass 对不变）

## 功能卡

### 模板扩展

目标：把视觉模板从 3 场景扩到 ≥6 套，风格可区分。

实现：梳理 hyperframes 已有模板（minimal-white/glass-card/dark-tech）与 video-pipeline scene 模板（minimal/vibrant/tech），补齐到 ≥6 套；每套定义风格标签（极简/玻璃拟态/暗黑科技/活力渐变…）；确认 ffmpeg 渲染路径可用。

验收：≥6 套模板各产出一条样片，视觉风格抽检可区分。

颗粒度：模板 JSON/HTML 扩展 + 渲染验证，多文件但每个独立。

依赖：无

架构位置：video-pipeline 模板层（scene/渲染）

### 模板参数化

目标：模板支持参数化配置，同一模板适配多种内容。

实现：scene 模板配置项（配色/字号/动效强度/转场）进 `config.json`；渲染读参数渲染不同效果；提供默认值保证不配也能跑。

验收：同一模板改参数产出不同视觉效果；不配参数走默认。

颗粒度：配置结构 + 渲染读取，单模块。

依赖：模板扩展

架构位置：video-pipeline 配置/渲染链路

### 模板测试与基线

目标：每套模板样片纳入质量基线，可回归。

实现：为每套模板生成样片入库 `samples/`（摸底显示 samples/ 目前为空，需真实样片）；`check_video_quality.py` 跑每套样片确认码率/时长/分辨率达标。

验收：≥6 套样片全量化达标，基线脚本输出通过。

颗粒度：样片生产 + 基线脚本跑通，单模块。

依赖：模板扩展, 模板参数化

架构位置：质量基线工具（check_video_quality.py）

## 转卡计划

模板扩展 / 模板参数化 / 模板测试与基线

## 备注

- 模板库是 M3「高表现力」的地基——视觉模板多、质量稳，后续渲染升级（3.3）才有对比基线。
- 与 006「质量量化加固」衔接：006 定量化标准，本方案产模板样片喂给基线。
