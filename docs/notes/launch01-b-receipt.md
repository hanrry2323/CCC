# 回执 · LAUNCH-01-B 修 registry 脏数据（5 行 status 标注）· 2026-09-13

> 执行席：CCC 执行窗（写码席）· worktree `/Users/fan/program/CCC-wt/launch01-b`（分支 `codex/launch01-b`，基 main 00a1933ed）
> 任务书日：2026-09-12 · 实作：2026-09-13
> 改动面：仅 `docs/projects/registry.yaml`（红线①）；未触 `server/**`、`scripts/**`。

## a) 改前基线（卡前缀派生，07-运行先贴）

```text
python3 -c "from server.board.registry import card_prefixes; print(card_prefixes())"
{'cla': 'cla', 'qb': 'qb', 'mx': 'medio-0', 'xy': 'xianyu', 'hp': '知识库',
 'tst': '管线自检', 'cd': 'ccc-demo', 'clw': 'clwarp'}
```

在此之上还有两个派生（同样贴出供比对基准）：
- `forbidden_prefixes()` = `{'ccc','qh'}`
- `taskable_names()`（含 cla/clawmed-ccc/hp 等，null-prefix 行 taskable:false 不进）
- `check_path_locations()` = `[]`（绿）

## b) 脏行逐条处置表（5 行 × 依据 × 处置）

| # | id | 改前 status | 处置 status | 依据 |
|---|----|------------|------------|------|
| 1 | ai-loop-router | archived | **retired** | 退役实据在职：`server/config/config.env` 三处注记（L17「2026-08-24 中转站退役拆除」、L18「原 RELAY_UPSTREAM_URL/KEY(127.0.0.1:6102 ai-loop-router) 已删除」、L26「2026-08-24 起直连 Claude CLI，不再走 6100 中转」）；运行时取证（本次）：6100/6102 均无监听、launchd 无条目、无进程。config.env 注记 = 当日已有书面实据，非仅凭自报 → 不标「待核」，标 retired |
| 2 | qx-map | active | **foreign** | 任务书①定调：量化线知识地图/外脑，跨线项目，CCC 运行时不依赖（registry 行内 role 自述 D2）；补 prefix 不便（无 CCC 卡前缀），按任务书④「status: foreign 标注保留 id」 |
| 3 | qx-observer | archived | **foreign** | 任务书①定调：量化线；2017 有仓体（mac2017-apps）但未挂 Engine、status 原 archived；跨线非 CCC 业务 → foreign |
| 4 | clawmed-ccc | archived | **retired** | 该行是 **ash 重复登记行**（本体在 `prefix: cla` 行，status:active 在役，见行 9-22）——本行重复登记已无业务指向（无 cla 卡头来源），退役指「重复登记行退役」非项目整体；处置 retired |
| 5 | ccc-relay-runtime | archived | **retired** | 退役记录：qx-map `AGENTS.md` L50/L112/L138「🛑 已退役（:4000/:4002 无监听 2026-08-25 核实；launchd com.qx.relay-4000 已卸载，目录仅剩日志）」「ccc-relay 已退役离线 2026-08-02」；本仓 docs/archive 多份交接文档亦载 → retired |

> 说明：本仓 `AGENTS.md` 为空壳无退役记录（grep 0 命中）；退役证据落在 qx-map `AGENTS.md` + 本仓 `docs/archive/` 交接族（`fleet-hygiene`/`vertical-qx`/`NEXT-DUAL-TRACK`/`reset-demo-fleet`）+ `server/config/config.env` 注记，均已列档取证。

**同步**：`updated_at: "2026-08-26"` → `"2026-09-13"`。

红线合规核查：
- **禁删行**：未删任何行，仅 5 处 status 值变更 + updated_at（diff 见下节 f）。
- **ai-loop-router 待核条款**：任务书③「查无实据就标 unknown + 待核」→ 因取到 config.env 书面实据，判定为有实据 → 标 retired，不触发 unknown 分支。
- **只改 registry.yaml**：单文件改动；commit 不含其他业务文件。

## c) 改后校验输出

```text
── card_prefixes()（PREFIXES 派生，须与改前一致）──
{'cla': 'cla', 'qb': 'qb', 'mx': 'medio-0', 'xy': 'xianyu', 'hp': '知识库',
 'tst': '管线自检', 'cd': 'ccc-demo', 'clw': 'clwarp'}
  ✓ 与 a) 基线逐键一致

── forbidden_prefixes() ──
forbidden: ['ccc', 'qh']          ✓ 不变

── taskable_names()（is_taskable 判定）──
['cla', 'clawmed-ccc', 'hp', 'hp 服务仓', 'medio-0', 'tst', 'xianyu', '知识库', '管线自检']   ✓ 不变

── check_path_locations() ──
[]                                  ✓ 绿

── server/tests/test_project_registry.py ──
11 passed                              ✓ 全绿
```

PREFIXES 仍=cla/mx/xy/hp/tst 5 个可出卡前缀（cd/clw 为 archived 列目录可见不进可出卡集）；is_taskable 判定不变（5 条 null-prefix 行 taskable:false 本就进不了 taskable_names，status 标注不改变量）。

## d) status 字段消费面核实（防引入运行时回归）

`status` 字段当前消费面：`server/board/roadmap.py`（方案状态）与 `server/web/wall/result_report`（运行时状态）均为**各自独立字段**，无一处消费 `registry.project.status`；registry 消费者只读 `prefix/taskable/forbidden`（`registry.py` 导出）。`server/tests/test_project_registry.py` 断言集只覆盖 PREFIXES/forbidden/taskable/location/isolation，status 值自由。→ 新增 retired/foreign 两值无消费方冲突。

## e) 执行记录

- worktree 脏数自证（动手前，任务书⑥）：`git status --short`（除 `.venv-hub` 符号链接）= **0**。
- 改动命令：5 处 `status:` 值替换 + `updated_at` 更新（Edit 逐条精确替换，未 `git add -A`）。
- diff 全文（`git --no-pager diff docs/projects/registry.yaml`）：6 处 `-`/`+`（updated_at 1 + status 5），无增删行。

## f) commit sha

- 本次人工 commit（含 registry 5 行 + 本回执）：`chore(launch01-b): registry 5 条 prefix=null 脏行补 status 标注（retired/foreign）+ updated_at`。
- commit 自引用限制（launch01-a 同款）：sha 由主脑以 `git log --oneline -1` 核验本分支 HEAD；`docs/projects/registry.yaml` 的改动随本 commit 落地。
- **push 状态**：任务书③「commit 后禁推 main（推工作分支允许）」→ 推 `origin/codex/launch01-b`。

## 附录 · 回执完整性自查

- 改前基线：见 a（baseline card_prefixes + forbidden + taskable）。
- 逐行处置表 5 行×依据：见 b（含 cla 重复登记行发现）。
- 改后校验输出：见 c（含单测 11 passed）。
- commit sha：见 f（自引用限制标注）。