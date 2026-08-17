# 方案 · 渲染引擎升级（M3-3.3）

> 项目：xy · 编号：xy-plan-007 · 状态：部分执行 · 作者：Claude（中枢） · 工具：Claude Code
> 批准：老板确认转卡 · 2026-08-17
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：xy046, xy047, xy048
> 关联方案：无
> 进度：1/3 (33%)
> 里程碑：M3 · 视频高表现力
> 子项目：3.3 渲染引擎升级
> 环境准备：mac2017 xianyu 业务仓可写；video-pipeline 可渲染（ffmpeg 在机）；可选 node 环境（remotion）

## 目标

评估 video-pipeline 的渲染引擎路径（现状 ffmpeg 主路径 + hyperframes/remotion 两个试用骨架），选定高表现力主路径并落地，产出质量 ≥ ffmpeg 基线的样片，且不破坏管线接口。

## 背景

摸底确认：主路径 `render_engine: "ffmpeg"`（PIL/numpy 逐帧 + ffmpeg 合成，已产出达标样片）；另有**两个试用骨架**——`video-pipeline/hyperframes/`（HyperFrames 0.6.97，3 模板 + 1 真实 render `hyperframes_2026-08-08_07-47-05.mp4`）和 `video-pipeline/remotion/`（React Remotion，仅 package.json + `src/index.tsx`，无 node_modules，未落地）。M3 高表现力需要「表现力更丰富的渲染路径」，但**不能为了换引擎而破坏已达标的质量与管线接口**——先评估、后选定、再落地。

## 方案内容

三块：

1. **引擎评估**：对比 ffmpeg（现状主路径）/ hyperframes（HTML 组合渲染，glass 等模板）/ remotion（React 动画，未落地）三条路径——质量上限、表现力（动态镜头/转场/特效）、维护成本、与 video-pipeline `contracts.py` 的兼容度；产出评估结论（选哪条为主 / 保留 ffmpeg + 模板化）。
2. **选定路径落地**：按评估结论落地——若升 hyperframes/remotion 为主，则接入 scene 阶段（`contracts.py` 的 `SceneInput→SceneOutput` 接口不变，换实现）；若保留 ffmpeg，则把 hyperframes 视觉风格迁入 ffmpeg 模板体系（与 005 模板库衔接）。
3. **集成验证**：选定路径产出样片，质量 ≥ ffmpeg 基线（对照 006 质量报告），管线接口不破坏。

## 验收标准

- [ ] 引擎评估结论落文档（三条路径对比 + 选定理由），有量化依据
- [ ] 选定路径产出样片，质量 ≥ ffmpeg 基线（对照 `check_video_quality.py`）
- [ ] `contracts.py` 四组接口不变，video-pipeline 五阶段流程不破坏
- [ ] 产出样片与模板库（005）/质量基线（006）衔接，纳入统一质量报告

## 功能卡

### 引擎评估

目标：三条渲染路径（ffmpeg/hyperframes/remotion）对比，产出选定结论。

实现：各自跑一条样片（ffmpeg 已有、hyperframes 已有 1 条、remotion 补装 node_modules 试跑或静态评估）；对比质量上限/表现力/维护成本/接口兼容；产出一页评估文档。

验收：评估文档有量化对比（质量指标 + 表现力 + 成本）与选定结论。

颗粒度：调研 + 对比样片 + 文档，覆盖三路径。

依赖：无

架构位置：video-pipeline 渲染层（决策文档）

### 选定路径落地

目标：按评估结论把选定渲染路径接入 video-pipeline。

实现：若升 hyperframes/remotion 为主 → 接 scene 阶段（实现替换，接口不变）；若保留 ffmpeg → 把 hyperframes 视觉风格迁入 ffmpeg 模板（配合 005）。接入后 `python3 pipeline.py` 端到端可跑。

验收：选定路径在 video-pipeline 内可产出样片，`pipeline.py` 端到端通过。

颗粒度：渲染实现接入，单模块。

依赖：引擎评估

架构位置：video-pipeline scene/渲染阶段

### 集成验证

目标：选定路径样片质量 ≥ ffmpeg 基线，接口不破坏。

实现：产样片跑 `check_video_quality.py`（对照 006 质量报告）确认达标；跑 pipeline 契约测试（`contracts.py` 相关测试）确认接口不破坏；样片入库 `samples/`。

验收：样片质量报告 ≥ 基线；契约测试通过；样片入库。

颗粒度：验证 + 样片，多文件产出。

依赖：引擎评估, 选定路径落地

架构位置：video-pipeline 集成 + 质量基线

## 转卡计划

引擎评估 / 选定路径落地 / 集成验证

## 备注

- 本方案是 M3 高表现力的收尾——以「表现力提升但质量不倒退、接口不破坏」为底线，不是为换引擎而换引擎。
- 与 005（模板库）/006（质量量化）强衔接：005 供风格模板、006 供对比基线，本方案在其上定渲染主路径。
