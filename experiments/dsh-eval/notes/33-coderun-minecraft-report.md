# 实验 33 · OpenCode CodeRun 模式首单实测（Minecraft 3D）

- **状态**：完成
- **环境**：2017（192.168.3.116）OpenCode · code 模型档位 · 中转站通道
- **日期**：2026-08-17
- **关联**：任务 #14；埋点计划见 [[32-instrumentation-plan]]；全流程问题见 [[31-formal-flow-issues]]

## 一、背景与目标

验证「OpenCode 用 CodeRun 模式（程序化编排）能否独立完成一个多步骤开发任务」。
选任务：3D 版《我的世界》HTML 小游戏（生成代码 → 部署内网 → 自检交付）。
CodeRun 是 DSH 专有术语，OpenCode 不认识，故把 CodeRun 转译为它听得懂的「程序化编排」指令（见 `/tmp/minecraft_prompt.txt`）。

## 二、指令转译（CodeRun → OpenCode 语言）

原始 CodeRun 要求（DSH 语义）：
- 程序化编排：写脚本一次编排，不逐轮敲工具
- 一次产出：能一次生成的完整文件不拆分多次编辑
- 并发意识：并行取证

转译后给 OpenCode 的核心指令（4 条可执行要求）：
1. 把多步骤工作写成一个或多个脚本（bash/python/node），脚本一次编排完成
2. 能一次生成完整文件的内容不要分多次编辑
3. 需要并行取证的步骤用脚本并发跑
4. 明确告知「你的执行方式本身是验收的一部分」

## 三、编排遵守度证据（run a6a1b7a0）

OpenCode 的产出是一个 **557 行单体编排脚本 `setup_and_deploy.sh`**，结构：

| 步骤 | 实现 | 证明 |
|---|---|---|
| 生成完整游戏 | `cat << 'EOF' > index.html` 一次写入 504 行完整游戏 | 头部 40 行即完整 heredoc |
| 端口冲突处理 | 循环检测 PORT，占用则 kill 占位 PID 并 +1 | `lsof -t -i :$PORT` 分支 |
| 起服务 | `nohup python3 -m http.server $PORT -d TARGET_DIR` | line 543 |
| 自检交付 | `curl -s -w %{http_code}` 校验 200，失败 exit 1 | 尾部 15 行 |

**执行时序**（opencode.log，2.7 分钟全流程）：
```
18:33:05  run 开始（写编排脚本）
18:35:03  chmod +x setup_and_deploy.sh → 执行
18:35:35  edit setup_and_deploy.sh（一次修正）
18:35:44  chmod → 重跑
18:35:49  curl -I http://192.168.3.116:8123 自检
```

**结论**：OpenCode **识别并遵守了程序化编排指令**——多步骤被封装进一个脚本一次编排完成，非逐轮敲命令；写→跑→修→重跑→自检只有 **1 轮迭代**。

## 四、效率指标

| 指标 | 数值 | 说明 |
|---|---|---|
| 全流程耗时 | ~2.7 分钟 | 18:33:05 → 18:35:49 |
| run 内事件数 | ~150 条 | 以权限评估事件为主，非纯工具调用 |
| 编排迭代轮次 | 1 轮 | 写→跑→1 次 edit→重跑→过 |
| 部署产物 | 单脚本 + 单 HTML | 无构建工具，零依赖下载（CDN three.js） |

> 注：精确工具调用数/token 消耗需 OpenCode 会话级埋点，当前仅能从权限事件反推——这正是 [[32-instrumentation-plan]] P0（Engine 埋点）要补的统计层。

## 五、代码质量

**功能完整度**（index.html 504 行，21KB，Three.js）：
- 程序化地形：`random` × 6 + 18 处 `for (let` 循环生成方块世界 ✓
- 第一人称：PointerLockControls + WASD + 空格跳 ✓
- 放置/破坏：左键 `button===0` 破坏、右键 `button===2` 放置，raycast/intersect 瞄准 ✓
- 物理：gravity + collision + velocity ✓

**缺陷记录（1 个，老板实测发现）**：
- 进入环节卡死：`#instructions` 设了 `pointer-events: none`，阻断点击 → PointerLock 无法触发；且回车无处理。
- 修复：`pointer-events: none→auto` + 补 `keydown` 任意键启动（一次性监听）。修复后老板复测通过（部署日志 02:45/02:53 两次 200 访问）。

## 六、部署交付

- 地址：`http://192.168.3.116:8123/index.html`（内网可访问）
- 自检：脚本内 curl 200 校验 + opencode 侧 `curl -I` 复核
- 老板实测：M1（192.168.3.140）两次访问 200，进入游戏体验后反馈 1 个 bug，修复后通过

## 七、技术指标汇总

| 维度 | 结论 | 置信度 |
|---|---|---|
| CodeRun 指令可转译给 OpenCode | ✅ 成立，OpenCode 能理解「程序化编排」并遵守 | 高 |
| 程序化编排产出 | ✅ 单体编排脚本 + 一次生成完整文件 | 高 |
| 编排质量 | ✅ 端口处理/自检/失败退出齐全，符合 CodeRun 范式 | 高 |
| 迭代收敛 | ✅ 1 轮修正即交付，优于逐轮交互 | 高 |
| 代码质量 | ⚠️ 功能齐但有 1 个交互 bug（pointer-events），需人工复测兜底 | 中 |
| 部署交付 | ✅ 内网可达、自检通过 | 高 |
| 调用量/耗时 | 2.7 分钟全流程；精确调用量缺埋点 | 中 |

## 八、结论

**OpenCode 具备用 CodeRun（程序化编排）模式独立完成多步骤开发任务的能力**：
1. 指令转译是前置条件——「CodeRun」术语要转成「写脚本一次编排」这类可执行要求；
2. 编排产出质量好（端口/自检/回滚意识都在），1 轮迭代即收敛，是 CodeRun 的核心收益；
3. 但代码质量仍需人工复测兜底（pointer-events 这类交互 bug 编排自检发现不了），印证 [[31-formal-flow-issues]] 机审环节不可省；
4. 精确调用量/token 统计缺口 → [[32-instrumentation-plan]] P0 落地是后续量化前提。

## 九、清理

按老板要求，本实验属临时任务：报告落档后删除 `/Users/fan/ccc-test-minecraft/` + 停 8123 服务。证据已全部固化在本报告。

> 测试产物为一次性任务，不保留代码副本（避免污染 CCC 业务仓）。
