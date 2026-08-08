# 任务卡 xy024 · 遗留治理③：测试门禁修复与文档除债（P0-FLOW 前置）（OpenCode 执行）

> 关联：ccc-plan: xy PRM 批2：测试门禁修复与文档除债 · 执行体：OpenCode · 验收：OpenCode · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-08-08

## 目标

遗留治理③：测试门禁修复与文档除债（P0-FLOW 前置）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注

**机审打回（2026-08-08）**：机审不通过，打回重派。需修复：
1. pytest 3 例失败：（bgm_tags.exclude 排除逻辑/路径处理缺陷，bright.mp3 未被排除命中）
2. node 环境缺失导致 openclaw 2 例失败（环境问题，可注明或补装）
3. 回写区「退出码 0 / 667 passed」与实测（3 failed）不符，须如实修正
超 scope 说明：bgm_tags 源码修复属本卡必办项（P0-FLOW 关卡），node 环境可注明。`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `pyproject.toml`
- `docs/07-内容生产/视频生产规范.md`
- `docs/08-运维/部署指南.md`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. pyproject.toml 覆盖率门禁 --cov-fail-under=80 调低为合理阶段性阈值（如 25 或按实际 29.16% 附近定），pytest 全量运行 exit 0（不回写区自述，必须真实运行输出）
2. pytest 全量 677 用例收集并运行：功能性测试全 PASSED（沿用 xy020 实测结论），exit 0；覆盖率数字如实记录不改断言
3. docs/07-内容生产/视频生产规范.md 重写：删除 ChatTTS/PaddleSpeech/SadTalker/AnimateDiff/Fooocus 等作废工具描述，完整对齐当前真实管线（edge-tts 配音 + PIL 绘制帧 + FFmpeg 合成 + MPT/本地 Ollama 文案）
4. docs/08-运维/部署指南.md 修复：第 7 行 cd /Users/apple/program/xianyu 错误路径改为动态/正确路径；launchd 描述从 3+4 改为真实 12 个 plist 清单（或按当前实际状态如实描述）
5. 文档改动与代码一致：grep 文档中无已作废工具名（SadTalker/AnimateDiff/Fooocus/ChatTTS 仅可出现在'已弃用'说明）
6. 改动在 codex/xy024-* 分支提交 push，回写区列出 pyproject 改动 diff + 文档重写要点 + pytest 实际输出尾部

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
