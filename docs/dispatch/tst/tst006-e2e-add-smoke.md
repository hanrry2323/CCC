# 任务卡 tst006 · 管线E2E体检·tst仓新增add纯函数与pytest单测（DSH 执行）
> 批准：老板合入批准 · 2026-08-26

> 关联：产线E2E实弹验证（老板授权·外脑起草） · 执行体：DSH · 验收：DSH · 状态：已关闭· 派发：engine · 项目：tst · 日期：2026-08-26




## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/tst/README.md`
- 方案池：`docs/projects/tst/plans/`（关联方案见卡头「关联」）

## 目标

在 tst 业务仓新增纯函数 `add(a, b)`（返回 `a + b`）与单元测试 `test_add`（断言 `add(2, 3) == 5`），pytest 真实跑通并按流程回写。

> 本卡为产线端到端实弹验证卡（老板授权 · 外脑起草）：过程数据比结果重要。
## 实现

1. 新增 `math_utils.py`（仓根）：

```python
def add(a, b):
    """返回两数之和（纯函数：无 IO、无副作用、无全局状态）。"""
    return a + b
```

2. 新增 `tests/test_math_utils.py`：

```python
from math_utils import add


def test_add():
    assert add(2, 3) == 5
```

3. 白名单仅上述两个新文件；不建 Python 包、不改 README、不加任何依赖或配置文件。
## 红线（先看）

1. 白名单仅 `math_utils.py` 与 `tests/test_math_utils.py` 两个新增文件，禁触仓内其他任何文件（含 README）。
2. 禁直推 `main`；只推本卡分支。禁写 `## 机审区` / `## 验收区

**合入批准** · 日期：2026-08-26
- 判定：通过
` / 置「已关闭」。
3. 测试必须真实执行：禁 mock / 伪造 pytest 结果；回写区只写真实退出码与真实输出摘要。
## 范围

- `math_utils.py`（新增）
- `tests/test_math_utils.py`（新增）
## 步骤

1. Read 本卡全文；确认业务 worktree 内仓库状态干净（`git status`）。
2. 按「实现」节新增两个文件；在仓根执行门禁命令自测，确认退出码=0 且输出含 `1 passed`。
3. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
4. 回写区填实现说明/自测结果/commit hash 与 push 证据；**维护区四问逐项填写——勾选符必须落在问题行的方括号内**（如 `[否]`/`[有]`），说明行写一句实情（docgate 机械校验该格式，格式错会被机审打回）。
5. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。
## 验收标准

1. `math_utils.py` 含 `add` 函数、`tests/test_math_utils.py` 含 `test_add`，两文件真实存在于 tst 业务仓工作目录（biz_worktree）。
2. 门禁测试命令真实执行且退出码=0（以 wrapper 独立证据日志为准，不以回写区自述为准）。
3. 卡分支相对 main 的代码 diff 仅含白名单两个新增文件。
4. 卡头=已回写；维护区四问勾选落位问题行方括号、说明非占位。
## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：python3 -m pytest tests/test_math_utils.py -q
编译：
lint：
范围：false
## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成  四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 ；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：DSH · 日期：2026-08-26

> 本区为第 9 次回写（第 8 次回写后本卡已两度获机审「通过」（落卡提交 `df368babe`、`b671fb636`），卡分支又先后并入 origin/main（文档仓 `d62d0ba87`、`0e4e78873`），本轮 Engine 再次派发；按执行体 SOP 对既有实现全量复核：业务仓两白名单文件与卡内代码块逐字 diff＋门禁复跑＋git 跟踪文件清单＋远端同步与祖先关系核验），业务仓零代码改动。

- **实现说明**：按卡「实现」节的两个白名单文件已在 tst 业务仓真实存在且与卡内代码逐字一致——`math_utils.py`（仓根，`add(a,b)` 纯函数返回 `a+b`，3 行）、`tests/test_math_utils.py`（`test_add` 断言 `add(2, 3) == 5`，5 行）；未建 Python 包、未改 README、未加依赖或配置文件；第 9 轮 `git ls-files` 复核跟踪文件仅 README.md＋两白名单文件，`git diff origin/main...HEAD --stat` 仅含白名单两个新增文件（+3/+5），无越界（`__pycache__/` 为 pytest 本地运行产物，未跟踪未提交）。
- **测试结果**：门禁命令 `python3 -m pytest tests/test_math_utils.py -q` 在业务仓根真实执行（第 9 轮复跑）：退出码=0，输出 `. [100%] 1 passed in 0.05s`；另以临时期望文件对两白名单文件做逐字 diff，均完全一致。
- **push 证据**：commit `e037d42`（tst006: 新增 add 纯函数与 pytest 单测（管线E2E体检））第 9 轮复核仍为业务分支 HEAD 且与远端同值（fetch 后 `git rev-parse origin/codex/tst006-e2e-add-smoke` 返回 `e037d42486e689f1e71358aff45a926e832e7f87`＝本地 HEAD）；`origin/main`（`1ceae1b`）经 fetch 后 `git merge-base --is-ancestor` 核验为 HEAD 直接祖先（无需 rebase），未直推 main；文档仓本卡分支第 9 次回写 commit 见下方 git log，push 后本地与 `origin/codex/tst006-e2e-add-smoke` 同值。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[否]（方案推进「部分执行」或「已完成」，关联卡补全）
   - 说明：卡头「关联」无方案编号——本卡为老板直接授权的产线E2E实弹验证卡；第 8 轮复核方案池（`docs/projects/tst/plans/001-pipeline-smoke.md`＝tst-plan-001）仍仅关联 tst002–tst004 且已完结，与本卡无关，无需同步。
2. **教训沉淀**：本卡是否产出可复用教训？[无]（有 → 业务仓 lessons.md 或 CCC docs/notes/YYYY-MM-DD-<prefix>-lessons.md 新增一条）
   - 说明：常规最小冒烟实现且门禁一次通过，无新增可复用教训。
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[否]（是 → 项目档案 `docs/projects/<prefix>/README.md` 同步更新）
   - 说明：仅新增两个代码文件，项目路径、技术栈与目录约定均未变化，档案无需更新。
4. **线路图**：项目近况/下一步是否变化？[否]（是 → `docs/roadmap.md` 或档案「线路/近况」更新）
   - 说明：本卡为管线自检例行执行例，项目近况与下一步无里程碑级变化。

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）

## 执行提示

- 项目：tst（CCC 管线自检专用（冒烟/E2E，无真实业务））

- 项目仓（只读参考）：/Users/fan/program/apps/ccc-tst（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 开发技能与命令：
  - [domains::projects::常用命令] 常用命令 - 运行测试： 全量 - 单模块测试： - 代码检查：
  - [domains::projects::常用命令] 常用命令 - 运行测试： - 单模块测试： - 代码检查： - 编译检查： - 出卡： - 看板：

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：tst（CCC 管线自检专用（冒烟/E2E，无真实业务））

- 审查重点：代码实现质量、边界条件、异常处理、架构隐患

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，

    打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。

## 机审区

**DSH 机审席 · 2026-08-26 · severity：轻**

本轮为引擎再次派发的第 4 轮独立复审；上轮机审（落卡提交 `c4dcce5cd`，基线 `f9bccaeac`）之后，卡分支已并入 `origin/main`（热修 `42cedc0ed`，merge＝`ab0dabd02`），本轮 Engine 未派发新执行体回写、业务仓零代码改动（HEAD 仍 `e037d42`）；本席对当前状态全量重验，不引用执行体自述、不沿用上轮机审结论。业务仓 `/Users/fan/program/apps/.ccc-wt/tst/tst006`（分支 `codex/tst006-e2e-add-smoke`），文档卡副本 `/Users/fan/program/CCC-wt/tst006/docs/dispatch/tst/tst006-e2e-add-smoke.md`（审查基线＝文档仓 HEAD `ab0dabd02`）：

1. 范围核对：业务仓 `git fetch` 后 `git diff origin/main...HEAD --name-status` 仅 `A math_utils.py`、`A tests/test_math_utils.py`（`--stat` +3/+5 纯新增），`git ls-files` 仅 `README.md`＋两白名单文件；未跟踪项仅本地 pytest 运行产物 `__pycache__/`、`tests/__pycache__/`、`.pytest_cache/`（均未入提交）——白名单外零越界。文档仓 fetch 后 `git diff origin/main...HEAD --name-status` 仅触本卡 md 一个文件（merge-base＝`origin/main` 尖端 `42cedc0ed`），分支侧提交全部为本卡回写/机审落卡/Engine 信封/合并 main，无越界文件。
2. 内容逐字比对：以脚本抽取卡「实现」节两个 python fence 与业务仓文件做字节级比对——`MATH_VERBATIM_MATCH=True`、`TEST_VERBATIM_MATCH=True`（3 行/5 行），实现即卡所规定，无夹带改动。
3. 门禁复跑：在业务仓根真实执行 `python3 -m pytest tests/test_math_utils.py -q` → 退出码=0（`GATE_EXIT=0`），输出 `. [100%] 1 passed in 0.01s`，与回写区自述一致。
4. push/红线核验：业务仓 fetch 后 HEAD＝`e037d42486e689f1e71358aff45a926e832e7f87`＝`origin/codex/tst006-e2e-add-smoke`（本地远端同值）；`origin/main`＝`1ceae1be` 经 `git merge-base --is-ancestor` 核验为 HEAD 直接祖先（未直推 main、无需 rebase）；唯一业务提交作者/提交者均为 `qx-observer <qx-observer@local>`（身份未改写）。文档仓 fetch 后 HEAD＝`ab0dabd02`＝远端卡分支同值、工作树干净；`origin/main`（`42cedc0ed`）为其祖先，且上轮机审提交 `c4dcce5cd` 不在 `origin/main` 上——main 版卡仍为占位（状态：待分派），与派发口径一致。卡相对 main 版逐节 diff：目标/基准文件/实现/红线/范围与验收标准/门禁各节字节级一致（`GOAL_IMPL_REDLINE_SCOPE_UNTOUCHED` / `ACCEPT_GATE_UNTOUCHED`），差异仅四处——状态行（待分派→已回写）、回写区、维护区、机审区；无 `## 验收区` 节，「已关闭」仅出现于红线/提示模板文本，状态落位「已回写」。
5. 维护区四问核对（P1-b 机械判据）：四问均单选落位问题行方括号（[否]/[无]/[否]/[否]），说明各为一句实情、非空非占位；全文 grep 无 `[是/否]`/`[有/无]`/「占位待填」模板残留。抽查第 1 问引用工件 `docs/projects/tst/plans/001-pipeline-smoke.md` 真实存在（1687 字节），其卡头「关联卡：tst002, tst003, tst004 · 状态：已确定 · 进度：1/1 (100%)」与「与本卡无关、无需同步」的结论一致。
6. 对抗式找茬 0 发现（风险论证）：实现为卡内逐字锁定的纯函数＋最小断言，无 IO/副作用/全局状态/新增依赖；`add` 对非数值入参抛 TypeError 是 `+` 的固有语义，卡已锁定最小实现，扩展反越白名单；根导入 `from math_utils import add` 由门禁命令 cwd 进 sys.path 保证且本轮真实跑通，补 conftest/pyproject 反触「不加任何依赖或配置文件」红线。观察项（不计缺陷、非打回原因）：①本文档 worktree 卡分支 upstream 误指 `origin/main`（`branch -vv` 显示 ahead 22），存在误推风险——本席本次落卡推送即改用显式 refspec `HEAD:refs/heads/codex/tst006-e2e-add-smoke` 规避，建议后续修正 upstream 配置；②维护区第 1 问说明称方案「已完结」，方案头字段实为「状态：已确定 · 进度 1/1 (100%)」，语义同指已收尾、实质结论（与本卡无关、无需同步）不受影响，属措辞漂移；③历轮审计文本称未跟踪产物仅两处 `__pycache__`，实测另含 `.pytest_cache/`（同为本地 pytest 产物、未跟踪未提交），记录性勘误。severity 计分：影响面 1（管线自检专用仓）＋改动深度 1（纯新增 8 行）＋红线邻近 1（零接触）＝3 → 轻；0 处需就地修复。

机审：通过
