# 方案 · 断裂点修复（M2-2.2）

> 项目：xy · 编号：xy-plan-003 · 状态：待排期 · 作者：Claude（中枢） · 工具：Claude Code
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：无
> 关联方案：无
> 里程碑：M2 · 生产就绪
> 子项目：2.2 断裂点修复
> 环境准备：mac2017 xianyu 业务仓可写；openclaw-plugin 目录可编译

## 目标

修复摸底发现的三个断裂点——openclaw-plugin 路径硬编码、daily-video 中文 TTS 缺失、企微告警占位——让既有能力真正可运行，而不是「代码在但跑不通」。

## 背景

摸底（2026-08-17）发现三个实际断裂点：
1. **openclaw-plugin 路径硬编码**：`openclaw-plugin/src/index.ts:5` 写死 `XIANYU_ROOT="/Users/apple/program/xianyu"`，但 xianyu 业务仓实际在 Mac2017 `/Users/fan/program/apps/xianyu`——路径不存在，插件必然失败。
2. **daily-video 中文 TTS 缺失**：`DEPLOY_MAC2017.md` 记录 Mac2017 缺中文 `say` voice（`Flo 中文 not found`），5 个 daily slot 曾跑空生成**无声视频**。推荐方案 A = 改用 edge-tts（`src/` 已有 edge-tts 依赖与 tts Worker）。
3. **企微告警占位**：`WECOM_WEBHOOK` 未填真值，`core/notify` 自动跳过告警——生产事故无通知。

## 方案内容

三个断裂点各一张功能卡：

1. **openclaw-plugin 路径修正**：`XIANYU_ROOT` 改为 `/Users/fan/program/apps/xianyu`（或改动态定位——从环境变量/包位置推导），编译通过。
2. **daily-video TTS 通道切换**：视频生产的 TTS 从 `say`（macOS 系统语音）切到 edge-tts（网络 TTS，中文质量更高），消除无声视频。
3. **企微告警接线**：`WECOM_WEBHOOK` 填真值（或标注待老板提供 → 配置占位但代码就绪、可随时启用），`core/notify` 告警通道可用。

## 验收标准

- [ ] openclaw-plugin 路径在 Mac2017 可解析（`XIANYU_ROOT` 指向存在的业务仓），`dist/` 可编译
- [ ] daily-video 产出有声视频（中文配音），无「Flo 中文 not found」错误
- [ ] 企微告警代码就绪（webhook 配置后即可触发），配置项有明确标注

## 功能卡

### openclaw-plugin 路径修正

目标：修复 `XIANYU_ROOT` 硬编码指向不存在的路径，使 openclaw 插件能找到 xianyu 业务仓。

实现：`openclaw-plugin/src/index.ts:5` 的 `XIANYU_ROOT` 改为 `/Users/fan/program/apps/xianyu`，或改为动态推导（优先环境变量，回退包位置）；重新编译 `dist/`。

验收：Mac2017 上插件可定位业务仓；`xianyu_run` 工具可调起。

颗粒度：单文件常量修正 + 重新编译，无逻辑改动。

依赖：无

架构位置：openclaw-plugin 接入层（xianyu → openclaw skill 桥）

### daily-video TTS 通道切换

目标：消除 daily-video 无声视频——中文配音从 macOS `say` 切到 edge-tts。

实现：定位 daily-video 的 TTS 调用点（`src/xianyu/video/` 或相关脚本），从 `say` 切到 edge-tts（复用 `src/` 已有 edge-tts 依赖与 tts Worker 的通道）；无网/失败时保持兜底提示。

验收：产出一条带中文配音的视频，ffprobe 确认含音频流且非静音。

颗粒度：TTS 调用点切换 + 依赖确认，单模块。

依赖：无

架构位置：视频生产链路（TTS 阶段）

### 企微告警接线

目标：`WECOM_WEBHOOK` 从占位到可用的告警通道。

实现：确认 `core/notify.py` 的 webhook 调用点；`WECOM_WEBHOOK` 填真值（老板提供）或标注「待配」，确保代码就绪（配置后即触发），`.env.example` 对齐。

验收：配置 webhook 后手动触发一次告警成功（或代码路径已验证可触发）。

颗粒度：配置接线 + 通道验证，单模块。

依赖：无

架构位置：core/notify（告警推送）

## 转卡计划

openclaw-plugin 路径修正 / daily-video TTS 通道切换 / 企微告警接线

## 备注

- 企微 webhook 真值依赖老板提供；若暂无可给，该卡验收降为「代码就绪 + 标注待配」，不阻塞 M2 完成。
- 三个断裂点均不涉及发布（D4），与老板定的「先专注生产」范围一致。
