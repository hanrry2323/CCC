# CCC 自动开发流程代码级分析 · 交叉验证 ccc01 调研

> 日期：2026-08-12 · 方法：只读分析 Engine 核心（server/engine/*）+ 出卡/合入脚本 + 最近 git 轨迹。
> 交叉验证对象：`docs/notes/2026-08-12-ccc-flow-research.md`（下称 ccc01）。
> 说明：`scripts/ccc-engine.py` 不存在——Engine 驱动已收敛为 Python `server/engine/main.py`（3589 行）＋
> `dispatch.py / pool.py / scheduler.py / store.py / observer.py`；`ccc-plan` 是 plan 文档内围栏，
> 由 `plan-to-cards.sh` 消费，无独立脚本文件。

---

## 一、代码层问题清单（按严重程度）

### P0 级

**P0-A 三源状态真值漂移：分支信封 / 磁盘卡 / sidecar 无单一权威**
- 位置：`store.py:_branch_envelope_state` + `main.py:_audit_round` + `runtime_state.py`。
- 引擎同一张卡有三种读取真值来源（`origin/codex/<stem>` 分支卡文件、磁盘 `docs/dispatch/*.md`、sidecar `{id}.json`）。
- 分支信封在 `git sync` 后读（`origin/codex` 是**上次 fetch 的快照**），磁盘卡在合入前永远旧值「待分派」，sidecar 是引擎私有。三者无事务边界，靠「收敛器」事后对账补漏。
- **证据链**：mx031/032 假机审正是「分支信封残留『已回写』→ 下轮读成 DONE → 无限机审」；ccc01 也点名此风险会在 REMOTE 认领协议中重演。代码里 `_mark_branch_card_state` 是**事后补丁**（机审打回时反向改分支卡），治标不治本——根因是「谁写终态」职责不清。
- 风险：并发多引擎实例 / Worker 同时推进同一卡时，双写冲突无 CAS。

**P0-B 机审通过证据的读取是非原子的「最近读取快照」**
- 位置：`main.py:_audit_evidence_passed`（读 `_worktree_hint_for` worktree 或分支信封）。
- 机审「通过」判定依赖 worktree 里被审 commit 与推送是否已完成；若执行体刚 push 而 worktree 未同步，机审会漏判或读到半成品。
- 与 P0-A 同源：证据链基于「本地 git 视图」，而 approve-merge 又基于 `origin/codex`（另一套视图），两视图可不同步 → 机审通过≠合入时可见。

### P1 级

**P1-A `approve-merge.sh` 本地卡回退路径破坏「分支信封唯一证据」契约**
- 位置：`approve-merge.sh` 第 366-379 行。
- 逻辑：先查 `origin/codex/<stem>` 卡含「机审：通过」；**否则回退 `check_audit "$path"` 读本地 `docs/dispatch` 卡文件**。card-evidence.sh 声明「只认 origin/codex」，但 approve-merge 开了本地回退后门——本地 main 卡头是合入前旧值，一旦 main 镜像被脏改会绕过机审证据。
- 这是与 ccc01「分支信封唯一真值」声称相矛盾的实现：证据读取不唯一。

**P1-B 出卡后卡路径用 `find ... | head -1` 定位，非精确匹配**
- 位置：`plan-to-cards.sh` 第 123 行。
- `find` 用 glob `*-${slug}.md` 前缀通配，slug 含 `-` 时可能命中多个同名歧义文件，`head -1` 取首个，非确定性。多 slice 同 title 派生同 slug 时风险更高。
- 应改为「出卡工具自身返回精确路径」而非回调扫描。

**P1-C SSE 长连接 / 异步确认无超时释放的隐性资源**
- 位置：`server/web/server.py` 挂起线程池（T43 长轮询，`test_longpoll_timeout_returns_empty` flaky 已暴露）。未设全局 idle 超时兜底清洗挂起 socket。

**P1-D Worktree 清理与并发派发竞态**
- 位置：`main.py:_cleanup_closed_worktrees` 与 `_claim_running_marker`。
- `_cleanup_closed_worktrees` 扫已关闭卡删 worktree；同一轮 `run_once` 可能同时对刚 submit 的卡写 marker。若卡状态切换（关闭后又被 `_hold_infra_failure` 回待分派），worktree 被提前删除 → 重派时重建。已有 `_WORKTREE_FAILURES` 计数兜底，但无「worktree 归属卡正在使用」互斥锁。

### P2 级

**P2-A 多个脚本硬编码路径/IP/解释器**
- `approve-merge.sh`: `fan@192.168.3.116`、`prod_repo="/Users/fan/program/CCC"` 硬编码（第 252-255、497、535 行）。仅 `CCC_BOARD_URL` 可覆写，SSH 主机不可。
- `observer.py`: 第 865 `/Users/fan/.config/opencode/opencode.json`、第 1091/1117 `/Users/fan/.ccc/logs/exec` 硬编码默认。
- `card-evidence.sh`: 第 68 行 `python3`（非 `$CCC_PYTHON_BIN`）；第 67 写 `/tmp/ccc-ready-$$.json`。
- `validate-plans.sh`: 第 28 行裸 `python3`（非 `$CCC_PYTHON_BIN`）。
- 溢出风险：只在 2017 本机运行无碍，但 M1（`/Users/apple`）与 2017（`/Users/fan`）同为执行面，任何脚本绑死一个用户路径即跨机失效——正是 git 轨迹里 `dd72ca4f fix(chat): 心跳拉起用远端 ~/program/CCC 路径（2017 路径不适用于 M1）` 反映的那类问题。

**P2-B `approve-merge.sh` `--close-only` 使用无证据复核**
- close-only 只凭「代码已在 main/外仓」的人工判断，脚本不校验业务仓分支是否真合入业务 main（`print_external_repo_hint` 只打印提示不 gate）。非 ff 合入时绕过机审钉漂移校验（第 387-403 行只在信封路径执行）。低风险但属「人工豁免」，应输出告警标记。

**P2-C `validate-plans.sh` 8.2 用本地卡文件对账**
- 第 168 行 `find docs/dispatch ...` 读本地卡头判「已关闭」；若本地 main 滞后（合入前旧值），会把未关闭卡误判为已关闭 → 方案收尾误报。与 P0-A 同根：本地视图非权威。

**P2-D `plan-to-cards.sh` 多 slice 循环内逐卡 find + 校验，无整体回滚**
- 中间某卡 validate 失败即 `exit 1`，前面已生成的卡留在磁盘未 commit（脏卡）。应「全量生成 → 全量校验 → 单次 commit」，失败整体清理。

**P2-E `pool.py` 轻量竞态**
- `submit()` 用 `existing.is_alive()` 判重：线程刚结束但未 `reap` 时 `is_alive()` 已 False，可重复 submit 同 id。余量小但非严格串行。

### P3 级（低）

- `main.py:2887` `return` in `finally`（SyntaxWarning，pytest warnings 出现）——语义易误读。
- Worker 认领超时 `claim_ts` 无时区强校验，`fromisoformat` 失败即 `elapsed=0`（永远 in_flight，永不回收）。
- `observer/metrics` 无 DB 持久化，健康指标「循环基线」数据采样后即弃（ccc01 §四-3 需要可视化时数据已不连续）。

---

## 二、最近 git 轨迹修复模式 → 系统性弱点

`git log --oneline -25` 的实际主题分布（2026-08-12 前后）：

1. **chat/bridge 主题占多数**（约 60%）：`699fd901`（原生历史）、`bdaf9a27/2a1d2c24`（bridge 心跳/免 token）、`9499dea8`（前端直连 CORS+config）、`d79b979b`（http.client 流改）、`49a3c47b`（do_OPTIONS/do_POST）、`dd72ca4f/53fa364a/3e631425/844f68b4`（config 兜底 + 双机路径）。**修复模式**：反复围绕「M1 与 2017 双机路径不一致」「launchd 出站流卡住」「token 直连 401」打补丁 —— 印证 P2-A 双机硬编码路径 + config.env 兜底链是**脆弱点**。
2. **test 隔离模式**：`a0bb90c9/ac5db718/ae4c7fa0/b7839e55` 连续 4 个 commit 都是**测试环境隔离/等待容限**（monkeypatch 对话桥隔离、deadline 放宽）——说明测试对**本地 config.env / 生产侧状态泄漏**高度敏感，反证生产配置与测试环境未彻底隔离（正是 P1-A 本地回退的镜像）。
3. **机审死循环修复**：`_mark_branch_card_state`（main.py 328-374）——多次打补丁解决「分支信封读旧值→无限机审」。**系统性弱点**：状态真值源不唯一（P0-A），每次都是「加一个反向写」而非「统一真值」。

**结论**：最近修复高频集中在「双机路径不一致」「状态漂移」「测试受生产配置污染」三类——这三类在代码层都能在 P0-A / P2-A / P1-A 精准对应，说明**这些不是偶发 bug，而是架构级真值管理与配置注入的系统性弱点**。

---

## 三、与 ccc01 调研报告的交叉验证

| ccc01 结论 | 代码层印证 | 结论 |
|-----------|-----------|------|
| P0-1 合入批准单点人工瓶颈 | approve-merge 是唯一人审动作，脚本层无 `--auto` 模式 | ✅ 印证（流程级，非代码缺陷） |
| P0-2 机审打回→死循环已修复但需警惕 | `_mark_branch_card_state` 是补丁式反向写，三源无单点 | ✅ 印证实锤——根因在 P0-A |
| P1-3 Worker 池未真正运转 | worker-claim.sh 就位，但 `REMOTE → 保持待分派（不标执行中）`、`_claim_round` 仅靠读 git 卡头无原子认领态 | ✅ 印证：认领协议依赖 git 视图，无原子认领（ccc01 提到「CAS 未实现」在代码层确认） |
| P1-5 循环健康指标未可视化 | observer/metrics 采样即弃，无 DB | ✅ 印证 |
| P2-6 Delivery Gate 未完成 | validate-plans 8.2 依赖本地卡视图（P2-C），方案级收尾易误报 | ✅ 印证且指出实现层隐患 |
| P2-8 看板无实时推送 | 依赖 12s 轮询 | ✅ 印证 |
| P3-9 注册表双源漂移 | executors.json 未在代码层强校验与 config 对账 | ✅ 印证 |
| **（ccc01 未覆盖）** | P1-B find|head 歧义、P2-D 多 slice 无回滚、approve-merge 本地回退后门 | ➕ 本分析新增代码级发现 |

**交叉验证结论**：ccc01 的瓶颈判断方向正确，且**大多数瓶颈在代码层都能找到直接证据**（尤其状态真值漂移是 P0-2 / 认领 CAS / 方案收尾 三个 ccc01 问题的共同根因）。但 ccc01 偏「流程拓扑」视角，本分析补充了 4 个**纯代码层**隐患（P1-B / P2-D / P1-A 后门 / P2-E），是 ccc01 未提及的。

---

## 四、可立即执行优化清单（低风险 · 高收益优先）

按「改动小、不动真值架构」的保守原则排序——在老板授权前，避免动 P0-A 这类需要架构决策的部分：

### 立即（纯脚本层，零架构风险）

1. **消除 approve-merge 本地回退后门**（P1-A）
   - 改：`check_audit` 回退路径仅保留在显式 `--close-only` 时允许；非 close-only 一律强制分支信封证据。改动 3 行，关门一个证据后门。
2. **plan-to-cards 改精确路径**（P1-B）
   - 改：`new-card.sh` 末尾 `echo "$CARD_PATH"` 输出精确路径；`plan-to-cards.sh` 用命令替换捕获，替代 `find | head -1`。消除同名歧义。
3. **多 slice 整体回滚**（P2-D）
   - 改：先全量生成到临时清单，全量 validate 通过后再单次 `git add+commit`；失败 rm 全部。当前是逐卡 commit 不可回滚。
4. **路径/解释器变量化**（P2-A）
   - 改：`approve-merge.sh` 的 SSH host 与 prod_repo 挪到 `CCC_SSH_HOST` / `CCC_PROD_REPO` 环境变量（默认值保留）；`card-evidence.sh` / `validate-plans.sh` 的 `python3` 统一 `$CCC_PYTHON_BIN`。删掉所有 `/Users/fan` 裸路径。
5. **validate-plans 8.2 改读权威源或降级为 warn**（P2-C）
   - 改：交叉引用本地卡头时，仅当其不属于「待分派/已回写」（本地滞后态）才告警；或降级为黄色警告不判 error，避免误报方案已收尾。

### 短中期（需一点设计，不动真值权威）

6. **认领态原子化**（P0-A 的一部分，先从 REMOTE 收窄）
   - 改：`_claim_round` 里认领成功写一条 `{id}.claim` sidecar（引擎私有、原子），替代「读 git 卡头判断认领」。Worker 侧认领也写同 sidecar → 引擎/Worker 共享同一状态文件，消除跨视图漂移。
7. **测试隔离固定模式**（呼应 git 轨迹）
   - 改：全局 `conftest.py` monkeypatch 掉 `_chat_bridge_url()` / 清 `config.env` 缓存，从根上杜绝「测试受生产配置污染」类 flaky（本次已连续 4 个 commit 修同类问题，应固化止损）。
8. **认领超时兜底**（P3）
   - 改：`claim_ts` 解析失败时用文件 mtime 兜底，避免「解析失败 → elapsed=0 → 永不回收」。

### 需老板拍板（架构级，不建议擅自动）

9. **状态真值单一化**（P0-A 根治）——引入「磁盘卡头唯一权威」或「sidecar 唯一权威」二选一，收敛器改为校验而非修数据。影响面大，需先出方案。
10. **合入批准半自动**（ccc01 高杠杆）——`approve-merge --auto`，仅对全自动门禁通过且零代码改动的文档/配置卡开放，风险低、收益高。

---

## 五、一句总结

代码层印证了 ccc01 的三大瓶颈（合入人工、机审死循环、Worker 未运转），并额外指出**状态真值是软肋**：分支信封 / 磁盘卡 / sidecar 三源无单点、批准与验证都读「本地 git 视图」快照——这是近期所有状态漂移 bug 的共同根因；先做 5 项脚本层小改即可消除大部分低风险隐患，架构级真值统一另议。
