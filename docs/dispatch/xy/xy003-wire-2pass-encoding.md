# 任务卡 xy003 · 接入2pass VBR编码到生产链路（OpenCode 执行）

> 关联：阶段 3 P1 · 执行体：OpenCode · 验收：Claude Code · 状态：待分派· 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

把 `xianyu/video/encoding.py` 里的 `run_2pass_encoding` 异步二遍高质量编码逻辑，真正接进 xianyu 仓的视频生产调用链（替代当前的单遍/普通编码，并在高质量预设下生效）。

## 红线（先看）

1. 只动 2017 `/Users/fan/program/apps/xianyu` 仓；不碰平台（CCC server/engine/board）与其他项目。
2. 不直推 main；走卡内分支 `codex/xy003-wire-2pass-encoding`。
3. 必须包含真实的 2pass FFmpeg 进程调度，不得用 dummy/mock 脚本冒充的高质量编码。
4. 禁止在 CCC 仓新建业务深文档；本卡只改 xianyu 仓。

## 范围

- xianyu 仓内视频渲染/合成逻辑（如 `orchestrator/` 或 `video_pipeline/` 中负责调用 FFmpeg 的模块）。
- 建立高质量编码模式开关（如 `--high-quality` 或在 schema 预设中指定），仅在高质量模式下走 2pass 编码，普通模式保持不变防退化。
- 配套修改，让高质量产物落到既有 `workspace/outputs/video/` 目录。

## 步骤

1. **先定位调用点（不得跳过）**：读 xianyu 仓代码，定位当前视频渲染/编码在哪里触发（查找 FFmpeg 运行入口，如 subprocess、sh、或既有 runner 模块），并在回写区「接入定位」说明现状。
2. **接入调用链**：把高质量模式分支接上 `run_2pass_encoding`（Pass 1 跑完落日志，Pass 2 最终生成，清理临时 log），实现无缝替换。
3. **回归与新增测试**：对调用点模块新增高质量模式单测，确保既有普通模式不坏、高质量 2pass 能正常在 Mock FFmpeg 状态下跑完。
4. **探针实测**：真机运行一次高质量编码命令（可输极短测试视频），确认最终在 `workspace/outputs/video/` 下产生 2pass 编码后的视频文件。
5. commit+push 到卡内分支（勿直推 main）；卡头改为「已回写」。
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. 高质量模式下，视频渲染逻辑能成功调用并走完 `run_2pass_encoding` 两遍 FFmpeg 编码（附实测命令与带 Pass 1 + Pass 2 的日志截图或文本）。
2. 在 `workspace/outputs/video/` 目录下真实产生了 2pass 高质量编码视频，且能正常播放/验证（附文件路径与大小）。
3. 新增/更新单元测试，全量 pytest 100% 通过（除去外部网络 marked skipped 项）。
4. 现状定位写清：说明了原本在哪里编码，现在怎么分流进 2pass 高质量分支。

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 回写区

**执行体**：OpenCode · 日期：
