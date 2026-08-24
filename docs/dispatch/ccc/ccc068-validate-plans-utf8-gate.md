# 任务卡 ccc068 · validate-plans UTF-8 locale 门禁修复——C locale 字节截断致 8.2 漏判（DSH 执行）

> 关联：无方案（2026-08-24 老板任务指令直派） · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：manual · 项目：ccc · 日期：2026-08-24
> 历史卡 · 2026-08-24 基线封存（流程纪律重置前合入/作废）

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/ccc/README.md`
- 引擎口径参照：`server/board/plans.py::sync_plan_progress`

## 目标

修复存量测试失败 `server/tests/test_plans.py::TestValidatePlansScript::test_script_cards_all_closed_but_not_advanced`
（2026-08-24 部署门禁拦截实证）：方案状态=部分执行、关联卡已全部关闭时，validate-plans.sh
在部署环境误返回 OK，8.2「全部关闭但未推进」漏判。

## 实现

白名单仅 `scripts/validate-plans.sh`（test_plans.py 经核验无需改动，见回写区说明）：

1. 脚本顶部（`set -euo pipefail` 之后）新增：
   `export LC_ALL="${LC_ALL:-en_US.UTF-8}"`
   根因：C/POSIX locale 下 BSD sed 按**字节**处理，字符类 `[^ ·\t\r\n]+` 中分隔符「·」的
   尾字节 B7 与「已」第二字节相同 → 卡头状态抽取被截成单字节 0xE5 → 已关闭卡误判活跃
   → active_count≥1 → 8.2 不触发。pytest 子进程继承 UTF-8 故本仓绿、launchd 部署 C 红。
   强制 UTF-8 后 sed/字符类按完整多字节字符工作。
2. 8.2 段缺失关联卡 else 分支：保持「计入活跃」不变（与引擎 sync_plan_progress 同口径：
   缺失 entry state 取空、不计 closed、落入活跃分母），仅新增 yellow WARN 观测告警，
   提示人审核对幽灵引用。

## 红线（先看）

1. 白名单外零触碰；禁直推 main（本卡由中枢出卡并按老板指令直派执行，执行体只推 codex 分支）。
2. 禁写机审区/验收区/置已关闭。
3. 不得改变 8.x 既有计数语义；缺失卡必须维持「活跃」口径（引擎一致性红线）。

## 范围

- scripts/validate-plans.sh
- server/tests/test_plans.py（预留：经核验夹具无需改动，实际未触碰）

## 步骤

1. 复现：沙箱三变体探针 + 双环境（UTF-8/C）对照，字节级定位 B7 碰撞。
2. 最小修改如上；`bash -n` 通过。
3. 验证电池：变体 A（存在已关闭卡，外层强制 C）→ rc=1 且输出含「关联卡已全部关闭/作废但状态仍为」；
   变体 B（缺失卡）→ rc=0 + OK + WARN；变体 C（开发中活跃卡）→ rc=0。
   目标用例常规环境与强制 C 环境双绿；全量 pytest 无新增失败。
4. commit+push 分支 `codex/ccc068-validate-plans-utf8-gate`；本卡以「已回写」态发布（老板指令直派，跳过引擎开发队列，机审照常异席执行）。
5. 停手等机审与环节②合入。

## 验收标准

1. 目标用例真实退出码=0（常规与强制 C 双环境）。
2. validate-plans 与 engine 缺失关联卡判定同口径（均计活跃，不视为已关闭）。
3. 全量 pytest 失败数不高于基线（基线=合并 tst004 后主干的当前失败集）。
4. 白名单外零触碰；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc068 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_plans.py -q

## 回写区

### 实现说明

- 改动文件：仅 `scripts/validate-plans.sh`（+11/-1）。两处：①顶部强制 `LC_ALL=en_US.UTF-8`（外层未显式设置时）；②8.2 缺失卡分支补 WARN 观测（计数语义不变）。
- `server/tests/test_plans.py` 未改动：夹具与断言本身正确（期望非零+断言文案），失败纯因被测脚本 locale 敏感；修脚本即绿，加测试属冗余。

### 自测结果（附命令）

```
bash -n scripts/validate-plans.sh                     → 通过
变体A 存在已关闭卡 @外层LC_CTYPE=C                    → rc=1，输出「FAIL 方案关联卡已全部关闭/作废但状态仍为 '部分执行'」✓
变体B 缺失卡   @外层LC_CTYPE=C                        → rc=0，OK + WARN 幽灵引用观测 ✓（与引擎同口径）
变体C 开发中卡 @外层LC_CTYPE=C                        → rc=0，OK ✓
pytest 目标用例（常规环境）                            → 1 passed ✓
pytest 目标用例（env -u LANG/LC_ALL LC_CTYPE=C）      → 1 passed ✓
全量 pytest server/tests -q（worktree 基座 0289471a4） → 100% 通过，0 失败 ✓
```

### commit 与 push 核验

- 分支 `codex/ccc068-validate-plans-utf8-gate`（基于 origin/main@0289471a4）
- 实现 commit：`ed1a863c3`
- push 证据：`git push -u origin` 输出 `* [new branch] … -> codex/ccc068-validate-plans-utf8-gate`；
  `git ls-remote origin refs/heads/codex/ccc068-validate-plans-utf8-gate` 返回 `ed1a863c3…` == 本地 HEAD。
  门禁命令真实退出码以 wrapper 截获证据日志为准（EXECUTOR_LOG_DIR/ccc068.test-evidence.log）。

### 异常披露

- 出卡时两次遭 git_sync 强制对齐清理未跟踪文件，最终以原子落盘即推方式发布（tst003 同款教训）。

## 机审区

（验收席专用——执行体禁止写入）

**DSH 机审席 · 2026-08-24 · severity：轻**

> 本块为同日第二轮复审，取代上一轮机审块：被审栈已整体 rebase 换板（实现件 58e4f2ab6@670e84c3a →
> 5582feb98@fe31a4003，补强 ef4987a9f 与卡回写 68e4f8fa0 随行），换板必须重新独立核验。
> 两树 `git diff 58e4f2ab6..HEAD -- scripts/validate-plans.sh server/tests/test_plans.py` 实测：
> 差异仅为 F1 补强块本身，其余内容逐字节一致。

独立核验（全部命令在本 worktree 实跑复现，不引用执行体自述）：

1. 范围核对：`git diff fe31a4003..HEAD --stat` 仅 `scripts/validate-plans.sh`（+22/-1）与卡文件；
   test_plans.py 属白名单预留、实际零触碰 ✓；`git ls-remote` 远程分支 == 本地 HEAD == 68e4f8fa0 ✓；
   未直推 main（远程 main 不含分支提交）、卡头仍「已回写」未置已关闭、验收区未触碰 ✓。
   注：工作区现有两处与本卡无关的未提交残留（docs/projects/mx/roadmap.md 一行 Loop 巡查更新、
   未跟踪 docs/archive/legacy-t-cards/cards.index.jsonl）——非本卡产物，本审不纳入提交、原样保留并披露；
   上一轮「git status 干净」系其时点事实，现已不成立。
2. 门禁实跑三连：目标用例常规环境与 `env -u LANG -u LC_ALL LC_CTYPE=C` 强制 C 双环境均 [100%] rc=0；
   全量 `python3 -m pytest server/tests -q` [100%] rc=0；`bash -n` 通过——验收标准 1/3 达成。
3. 对抗探针电池（/tmp 独立复刻 pytest 夹具，外层 LC_CTYPE=C）：变体 A 已关闭卡 rc=1 且输出
   「FAIL 方案关联卡已全部关闭/作废但状态仍为 '部分执行'」✓；变体 B 缺失卡 rc=0 + WARN 幽灵引用 ✓；
   变体 C 开发中卡 rc=0 ✓；探针 D（外层显式 LC_ALL=C）rc=1 ✓。同一探针 D 打在补强前脚本原文
   （git show 5582feb98 提取）rc=0 误放行——上一轮 F1 漏洞独立复现属实，补强实测有效。
4. 引擎同口径与消费面核验：server/board/plans.py:962-975 缺 entry → state 取空 → 不计 closed/作废、
   留活跃分母，与脚本缺失卡分支逐句一致 ✓；engine create_plan（plans.py:504-514）仅判 returncode，
   全仓无按 OK/WARN 文本解析 validate 输出的消费者——新增 WARN 行零破坏 ✓；
   退出码仅看 ERRORS（脚本 :402），WARNINGS 仅计数（:56 预初始化）✓。

发现与处置：

- **F3（轻 · 记录不改）**：locale 探测 fallback 为 C.UTF-8——若部署环境同时缺失 en_US.UTF-8 与
  C.UTF-8（极罕见最小镜像），LC_ALL 指向无效 locale 可能退回字节语义、8.2 再漏判。当前 macOS
  （locale -a 含 en_US.UTF-8）与 glibc≥2.19（内建 C.UTF-8）均覆盖，launchd 实证环境不受影响；
  若未来部署面收窄到此类镜像，应改为探测失败即显式报错而非静默 fallback。
- **F4（时点性说明，非缺陷）**：origin/main 复审期间又前进至 28c695fd7（wall/UI 两笔），
  与 validate-plans.sh、test_plans.py 零交集，不影响本轮结论，合入换板归环节②。
  教训笔记规则①的 `:-` 写法建议仍未修正（该文件在 main 侧不属本卡白名单），维持上一轮 F2 留痕待后续维护卡。

维护区四问核对：四问均为具体单选（否/有/否/否）非占位，说明句皆实情；引用工件抽查——
教训笔记 `docs/notes/2026-08-24-ccc-locale-sed-byteslice.md` 存在（28 行）且内容与卡内论证一致 ✓；
门禁证据日志 `~/.ccc/logs/exec/ccc068.test-evidence.log` 存在且记录 exit_code=0，回写区声明属实 ✓。

第三轮独立复核（同日第三席 · 只增不改前两轮记录 · 全部命令实跑）：

1. 换板零漂移链：脚本 blob `cf9c637efe` 在三代栈逐字节相同——ae8f8731c@670e84c3a、a68d089e2@fe31a4003、
   2f322d340@28c695fd7 三代 `git rev-parse <tip>:scripts/validate-plans.sh` 同值；卡文本 blob `8ccef540`
   换板前后同值。本审期间两次在途换板均未触及本卡内容，既有测试证据对现 tip 继续有效。
2. 独立探针（/tmp 自建夹具，非复制他席脚本，外层 `env -u LANG -u LC_ALL LC_CTYPE=C`）：
   变体 A 已关闭卡 rc=1 且输出「FAIL 方案关联卡已全部关闭/作废但状态仍为 '部分执行'」✓；
   变体 B 缺失卡 rc=0 + WARN 幽灵引用 ✓；变体 C 开发中卡 rc=0 ✓；探针 D 外层显式 `LC_ALL=C` rc=1 ✓；
   同一探针 D 打补强前脚本原文（blob `0001559e5`）rc=0 误放行——F1 漏洞与补强有效性双向实测属实 ✓。
3. 门禁复跑：`python3 -m pytest server/tests/test_plans.py -q` 常规与强制 C 双环境均 [100%] rc=0；
   全量 `python3 -m pytest server/tests -q` [100%] rc=0；`bash -n` 通过；退出码仅看 ERRORS（:401-404）、
   WARNINGS 仅计数（:55-56 预初始化）✓。
4. 引擎同口径复读：`server/board/plans.py:967` 缺 entry → state 取空、不计 closed、留活跃分母，
   与脚本缺失卡分支一致 ✓；`ls-remote` 分支 == 本地 HEAD == 2f322d340 ✓；实现提交不在 origin/main ✓；
   教训笔记 28 行属实 ✓。
5. 时点披露：第二轮机审块所记「`git diff fe31a4003..HEAD --stat` 仅脚本+卡」系其时点事实；其后换板至
   28c695fd7 使该 diff 面扩至含新继承的 main UI 提交（2462ce96b/28c695fd7），属换板预期非越权；
   复核收口时点 origin/main 已前进至 c59b2ddb3，与本卡零交集。工作区仍有两处非本卡未提交残留
   （mx/roadmap.md 一行、未跟踪 cards.index.jsonl），维持原样不动。

机审：通过

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：[否]。本卡为老板任务指令直派的存量缺陷修复，无关联方案文件；根因与口径论证已完整记录于本卡目标/实现节，供后续方案化引用。
2. **教训沉淀**：本卡是否产出可复用教训？[有]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：[有]。教训=C locale 下 BSD sed 字节级截断多字节字符类（B7 碰撞）；正文见 docs/notes/2026-08-24-ccc-locale-sed-byteslice.md（出卡侧随本卡一并提交，不属执行体分支白名单改动）。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：[否]。仅改 scripts/validate-plans.sh 内部行为（locale 强制+观测告警），结构/技术栈/路径零变化。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：[否]。部署门禁可靠性修复属既定质量主线，不构成近况/下一步变化。

## 验收区

**合入批准** · 日期：2026-08-24
- 判定：通过
- ✅ 人审 diff 后合入批准（北星 W2）
