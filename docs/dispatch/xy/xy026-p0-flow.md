# 任务卡 xy026 · 测试门禁修复与文档除债（P0-FLOW 前置）（OpenCode 执行）

> 关联：xy PRM P0-FLOW 前置（xy024 意图重建） · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-09

## 目标

在 xianyu 仓修复测试覆盖率门禁并清理文档除债，为 PRM P0-FLOW 关卡扫清前置（本卡意图源自被清理的 xy024 打转卡，重建为干净卡）。

## 红线（先看）

1. **禁止改业务代码**：只动 pyproject.toml 门禁配置与 docs 文档，不改 `src/**`、`video-pipeline/**` 业务逻辑。
2. **必须真实运行**：pytest 全量必须真实执行并 exit 0，禁止在回写区自述"通过"而无输出证据。
3. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `pyproject.toml`（覆盖率门禁阈值）
- `docs/07-内容生产/视频生产规范.md`（重写对齐真实管线）
- `docs/08-运维/部署指南.md`（修复错误路径与 launchd 描述）
- `.ccc/decision.md`（如需记录门禁决策）

业务仓路径：`/Users/fan/program/apps/xianyu`（Mac2017）。

## 步骤

1. 进入 `/Users/fan/program/apps/xianyu`，先跑 `git status -sb` 确认工作区干净、基于最新 main。
2. 读 `pyproject.toml` 当前覆盖率门禁（原 `--cov-fail-under=80`，实际覆盖率约 29.16%）：调低为合理阶段性阈值（如 25 或按实测值附近定档），并记录调整理由到 `.ccc/decision.md`。
3. 运行 `pytest` 全量（预计 677 用例）真实执行，确认功能性测试全 PASSED 且 exit 0；覆盖率数字如实记录，不改断言。
4. 重写 `docs/07-内容生产/视频生产规范.md`：删除 ChatTTS/PaddleSpeech/SadTalker/AnimateDiff/Fooocus 等作废工具描述，对齐当前真实管线（edge-tts 配音 + PIL 绘制帧 + FFmpeg 合成 + MPT/本地 Ollama 文案）。
5. 修复 `docs/08-运维/部署指南.md`：第 7 行 `cd /Users/apple/program/xianyu` 错误路径改为动态/正确路径；launchd 描述对齐真实 12 个 plist 清单（或按当前实际状态如实描述）。
6. 校验文档与代码一致：`grep -rn "SadTalker\|AnimateDiff\|Fooocus\|ChatTTS" docs/07-内容生产/ docs/08-运维/` 仅可出现在「已弃用」说明。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
8. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. `pyproject.toml` 覆盖率门禁已调低为合理阶段性阈值（有调整理由），`pytest` 全量真实运行 exit 0（回写区附 pytest 实际输出尾部）
2. `docs/07-内容生产/视频生产规范.md` 已重写：无作废工具名（SadTalker/AnimateDiff/Fooocus/ChatTTS 仅可出现在「已弃用」说明），管线描述与真实链路一致
3. `docs/08-运维/部署指南.md` 错误路径已修复、launchd 描述与实际一致
4. 零业务代码改动；探针：`git -C /Users/fan/program/apps/xianyu status -sb` 只含白名单文件改动；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
