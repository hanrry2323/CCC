# 任务卡 xy017 · 存储路径统一规划与硬编码消除（OpenCode 执行）

> 关联：ccc-plan: xy 审计问题修复：路径规划/漂移修复/生产补漏 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-07

## 目标

存储路径统一规划与硬编码消除（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `scripts/daily/*.sh`
- `scripts/daily/generate_video.py`
- `scripts/daily/run_daily_video.sh`
- `video-pipeline/**/*.py`
- `video-pipeline/config.json`
- `.ccc/storage-layout.md`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. xianyu 仓新增权威目录规范文档 .ccc/storage-layout.md（或等价），定义：成片/中间产物/素材/BGM/credentials/日志 六大类路径
2. 生产脚本中所有硬编码 /Users/apple/program/xianyu（M1 路径）替换为变量推导（基于仓库根），grep 验证：grep -rn '/Users/apple' scripts/ video-pipeline/ 无残留（注释除外）
3. BGM 数据仓路径 data/bgm 写入规范文档，含文件类型/时长要求
4. credentials 目录规范：密钥文件仅存 .gitignore 覆盖的路径，禁止入库

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
