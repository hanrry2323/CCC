# 任务卡 ccc080 · R3 流程闭环实测卡——全链演练专用（DSH 执行）

> 关联：R3 排查指令（2026-08-24 老板直接任务） · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

> 处理记录（2026-08-24 · 出卡说明）：new-card.sh 按 FORBIDDEN_CARD_PREFIXES 设计拦截 ccc 自指出卡；本卡系老板 R3 指令明确要求「一条真实测试卡（ccc-prefix）穿过全链」，依 ccc075/076-079 先例以指令为授权手工落卡。另取证：dispatch 未提交新卡会被引擎 _force_align_dispatch 按 untracked 清除（吃单窗），故本卡落盘即提交。

## 目标

对 CCC 自动化全流程做一次端到端真实演练取证：本卡经 engine 派发 → DSH 执行体 → 自测 → 回写 → 机审 → ready_for_merge 可见，逐环节留证据，确认无断链、无假告警、无卡死。

## 红线

- 本卡白名单仅允许新增一个文件：docs/notes/r3-drill-ccc080.md（内容一行：R3 pipeline drill ok &lt;ISO时间&gt;）。
- 禁止触碰任何其他文件、禁止 git add -A、禁止直推 main。
- 执行体不改 engine/board/scripts 任何代码。

## 范围

- 仅 docs/notes/ 下单一新文件（见红线）。

## 步骤

1. 在 worktree 内创建 docs/notes/r3-drill-ccc080.md，写入规定一行内容。
2. git add 该文件并 commit（消息前缀 drill(ccc080):）。
3. 自测：文件存在且含规定字符串（cat 取证）。
4. 填写回写区与维护区四问，commit 并 push 分支 codex/ccc080-r3-pipeline-drill。

## 验收标准

- [ ] 分支上存在 docs/notes/r3-drill-ccc080.md 且内容匹配规定前缀
- [ ] 分支相对 origin/main 含业务 commit + 回写 commit
- [ ] 卡头状态流转 待分派→执行中→已回写 全程可观察

## 回写要求

- 卡头状态改「已回写」；回写区写明改动清单、commit sha、自测证据。
- 维护区四问逐项如实勾选并各附一句实情。

## 人工批注

（留空——环节② 合入时填写）

## 回写区

- 改动清单（2026-08-24 · DSH 执行体）：
  - 新增 `docs/notes/r3-drill-ccc080.md`（唯一白名单内新文件，内容一行：`R3 pipeline drill ok 2026-08-24T13:35:32Z`）。
  - 本卡文件状态流转回写：待分派→执行中（业务 commit）→已回写（本 commit）；并按 docgate 完成钩子补 `## 维护区` 节四问。
- commit：
  - 业务 commit：`17a550271`（drill(ccc080): R3 全链演练——新增规定取证文件，卡头 待分派→执行中）
  - 回写 commit：见分支最新一笔（drill(ccc080): 回写……）
- 自测证据：
  - `cat docs/notes/r3-drill-ccc080.md` → 输出 `R3 pipeline drill ok 2026-08-24T13:35:32Z`
  - `grep -c "^R3 pipeline drill ok " docs/notes/r3-drill-ccc080.md` → `1`（MATCH）
  - `ls -la docs/notes/r3-drill-ccc080.md` → 文件存在（42 字节）
- 分支：`codex/ccc080-r3-pipeline-drill`；相对 origin/main 含业务 commit + 回写 commit，未触碰 main。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：本卡系老板 R3 指令的一次性全链演练卡，无关联方案编号，不推进方案。
2. **教训沉淀**：[无]
   - 说明：演练产出即取证文件 docs/notes/r3-drill-ccc080.md，本次无新增流程教训需另立笔记。
3. **档案/README**：[否]
   - 说明：白名单仅限单文件新增，未触及 docs/projects/ccc/README.md 等项目档案。
4. **线路图**：[否]
   - 说明：一次性流程演练，不改变任何线路图意向或排期。
