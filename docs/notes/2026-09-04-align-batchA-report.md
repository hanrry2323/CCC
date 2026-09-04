# 2026-09-04 重构批A：治理文档 P1 对齐 —— 执行报告

> 指令：`/Users/fan/.ccc/instructions/2026-09-04-align-batchA.md`
> 执行窗口：2017 Claude CLI（产线修复窗口）· 全程 `/Users/fan/program/CCC`（权威仓）
> 性质：8 文件纯文档改动，零代码行为变更；未重启引擎、未跑全量测试
> 对齐基准：① 插座理念（一切工具=插件，可随时换）② 三层分工（管理席=可替换调度插件；前段执行=DSH；后段执行=CC CLI / phase2）③ 合入默认自动（phase2 CC），老板保留否决/打回
> 状态：✅ 全部完成并已 push origin main

## 一、每文件改动点

### 1. STARTUP-BRIEF.md
- §1 版本 v0.70.0 → v0.71.0（:4）
- §1 席位段（:20-25）：删 OpenCode/Codex 绑定；改为「开发/维护=前段 DSH｜审核/验收/合入/部署=后段 CC CLI（phase2）｜管理席=可替换调度插件（现役外脑）」；删「Codex=出卡/裁决」句；「合入批准=人审 diff 后唯一常规动作」→「合入默认 phase2 自动执行；老板保留否决/打回」；加一行「绑定只认 `server/config/executors.json`，随时可换」
- :29 cwd 铁律 →「CCC 权威仓=2017 `/Users/fan/program/CCC`；M1 副本已退役（2026-08-22）」
- :35 勿再说清单 → 追加「现役绑定只认 `executors.json`；DSH/CC CLI 为现役插件，OpenCode/Codex/桌面端为退役/休眠」（原「OpenCode 已禁用」条目在重启基线中不存在，顺带修正相近硬绑定表述）
- :44「3 个 launchd 服务」→「2 个（com.ccc.web-server + com.ccc.engine；board-scheduler 已收敛进 engine）」；§4 控制面同步改两服务，移除 `python3 -m server.board.export` 换成注释「board-scheduler 已收敛进 engine」
- :127-130 `claude -p` 示例 →「出口变量以 `config.env` / wrapper 为准；`claude -p` 裸调不作机审通道」
- :120 R-15 括号示例 →「指令直改（CLI）+ phase2 合入」
- :106 任务卡 glob `T<n>` → `<prefix>/<prefix><NNN>`（相邻同源错误顺手改）

### 2. docs/INDEX.md
- §0 定位声明（:19）：「DSH 已登记接入为自动化值班组件」→「现役插件登记见 `server/config/executors.json`（前段 DSH / 后段 CC CLI，均可换）」；决策源路径改 qx-map 归档
- 北星 A/B/C（:23-25）：A 加「老板/外脑逐张拟卡指令为合法单卡通道」；B 合入口径按基准 3 改；C 删「3 个人审节点」硬表述
- :33 契约 v1 路径改 qx-map 实际路径 `__archive__/dispatch-legacy-2026-08/ccc-refactor-contract-v1-2026-08-02.md`；方案定稿路径标 qx-map 归档
- :56 T31～T35 死链行删除（改为空行保留结构）
- :58 现行开发方向删「Codex 出卡驱动」双阶段模型 → 三层分工
- :91 版本行 v0.70 → v0.71
- :48 5c 行「合入批准」→「合入批准（默认 phase2 自动执行；老板保留否决/打回）」

### 3. references/red-lines.md
- :6 与 :8 自相矛盾统一：:6 删「6/11」，改为「红线本身仍现行（红线 1/3/12/R-15 等）」
- :9 验收席 Codex 表述 →「前段机审=DSH、后段验收/合入=phase2 CC CLI（均可换）」
- 红线 12 条目加授权例外句：「经老板明示授权的调度插件（授权须可追溯）不在此列」
- :163-164 mavis session new 残句 → 按 git 历史（77ef56884）恢复原文「不用 `mavis session new <agent>` 启动子会话（会导致非目标模型执行）」
- :269 VERDICT 停下要求补救残句 → 恢复完整「Planner 看到 report.md 缺 VERDICT 引用即停下，要求 Executor 补救后重跑」
- R-15 段（:646-655）：删 Hub 工作区 API 机制描述，改「R-15=禁 CCC 业务卡自我派发消费（仍有效）；CCC 本体改动=老板授权下指令直改（CLI），合入经 phase2 自动链（053 v2）」

### 4. docs/CCC-PRIME-DIRECTIVE.md
- §〇「已登记接入执行体：DSH」节（:35-37）→「现役插件登记见注册表；前段 DSH / 后段 CC CLI，一切皆插件」
- §〇 :5 决策源路径 →「qx-map 归档（原文件已清理，以本文件为准）」
- §四 人审节点表（:148-156）：节点③改「合入批准——默认由后段 CC CLI（phase2）自动执行+部署探活；老板保留否决/打回，重大合入可要求人审」，「不可绕过」字样删除
- §五自动化表（:190-203）：「合入批准 ❌ 人工」→「✅ 自动（phase2）+老板否决权」

### 5. docs/architecture.md
- :190-197 角色表：「管理席=桌面端总调度」→「可替换调度插件（现役外脑 Z Code；桌面端休眠）」；「验收/机审…桌面端终审」→「后段 CC CLI（phase2）+老板否决；前置机审=前段 DSH」；「六角色」→「五角色」统一（以 executors.json 实际 5 角色为准）
- :96 6100 表述已随 brain.py 行注释更新（「经现役出口」）；:98 relay 行已标「已退役」——relay 描述行本身为「旧中转站 server/relay/（6100/6102）已退役，仅保留历史记录」，已属退役口径，无需再标
- :105-108 三服务 plist 清单 → 两服务（删 com.ccc.board-scheduler.plist；board/scheduler.py 行标「已收敛进 engine」）
- :3,58 版本改 v0.71.0（含 :58 VERSION SSOT 注释 v0.70.0 → v0.71.0，顺手改）

### 6. SKILL.md
- :38-44 链路图改「任意设备壳 / 调度插件 → 拟指令 → 前段 DSH 开发+前置机审 → 已回写 → 后段 CC CLI（phase2）审核/验收/合入/部署 → 已关闭」
- :54-64 席位表按对齐重写（删 OpenCode/Codex/M1 终验行；改为前段 DSH / 后段 CC CLI / 管理席=可替换调度插件 / 其他工具按 executors.json 登记）
- 版本 v0.70.0 → v0.71.0

### 7. docs/DOC-PROTOCOL.md
- :85「合入批准=人审最终 diff，任何人/工具不可绕过」→「合入默认由 phase2 自动执行，老板保留否决/打回；重大合入可要求人审」
- :25,91「禁止一张张聊着出卡」加例外「老板/外脑逐张拟卡指令=合法单卡通道；批量 plan-to-cards 仍是方案期默认」

### 8. docs/product/dev-channel.md
- :13-33 席位表与主路径按三层分工重写（删桌面端/主 IDE/6100 出口；前段 DSH / 后段 CC CLI / 管理席=可替换调度插件；主路径=指令→前段开发+前置机审→已回写→后段审核/验收/合入/部署→已关闭）
- 文首三行引语同步对齐（删「谁开发谁验收」「6100」表述）

## 二、commit 列表（15 笔，均已 push origin main）

| commit | 说明 |
|--------|------|
| a359fe9b2 | docs(align): align startup brief with plugin model |
| 4aa53700d | docs(align): drop trailing whitespace on version line |
| ead088a70 | docs(align): align index governance terminology |
| c1a6f0e21 | docs(align): update red-lines plugin governance |
| 682ff7cdc | docs(align): clarify red-line authority exceptions |
| 36fcbed5f | docs(align): align prime directive execution stages |
| dc9c9f668 | docs(align): align architecture roles and services |
| b387a31ce | docs(align): normalize architecture whitespace |
| 7cccdfce6 | docs(align): align skill execution chain |
| 997b7e482 | docs(align): normalize skill whitespace |
| 9442f1adc | docs(align): update document protocol handoff |
| 888bda4d1 | docs(align): align development channel stages |
| e18295415 | docs(align): rewrite development channel seats table |
| f8a937b6d | docs(align): normalize protocol list numbering and whitespace |
| 35ca579b3 | docs(align): sync card glob and version SSOT across batch A |

## 三、验证与边界

- `git pull --ff-only` 开工前已确认与 origin/main 同步、工作区干净
- 全程零代码/配置/卡文件改动；未重启引擎、未跑全量测试
- 每 commit 前 `git diff --check` 通过（期间两处版本行尾随空格已单独清理 commit）
- 相邻同源错误顺手修正（已在报告中列明）：STARTUP-BRIEF `T<n>` 卡 glob、architecture VERSION SSOT 注释
- 遗留说明：STARTUP-BRIEF :5/:42 与 architecture :44 的「6100/6102 已退役」为历史记录口径，非现役绑定，保留
- 最终 head：`35ca579b3`

ALIGN-A-DONE 35ca579b3
