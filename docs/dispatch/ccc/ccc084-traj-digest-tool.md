# 任务卡 ccc084 · 轨迹抽取工具固化 traj-digest（DSH 执行）

> 关联：环节②交接指令(S116-01)卡3 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

将临时区取证脚本 /tmp/dsh-traj-extract.py（重启即失）固化为仓内 scripts/traj-digest.sh：对指定卡的执行轨迹一键出坑清单（并发风暴/空转/环境坑/git 工作流/测试依赖五类）。

## 红线

- 白名单：scripts/traj-digest.sh（新建）。只读消费既有轨迹数据（exec/*.log、worker-events.jsonl、engine.stderr.log），不改任何数据源。
- macOS 优先：避免 sha256sum 等 Linux 专属命令；set -euo pipefail。

## 范围

- 入参：卡号或 exec 日志路径；输出：结构化坑清单（类别/证据行/时间戳）。
- 兼容 stderr 无时间戳现状（按行序+metrics jsonl 对时策略）。

## 步骤

1. 以 /tmp/dsh-traj-extract.py 逻辑为基线重写为 bash+python 内嵌形态落仓。
2. 对 ccc076-079 四卡轨迹实跑，产出清单。

## 验收标准

- [ ] scripts/traj-digest.sh 对 ccc076-079 轨迹跑通，五类坑清单输出完整
- [ ] 清单结论与本批取证（环节②指令第二节）逐类可对齐
- [ ] bash -n 通过；重复运行幂等

## 回写要求

- 回写区附四卡跑批输出摘要与对齐说明；维护区四问如实。

## 人工批注

（留空）

## 回写区

**实现说明**（commit `cae16b61f` · scripts/traj-digest.sh，601 行，bash+python3 内嵌单文件）

1. **基线固化**：以 /tmp/dsh-traj-extract.py 逻辑为基线重写落仓；保留其会话 .zstd 摘要内核（tool_stats/llm_retry/首末时间/终报截断），新增五类坑检测器与结构化输出。数据源全部只读：会话轨迹 `~/.dsh/sessions/<worktree>-<卡>--/*/session.jsonl.zstd` + `exec/<卡>*.log` + `exec/worker-events.jsonl` + `exec/engine-metrics.jsonl` + `engine.stderr.log`。
2. **五类检测器 A1-E3**：编号逐条对齐环节②指令第二节取证表。会话级判定：A1=同指纹「任务卡（被审分支副本）」审计副本会话聚集（≥10 风暴级）；B1=executor 会话零编辑（tools≤20）聚集+runN 文件数+短命运行；B2=单会话 llm/retry≥3。关键词级：C1-C5/D1-D3/E1-E3/E2/A2 逐类正则，每条证据带 来源:行号/事件号 + 时间戳 + 截断原文。A3/B3 属白名单外数据源（git 时序/watchdog 日志），工具如实声明不出伪证据。
3. **stderr 无时间戳对时策略**：按行序线性内插，锚优先级 env `TRAJ_DIGEST_STDERR_T0/T1` → engine-metrics.jsonl 首末样本时间，内插值加 `~` 前缀标注近似；同时输出行区间供人工复核。
4. **macOS 纪律自证**：无 sha256sum/stat -c 等 GNU 专属命令（工具自身即 C1 坑的反面教材落地）；`set -euo pipefail`；grep 计数为零 exit 1 的 C5 坑一律 `|| true` 兜底。

**四卡跑批摘要**（`TRAJ_DIGEST_LOG_DIR=<归档展开目录> scripts/traj-digest.sh ccc076 ccc077 ccc078 ccc079`）

| 卡 | 会话数(机审副本) | runN | 命中类别 |
|----|----|----|----|
| ccc076 | 7 (4) | ×2 | A1 A2 C1 C2 D1 D2 D3 E1 E2 E3 |
| ccc077 | 3 (1) | ×1 | C2 D2 D3 E1 E2 E3 |
| ccc078 | 46 (33) | ×12 | A1 A2 B1 B2 C1 C2 C4 C5 D2 E1 E3 |
| ccc079 | 8 (5) | ×2 | A1 B2 C3 D1 D2 E1 E3 |

**与环节②指令第二节对齐说明**（逐类）

- **A1 并发风暴** ↔ ccc078 检出 **33 个同指纹审计副本会话**（风暴级，指令原表同数）；ccc079 worker-events 双审计间隔<1min；ccc076/079 多实例审计提示。
- **A2 写卡竞态** ↔ ccc076 四处命中原文「file changed since it was read / 并发实例下写入者不可归因」（session 136f487c、6a497d11 等，与指令点名一致）。
- **B1 重启空转** ↔ ccc078 run1..12.log 共 12 运行文件 + **11 个零编辑执行体会话**（08-24 14:47→15:38，52min 窗），对应指令「14:47→15:36 序列、13 短命会话」。
- **B2 llm_retry** ↔ ccc078 session c9383a6f ×5（指令点名同会话）、a965373d ×3；ccc079 同类命中。
- **C 类环境坑** ↔ C1 sha256sum 命中 ccc076 c0313075（指令点名）；C2 private/var 命中 ccc077.run1.log:19 维护区自述行（指令点名）；C3 Address already in use 命中 ccc079 **session-5b4185e4**#ev920 OSError errno48（指令点名同会话）；C4 No module named 与 C5 bash 语法坑集中命中 ccc078。
- **D 类测试基线** ↔ D1 test_board_loader 断言翻转披露命中 ccc079.run1.log:27（对应 d9be14023 入板契约修正）与 ccc076 机审区讨论；D2 真实仓污染/stash 存量失败/conversation 族命中 ccc076+ccc079；D3 TypeError 候选证据两卡可见。
- **E 类 git 工作流** ↔ E1 rebase 失败三卡全中（对应「三张卡各踩一次」）；E2 upstream/exit128 候选命中；E3 nothing to commit 竞态命中 ccc076/078。
- **边界如实声明**：A3（git 提交时序）、B3（watchdog 日志）不在本工具数据源白名单内，输出 notes 字段声明不造证据。

**数据面披露**：ccc076-078 的 exec 日志在 `~/.ccc/logs/archive-20260824/exec-sessions.tgz` 归档（现役 exec/ 仅存 ccc079+），跑批用归档只读展开视图（/tmp 暂存）驱动，未改任何源文件；现役日志面复验 `scripts/traj-digest.sh ccc084` 跑通（含 stderr 对时段）。worker-events.jsonl 对 ccc076-079 覆盖极薄（合计 5 行）已如实反映在数据面行。

**自测结果**

- 门禁① `bash -n scripts/traj-digest.sh` → 通过。
- 门禁② 四卡批量跑通退出码 0；连续两次运行 `diff -q` 零差异 → 幂等通过。
- 门禁③ `--json` 模式可解析（python json.load 通过）；无数据卡（ccc999）退出码 2 符合 usage 契约；exec 日志路径入参自动剥离 `.runN/.audit` 后缀解析卡号通过。
- 五类清单完整性：四卡合计命中 13/15 检测器；仅 A3/B3 按设计属数据源外（见 notes 声明）。

**Commit 与 push 核验**

- 分支 `codex/ccc084-traj-digest-tool`（基点 origin/main@3e93a861d）：`cae16b61f` 实现；`b7d3091b6` 卡回写。
- push 退出码 0；push 后 `git ls-remote origin codex/ccc084-traj-digest-tool` = `b7d3091b6e1ff0213c839dc513d19829639fbef0`，与本地 HEAD 一致。

**卡回写结果**：卡头状态=已回写；回写区填实现说明/跑批摘要/对齐说明/自测/push 核验；维护区四问逐项如实勾选。未写机审区/验收区、未置已关闭。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：本卡关联环节②交接指令(S116-01)卡3，非 prefix-plan-NNN 方案转卡，无方案文需同步。
2. **教训沉淀**：[无]
   - 说明：本卡本身即教训固化载体（五类坑检测器入库）；跑批新观察——worker-events.jsonl 对 ccc076-078 零覆盖、ccc076-078 exec 日志已归档 tgz，属运行面数据留存缺口，已在回写区披露待后续卡认领，未沉淀 lessons.md。
3. **档案/README**：[否]
   - 说明：新增 scripts/traj-digest.sh 用法与数据源契约已写在脚本头注释与本卡回写区，无项目档案/README 结构变更。
4. **线路图**：[否]
   - 说明：无新增线路意向；工具后续扩展（如 watchdog 日志接入补 B3 取证）留待实际需要时另出卡。
