# 任务卡 ccc091 · 引擎对齐宽限窗——未跟踪新卡不再静默清除（DSH 执行）

> 关联：R1-R4 吃单窗纵深防御 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

server/git_sync.py `_force_align_dispatch` 对 dispatch 子目录内 **mtime 距今 < GRACE_SECONDS（默认 300s，env CCC_ALIGN_GRACE_SECONDS 可调）的未跟踪 .md 新卡**不做清除，改为 logger.warning 告警一次（同文件去重）；超宽限仍存在才按原逻辑移除。纵深防御：即使出卡方忘记提交，卡也不会无声死亡。

## 红线

- 白名单：server/git_sync.py、server/tests/。
- 不改变已跟踪文件的对齐语义；不动 ff-only 主流程。
- 告警须含文件名与「疑似出卡未提交」提示。

## 步骤

1. _force_align_dispatch 移除未跟踪文件前按 mtime 过滤，命中宽限窗的记 warning 集合计数返回。
2. 自测：单测构造 untracked 新卡（mtime 新鲜）断言不被移除；伪造旧 mtime 断言被移除。

## 验收标准

- [ ] 两条单测绿
- [ ] 生产语义不变（ff-only 主流程零改动）

## 回写要求

- 回写区附单测输出与 diff 要旨；维护区四问如实。

## 人工批注

（留空）

## 回写区

- **实现说明**（2026-08-25 · DSH 执行体）：
  1. `server/git_sync.py` 新增 `_align_grace_seconds()`：宽限窗秒数读 env `CCC_ALIGN_GRACE_SECONDS`，缺省 300s，非法值回退缺省并 warning，负值按 0（=关闭宽限、恢复原立即清除语义）。
  2. `_force_align_dispatch()` 移除未跟踪文件前按 mtime 过滤：仅对 `.md` 未跟踪卡生效——mtime 距今 < 宽限窗 → 不清除，`logger.warning` 告警一次（模块级 `_GRACE_WARNED` 集合同文件去重，告警含文件名与「疑似出卡未提交」提示）；超窗仍存在才按原逻辑 `unlink`。返回契约由 `int` 改为 `{"removed", "grace_kept"}`（全仓仅本文件内两处调用），`sync_origin_main` summary 透出 `grace_kept` 并入 detail 文案。
  3. 红线核验：fetch/merge --ff-only 主流程段与已跟踪文件对齐语义零改动（diff 中无触碰）；ff-only 成功路径的 `_force_align_dispatch` 调用行原样保留。
  - diff 要旨：`server/git_sync.py` +58/-7（docstring 策略注记、import time、宽限窗助手与去重集合、mtime 过滤分支、返回契约与 summary 字段）；`server/tests/test_git_sync.py` +75（新增 `TestForceAlignGraceWindow` 4 测）。合计 2 文件 +133/-7。

- **自测结果**：
  - 卡面两条验收单测（`server/tests/test_git_sync.py::TestForceAlignGraceWindow`）：
    - `test_fresh_untracked_card_not_removed`：真实 git 临时仓构造 mtime 新鲜的未跟踪新卡 → 断言不被移除且 `{"removed": 0, "grace_kept": 1}`；caplog 取证告警恰 1 条且同时含文件名 `ccc099-new-card.md` 与「疑似出卡未提交」；第二轮对齐同文件不再重复告警（去重实证）。
    - `test_stale_untracked_card_removed`：伪造旧 mtime（1 小时前 > 300s 宽限）→ 断言按原逻辑移除，`{"removed": 1, "grace_kept": 0}`。
    - 另补 `test_grace_seconds_env_override`（env=0 关闭宽限 → 新鲜卡立即移除）与 `test_grace_seconds_env_parsing`（缺省 300 / 非法回退 / 负值按 0）。
  - 命令与输出：`python3 -m pytest server/tests/test_git_sync.py -v` → **11 passed in 3.69s**（4 新增 + 7 存量全绿）。
  - 生产语义回归：`python3 -m pytest server/tests/test_board_scheduler.py server/tests/test_engine_main.py server/tests/test_engine_dispatch.py` → **168 passed in 35.25s**；存量用例 `test_force_sync_cards_from_main`（dispatch-checkout 覆盖路径）原样通过。
  - 端到端冒烟（隔离 /tmp 沙箱 bare origin + local 克隆复刻生产拓扑）：本地脏 tracked 卡 + 新鲜未跟踪新卡触发 dispatch-checkout 路径，实测输出 `method = dispatch-checkout`、`removed_untracked = 0 | grace_kept = 1`、`fresh card exists = True`，stderr 告警原文：`git sync 对齐跳过宽限窗内未跟踪新卡 docs/dispatch/ccc100-brandnew.md（mtime 距今 0s < 300s）——疑似出卡未提交，暂不清除`。
  - Lint：`python3 -m ruff check server/git_sync.py server/tests/test_git_sync.py` → All checks passed。

- **Push 证据**：代码 commit `352e91b0f80b96d3b222249744ae3cf98888ef3f` → 分支 `codex/ccc091-align-grace-window`（基于 origin/main = c5d927686），push 退出码=0（GitHub 返回 `* [new branch] codex/ccc091-align-grace-window -> codex/ccc091-align-grace-window`）。本回写 commit 为分支第二个提交。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。直派单卡（R1-R4 吃单窗纵深防御系列），卡头「关联」无 plan 编号，无方案页面需同步。
2. **教训沉淀**：[无]
   - 说明：[无]。机制结论（出卡方忘提交时周期对齐会静默清卡，须以 mtime 宽限窗做纵深防御）已记录于本卡回写区，未另立 docs/notes 或 lessons 文件。
3. **档案/README**：[否]
   - 说明：[否]。仅 server/git_sync.py 内部加固与 server/tests/ 单测补充，不改项目结构/技术栈/路径。
4. **线路图**：[否]
   - 说明：[否]。单点防线收口，不构成新里程，项目近况符合原规划。

## 机审区

**DSH 机审席 · 2026-08-25 · severity：轻**

- **范围核对**：代码 commit `352e91b0f` 仅触碰 `server/git_sync.py`（+65/-7）与 `server/tests/test_git_sync.py`（+75），在卡白名单内；基线 `c5d927686` = origin/main；工作树干净。ff-only 主流程与已跟踪文件对齐语义零改动（diff 实证：fetch :111 / merge :123 / 成功路径调用行 :130 均未触碰语义）。
- **契约变更核验**：`_force_align_dispatch` 返回 int→dict，全仓仅本文件两处调用——`:130` 返回值弃用、`:145` 消费 dict；外部调用方（board/scheduler.py:50、engine/main.py:4110）只读 `ok/detail/method`，不受影响。
- **机械复现**（机审席独立执行，非采信执行体自述）：`pytest server/tests/test_git_sync.py -v` → 11 passed；回归 `test_board_scheduler + test_engine_main + test_engine_dispatch` → 168 passed；`ruff check` → All checks passed；`git ls-remote origin codex/ccc091-align-grace-window` → `7f9341f6f`（回写已推送实证）。
- **对抗探针**（隔离沙箱 bare origin 复刻生产拓扑）：非 `.md` 未跟踪文件不受宽限保护立即清除 ✓；子目录 `.md` 新卡受宽限窗覆盖 ✓；非法 env 回退 300s ✓；**F1 实锤**：未来 mtime（时钟偏斜）+ `CCC_ALIGN_GRACE_SECONDS=0` 时 `age<0 < grace=0` 为真 → 卡被保留且告警渲染「0s < 0s」，违背回写区「负值按 0=恢复原立即清除语义」承诺。
- **severity 三级**：影响面 1（病态场景、下周期自愈）+ 改动深度 1（单条件边界）+ 红线邻近 1（无）= 3 → 轻。
- **分流（轻→就地修复）**：机审席 F1 已修复——age 钳制 `max(0.0, now-mtime)`（server/git_sync.py:203-206），新增 `test_future_mtime_card_removed_when_grace_disabled` 锁定契约；修复后 12 passed、ruff 全绿；commit `0dfc3701c` 已推分支。
- **轻微项记录（不计分）**：O1 `_GRACE_WARNED` 进程生命周期不清理，同路径重建卡不再告警——符合卡面「告警一次（同文件去重）」规格，仅备忘；O2 验收标准两复选框未勾选，回写区证据已覆盖，不影响判定。
- **维护区核对**：四问均单选 [否]/[无] 非占位，说明各为一句实情；抽查 Q2「未另立 docs/notes」属实（grep docs/notes 无 ccc091/宽限窗相关文件）；Push 证据与远端一致。

机审：通过
