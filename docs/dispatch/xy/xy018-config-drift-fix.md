# 任务卡 xy018 · 配置漂移修复与文档对齐（OpenCode 执行）

> 关联：ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

配置漂移修复与文档对齐（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `video-pipeline/**/*.py`
- `video-pipeline/config.json`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. config.json 的 width/height 真实透传到 stages/scene/generator.py 渲染尺寸（当前写死 1080x1920），验证：改 config 尺寸后渲染帧尺寸随之变化
2. config.json 的 fps 真实透传 FFmpeg 拼片（当前死锁 24 FPS），scene/compose 两处对齐 config 值
3. 06-audio-merge 阶段现状核实并文档对齐：确认已 inline 进 05-compose 则在 .ccc/decision.md 标注，codebase.md 等旧文档不再描述第六阶段
4. 字幕时间估算：TTS 无 WordBoundary 时兜底估算保留但标注为近似，不改现有估算精度逻辑（防回归），仅文档说明
5. 全链路 1 条真实成片验证：video-pipeline 跑通产出 final.mp4，码率 ≥3.5Mbps、文件 ≥9MB、尺寸与 config 一致

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
