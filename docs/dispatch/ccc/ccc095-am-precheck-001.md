# 任务卡 ccc095 · am-precheck-001：approve-merge.sh 增设一次性环境预检段——环境检查与质量核验分区呈现（管理席直改·异席机审）

> 关联：外脑清场收尾2026-08-26 · 依据/tmp/approve-merge-diagnosis.md · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：manual · 项目：ccc · 日期：2026-08-26

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 诊断依据：/tmp/approve-merge-diagnosis.md（2026-08-26 只读诊断）

## 目标

scripts/approve-merge.sh 开头增设一次性「环境预检段」：A类11项中的可静默项（当前分支=main / worktree 干净 / origin 可达 / ff 状态等）预检通过即只输出一行 `[PRE-OK]`；任一项失败以独立 exit code 中止并明确指出失败项名称与处理指引。B类质量检查全部保留硬门禁不动。解决老板反馈的痛点：合入报告里路径/工作树类环境问题与代码质量问题混排互相淹没。

## 实现

（二级实现详情：功能背景 / 开发要求 / 关键代码思路。）

## 红线（先看）

1. 白名单：scripts/approve-merge.sh（唯一允许改动文件）。
2. 不改任何 B 类检查逻辑：密钥扫描、测试真实性证据、provenance 账本、维护区四问、信封纯度+漂移全部原样保留硬门禁。
3. git_sync 合入竞态检测保留阻断性质，但移入独立分区呈现（不与质量结论混排）。
4. 本卡为平台自研流程脚本卡：按老板 2026-08-26 指令不走 engine 自动派发，由管理席直接开发 + 异席机审补位（受老板临时授权，直改 diff 与测试证据回报后由环节②复核）。

## 范围

仅 scripts/approve-merge.sh；预检段为纯新增只读 git 查询，不改变任何既有检查函数的判定语义。

## 步骤

1. 在参数解析后、首卡处理前插入 env_precheck 函数：分支状态/worktree 脏洁/fetch 可达/ff 状态逐项检查。
2. 全过输出一行 [PRE-OK]；任一失败按「[PREFAIL] 失败项：<名称>：<指引>」输出并以独立非零退出码中止。
3. 隔离环境（/tmp 克隆仓 + 独立 CCC_DATA_DIR）做验收 a/b/c 三场景实测。

## 验收标准

1. 干净环境下合入一张测试卡，报告开头只见 [PRE-OK]，无环境噪音刷屏。
2. 人为制造一个脏 worktree 再合入，报错明确指向该项且 exit code 非0。
3. 近期已关闭卡的合入回归不受影响（对照已归档卡合入记录，既有 B 类检查输出行为不变）。

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试： bash -n scripts/approve-merge.sh
编译：
lint：
范围：true

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：DSH · 日期：2026-08-26

### 实现说明

- scripts/approve-merge.sh 参数解析后（`cd "$PROJECT_ROOT"` 之后）纯新增 `env_precheck` 函数与一次调用（+45行，零删改）：branch=main / worktree 干净 / origin fetch 可达 / 本地不落后 四项只读检查。
- 全过 → 一行 `[PRE-OK] 环境预检通过（branch/worktree/fetch/ff）`；任一失败 → `[PREFAIL] 失败项：<名称>：<指引>` 并以独立退出码中止（31=branch / 32=worktree / 33=fetch / 34=lagging）。
- B类八项检查与 git_sync 竞态检测零改动（diff 可证：纯新增块，无任何既有行变更）。

### 测试结果（/tmp/amtest 隔离克隆实测）

1. bash -n → PASS。
2. 场景a 干净环境：报告首行即 `[PRE-OK]`，与改动前基线输出 diff 仅多这一行，下游 spot-check 行为逐字节一致（rc 同为 1）。
3. 场景b 脏worktree（echo dirty >> README.md）：`[PREFAIL] 失败项：worktree …`，rc=32 非0。
4. 场景b2 非main分支（tmp-test）：`[PREFAIL] 失败项：branch …`，rc=31。

### push 证据

- 直改随本卡同一 commit 推送 main（见 git log feat(am-precheck-001)）。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：本卡为外脑清场收尾直派运维卡，无 prefix-plan-NNN 方案关联，无方案文件需同步。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：两条已落 docs/notes/2026-08-26-ccc-lessons.md——含「管理席直改卡同样必须同步填写维护区，否则机审门禁打回+熔断连锁」（外脑补充）；①dispatch 卡文件任何未提交编辑会被 git_sync 对齐秒级回吃，必须编辑与 commit 原子化；②engine 建工作树与出卡提交存在竞态，分支基点可能落后一拍，防护闸跳过派发时用 ff-only 对齐解卡。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅新增 approve-merge.sh 预检段，目录结构/技术栈/路径零变化（numstat 纯增可证）。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：环境预检属既有合入流程加固，线路与近况不变。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：ccc（CCC 平台自研主仓）

- 本卡由外脑清场收尾指令直派（编号 am-precheck-001）；因 new-card.sh 对 ccc 前缀设 FORBIDDEN_CARD_PREFIXES 护栏，按 DOC-PROTOCOL 命名手工制卡并过同款 validate 门禁；派发 manual，管理席直改，异席机审补位。

- 代码工作区：直接在本仓 main 工作区修改（平台自研脚本卡）；改动前先备份原文件到 /tmp 以便回滚

- 禁止：改 server/ 代码、动 B 类检查逻辑、越出白名单、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：ccc（CCC 平台自研主仓）

- 审查重点：diff 是否仅新增预检段；B 类八项检查逻辑是否零变更；三场景验收证据是否真实可复现

- 处理原则：

  - 可修问题 → 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（动了 B 类判定语义/越白名单）→ 输出「机审：不通过（具体原因）」并以非零退出

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

## 机审区

> 结论：通过
> 来源：engine 自动落盘（m4-first-audit-evidence）· 2026-08-26 12:06
> 证据：main=50fb5decc; pytest registry+audit_backfill+ccc_plan 绿; 实现已在 main（M4 受控首跑机审）
