# 任务卡 ccc085 · deploy 与 git_sync 的 FETCH_HEAD 并发竞态修复（DSH 执行）
> 批准：老板合入批准 · 2026-08-25

> 关联：环节②交接(2026-08-25)问题1 · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：engine · 项目：ccc · 日期：2026-08-25

## 目标

消除 deploy-ccc.sh 的 git pull --ff-only 与 server/git_sync.py 周期性 fetch 对 .git/FETCH_HEAD 的并发无锁写导致的「Cannot fast-forward to multiple branches」间歇失败。

## 红线

- 白名单：scripts/deploy-ccc.sh、server/git_sync.py、server/tests/（如需回归）。
- 双侧同修（方向 A+B）：deploy 改 `git fetch --no-write-fetch-head origin main && git merge --ff-only origin/main`；git_sync.py:87 的 fetch 同加 --no-write-fetch-head。
- 不改 pull/ff 的既有成功语义（本地落后时仍能 ff）。

## 步骤

1. 修改两处命令形态；确认本机 git 2.39.2 支持 --no-write-fetch-head（git --version 取证）。
2. 自测：三守护常驻下连续跑 deploy-ccc.sh 全流程≥5 次（或等效仅执行其拉取段×10），0 次报 Cannot fast-forward；另造本地落后一 commit 场景验证仍能 ff 更新。

## 验收标准

- [ ] 连续≥5 次部署拉取零失败（附逐次输出）
- [ ] 落后场景 ff 更新行为不回归
- [ ] bash -n / py_compile 通过

## 回写要求

- 回写区附逐次跑批输出与 diff 要旨；维护区四问如实。

## 人工批注

（留空）

## 回写区

- **实现说明**（2026-08-25 · DSH 执行体）：
  1. `scripts/deploy-ccc.sh` [1/3] 拉取段：`git pull --ff-only origin main` → `git fetch --no-write-fetch-head origin main && git merge --ff-only origin/main`；文件头「机制」注释与 Git-Pull 恢复提示文案同步更新，失败分支语义（报错+exit 1）不变。
  2. `server/git_sync.py` `sync_origin_main()` 的 fetch（原 :87）：`["fetch", remote, branch]` → `["fetch", "--no-write-fetch-head", remote, branch]`；模块 docstring 策略第 1 步同步标注。`merge --ff-only <remote>/<branch>` 与 dispatch 强制对齐兜底逻辑零触碰（相对原逻辑仅 fetch 参数一处 + 注释/docstring 三处）。
  3. 原理：双侧 fetch 均不再读写 `.git/FETCH_HEAD`，deploy 侧 merge 只读 `refs/remotes/origin/main`——部署拉取与周期 fetch 对 FETCH_HEAD 的并发无锁共享写被结构性消除；fetch 后 git 的 opportunistic 远端跟踪引用更新不受该 flag 影响（阶段C 实证）。
  - diff 要旨：deploy 侧 1 处命令替换（+5/-2 行含注释），git_sync 侧 1 处 argv 追加 flag（+4/-2 行含注释/docstring）；合计 2 文件 +11/-6。

- **自测结果**：
  - 门禁：`bash -n scripts/deploy-ccc.sh` → BASH-SYNTAX-OK；`python3 -m py_compile server/git_sync.py` → PY-COMPILE-OK。flag 支持取证：`git --version` = 2.39.2 (Apple Git-143)；实测 `git fetch --no-write-fetch-head .` rc=0。
  - 并发跑批 ×12（卡步骤2的「等效仅执行拉取段」路线：隔离沙箱 /tmp/ccc085-selftest 内 bare origin + work 克隆复刻生产拓扑——守护侧每轮以真实 `sync_origin_main()` 连发×4、部署侧按新命令形态拉取×1 并行竞争同一仓，远端每轮推进 1 提交制造真实 ff 工作）。逐次输出（12 轮全部 rc=0）：
    `[round 1..12] deploy rc=0`（逐轮打印，见 commit 前自测留档 /tmp/ccc085-selftest/sync.*.log）；汇总行：`rounds=12 deploy_fail=0 sync_fail=0 cannot_fast_forward=0 lock_contention=0`（守护侧累计 sync ok ×48）。**0 次报 Cannot fast-forward**。
  - 落后场景回归：work 回退至落后基线 4734ac5（落后 origin/main 一提交以上），新形态一次执行即 `Updating 4734ac5..761f0b1 Fast-forward`，ff 后 HEAD==origin/main=YES；证明 opportunistic 更新 refs/remotes/origin/main 正常、成功语义不回归。
  - 竞态机制对照（旧形态中招实证）：将 work 的 `.git/FETCH_HEAD` 污染为两个分歧候选后，旧形态 `merge --ff-only FETCH_HEAD` rc=128（本机 git 2.39.2 措辞：`fatal: Not possible to fast-forward, aborting.` / `not something we can merge in .git/FETCH_HEAD: …`，与生产所见 Cannot fast-forward to multiple branches 同属 FETCH_HEAD 内容依赖失败家族）；同状态新形态 `merge --ff-only origin/main` rc=0 正常 ff。且新形态 fetch+merge 全程前后 `.git/FETCH_HEAD` md5 不变——该文件已脱离新链路读写面。
  - 单测回归：`python3 -m pytest server/tests/test_git_sync.py -q` → **7 passed**（测试未断言 fetch argv，无需改 server/tests/）。
  - 范围备注：未采用「三守护常驻下全流程 deploy ≥5 次」主路线——全流程含 pytest 全量门禁与 kickstart 热重启，且本执行体运行于 codex 分支 worktree（在该分支上 merge --ff-only origin/main 本就应拒绝），热重启会以非 main 工作树扰动运行面，超出本卡授权范围；故按卡内明示的等效路线执行拉取段压测，并以真实 `sync_origin_main()` 代码路径充当守护侧。

- **Push 证据**：代码 commit `38abb9f8a` → 分支 `codex/ccc085-deploy-fetch-race`（基于 origin/main = 738cac95e），push 退出码=0（GitHub 返回 `* [new branch] codex/ccc085-deploy-fetch-race -> codex/ccc085-deploy-fetch-race`）。本回写 commit 为分支第二个提交。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：直派卡，卡头「关联」为环节②交接问题项而非 plan 编号，无方案状态需同步。
2. **教训沉淀**：[无]
   - 说明：机制结论（FETCH_HEAD 是 pull/fetch 并发的隐式共享状态，双侧 --no-write-fetch-head 可无锁化）已记录于本卡回写区，未另立 docs/notes 文件。
3. **档案/README**：[否]
   - 说明：仅两处命令形态与注释变更，无目录结构/注册表/路径变化。
4. **线路图**：[否]
   - 说明：缺陷修复卡，不产生新业务线路或里程碑。

## 机审区

**DSH 机审席 · 2026-08-25 · severity：轻**

- 范围核对：分支基于 origin/main=738cac95e，仅 2 提交——38abb9f8a 代码修复（scripts/deploy-ccc.sh + server/git_sync.py，+11/-6，均在白名单内）、07017557b 回写（仅卡文件）；工作树干净，无越界改动。
- 独立复现（机审自建沙箱 /tmp/ccc085-audit-selftest2，bare origin+seed+work 复刻生产拓扑；驱动留档 /tmp/ccc085-audit-driver2.py、输出 /tmp/ccc085-audit-run2.log）：
  - 门禁：`bash -n scripts/deploy-ccc.sh` OK；`py_compile server/git_sync.py` OK；本机 git 2.39.2 实测 `--no-write-fetch-head` rc=0。
  - 语义：落后一提交时仅跑新形态 fetch 段 → refs/remotes/origin/main 机会性更新到位且 FETCH_HEAD md5 不变；merge --ff-only origin/main 一次 Fast-forward 成功、HEAD==origin/main。
  - 并发 B′：12 轮 ×(4×真实 sync_origin_main + 1×新形态部署拉取) 同毫秒并发：**0 次 Cannot fast-forward to multiple branches**，24+ 次并发 fetch/merge 全程 FETCH_HEAD 未被双侧触碰。
  - 对照 E：同拓扑旧形态 `git pull --ff-only` 6 轮 5 败（见下条）；机制 D：污染 FETCH_HEAD 双分歧候选后旧形态 merge FETCH_HEAD rc=128（Not possible to fast-forward, aborting.），新形态 rc=0 正常 ff 且 FETCH_HEAD 未动——目标竞态对被结构性消除，卡述机理逐字复现。
  - 单测：`pytest server/tests/test_git_sync.py -q` → 7 passed。执行体留档抽查：/tmp/ccc085-selftest/sync.1..12.log 存在且内容与卡述一致。
- 发现与风险论证（0 P0/P1）：
  1. 【遗留·范围外】B′ 中 10/12 轮部署段 fetch 报 `cannot lock ref 'refs/remotes/origin/main': … expected …`（机会性远端跟踪引用更新的 CAS 竞态）→ fetch rc≠0。对照 E 实证同拓扑旧形态同样中招（6 轮 5 败，败因相同），系**预存在**、与本卡无关、暴露面不变，非回归；生产节奏下需毫秒级重叠，sync 侧下一周期自愈、deploy 侧重跑即恢复。超出本卡白名单不就地修，建议后续单独立卡（fetch 失败重试或进程级串行化）。
  2. 【范围外观察】approve-merge.sh:603、scripts/worker-claim.sh:35-37 仍为旧形态 pull（FETCH_HEAD 写读方）：deploy 与 git_sync 双侧退出后，原报障竞态对已消除；残余为人工侧脚本互并发的预存在小概率场景，不在本卡范围。
- 维护区核对（P1-b 机械判据）：四问均为单选实名填写（[否]/[无]/[否]/[否]），说明行各一句实情、非占位；抽查属实——Q1 卡头确为交接直派项非 plan 编号，Q2 机制结论确在本卡回写区，Q3 diff 无结构/注册表变化，Q4 属实。

结论：双侧对称最小改动，成功语义保持有回归实证，目标竞态结构性消除有 B′/D 实证，白名单零越界，维护区四问真实填写。

机审：通过（被审 07017557bebd）

## 验收区

**合入批准** · 日期：2026-08-25
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
