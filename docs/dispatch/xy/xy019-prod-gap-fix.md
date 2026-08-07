# 任务卡 xy019 · 生产补漏：Pexels Key 部署与 BGM 校验与调度核实（OpenCode 执行）

> 关联：ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

生产补漏：Pexels Key 部署与 BGM 校验与调度核实（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `scripts/daily/generate_video.py`
- `scripts/daily/*.sh`
- `.env.local`
- `.ccc/ops.md`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. PEXELS_API_KEY 来源落实：2017 侧 .env.local（被 .gitignore）写入真实 key（来源 M1 shared/credentials/pexels-001.json，执行体不得把 key 值提交任何 git 仓）
2. 验证 key 生效：PEXELS_API_KEY 存在时 generate_video.py --image-source pexels 单条探测可搜到图（网络可达时）；网络不可达则记录失败原因不阻塞
3. BGM 静态校验脚本产出：校验 data/bgm 下文件类型（mp3/wav/m4a）与时长（≥30s），输出校验报告
4. 调度现状核实并记录：2017 无 xianyu launchd plist、daily_video.log 为空、workspace/daily 不存在，报告里'每日5时段自动跑'与实际不符——产出核实结论写 .ccc/ops.md，标注真实调度状态（未运行/手动/缺失）
5. 双轨决策落账：.ccc/decision.md 记录老板决策'双轨保留同步开发，后续按视频质量与文章需求再定取舍'

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
