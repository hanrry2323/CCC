# 正式流程跑测暴露的派发链路问题（待全流程梳理）

- **状态**：记录（流程跑通后全流程梳理）
- **来源**：hp009 正式流程跑测（2026-08-16）
- **处置方向**：不在单点修，纳入全流程梳理，从总体架构/流程层解决

## 问题 1 · 执行体命令解析与运行环境不一致

**现象**：engine 派发时 `opencode` 命令 `[Errno 2] No such file or directory`。opencode 实际装在 `/Users/fan/.npm-global/bin/opencode`（fan shell PATH 里有），但 engine 走 launchd 环境（PATH 不含该目录）。

**单点修复**：executors.json 命令改全路径 `/Users/fan/.npm-global/bin/opencode`（claude 同理）。

**架构层根因（待梳理）**：
- 执行体注册表的「命令」字段假设**声明环境**与 **engine 运行环境（launchd）** 的 PATH 一致——实际不一致。
- 缺「命令存在性校验」：派发前没检查命令可解析，启动失败才暴露。
- launchd 服务环境变量（PATH）与用户 shell 环境是两套，执行体配置没感知这个差异。

## 问题 2 · worktree_base 为空导致命令构造坏

**现象**：`--dir {worktree}` 占位为空（开发执行体 worktree_base=""），命令变成 `--dir "" <prompt>` → opencode `Failed to change directory to 请严格按任务卡...`。

**单点修复**：给 CLI 执行体（开发/维护/验收）配 `worktree_base=/Users/fan/program/CCC-wt/<task>`。

**架构层根因（待梳理）**：
- worktree_base 是**派发必需项**（worktree 隔离是 2026-08-12 升级的硬约束），但 executors 配置**不强制**（可空），命令构造也不防御空占位。
- build_command 对「空占位符」无防御——`{worktree}` 空时生成了非法命令，而不是省略 `--dir` 或报「配置缺失」。
- 缺少「executors 配置完整性校验」：worktree_base 空应该在校验阶段拦截，而不是派发阶段炸。

## 共同根因（全流程梳理切入点）

这两个问题都是**派发链路的「声明-校验-构造」三层缺口**：
1. **声明层**：executors.json 允许不完整配置（命令可解析性、worktree_base 必需性未强制）。
2. **校验层**：注册表加载只校验占位符合法，不校验「命令存在 + 必需字段非空」。
3. **构造层**：build_command 对空占位无防御，生成非法命令才在运行时失败。

**建议梳理方向**：把「执行体注册 → 配置完整性校验 → 命令构造 → 运行环境」作为一条链路，在架构层加：
- 执行体注册时校验命令可解析（PATH/绝对路径）+ 必需字段完整
- build_command 对空占位防御（省略或报错）
- 运行环境（launchd PATH）与执行体声明对齐或显式声明

## 关联

- 这两个问题是**真实流程跑测**（CodeRun 模式验证卡）暴露的——正好证明「流程内测试」的价值：不跑真实卡，这些派发缺陷不会浮现。
- 全流程梳理时一并处理，不单点打补丁。
