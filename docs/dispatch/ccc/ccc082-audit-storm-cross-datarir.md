# 任务卡 ccc082 · 并发机审风暴防线跨 DATA_DIR 验证与加固（DSH 执行）

> 关联：环节②交接指令(S116-01)卡1 · 执行体：DSH · 验收：DSH · 状态：已回写（机审打回修复·第2轮回写） · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

核验防双审机制 `_audit_marker_alive`（server/engine/main.py）在双 engine 使用不同 DATA_DIR（即不同 log_dir）时是否仍能挡住并发机审风暴（复现 ccc078 33 实例场景的等价小规模模型）；有缺口即加固，无缺口则补探针断言固化防线。

## 红线

- 白名单：server/engine/main.py（marker 机制相关函数）、server/tests/ 新增或修改测试。
- 实验只用临时目录 DATA_DIR（tmp_path），禁止触碰生产 ~/.ccc/data 与生产 engine.lock；禁止启动第二个生产 engine 进程。
- 禁改 OPENCODE_GO_API_KEY。

## 范围

- 复现模型：同机两个进程各自 DATA_DIR_A/B 对同一 work_id 各自 claim/alive 判定——分析共享面（log_dir 不同则标记互不可见是否导致双审并行）。
- 若确认穿透：给出最小加固（如全局锁文件/注册表级 in-flight 登记），保持向后兼容。
- 若无穿透：补一条「跨 DATA_DIR 双 claim」探针单测固化当前行为语义并文档化边界。

## 步骤

1. 读 _audit_marker_alive/_claim_running_marker/_write_running_marker 与 audit_pool.alive_ids 防线，画共享面。
2. tmp 双目录实验（pytest 形态），记录双审与否及证据。
3. 按结论实施加固或固化断言。

## 验收标准

- [ ] 结论明确（穿透/不穿透）且附实验命令与输出
- [ ] 新增至少一条回归单测覆盖该场景
- [ ] 生产文件零触碰（git status 干净除白名单）

## 回写要求

- 回写区写明实验设计、结果、diff 要旨；维护区四问如实。

## 人工批注

（留空）

## 回写区

（执行体回写时填写）

### 结论

**穿透成立 → 已加固**。防双审共享面原只有两处，均锚定单个 DATA_DIR：`DATA_DIR/engine.lock` 单实例锁（main.py `_acquire_engine_single_instance`，不同 DATA_DIR 各持各锁互不排斥）与 `{EXECUTOR_LOG_DIR}/{id}-audit.running` 标记（`_audit_marker_alive` 只读本 log_dir）；外加进程内 `audit_pool.alive_ids()`（pool.py 模块级单例 `_AUDIT_POOL`，天然进程私有）。双 engine 各用不同 DATA_DIR 时三者全失效 → 对同一卡并发机审。

### 实验设计（tmp 双目录等价小模型 · pytest 形态）

- 视角 A：`_claim_running_marker(log_a, "w1-audit") + _refresh_running_marker_child(log_a, "w1", <真实 sleep 子进程 pid>, phase="audit")`——生产同款两步认领，判活走 PID 存活路径不依赖宽限期分支。
- 视角 B：对 `log_b`（另一 DATA_DIR 的 log_dir）调 `_audit_marker_alive(log_b, "w1")`。
- 对照组：同 log_dir 判定。全程 tmp_path，零生产触碰。

加固前实测输出（`python3 -m pytest server/tests/test_engine_audit_cross_datadir.py -v -s`）：

```
[same-log_dir] alive=True      ← 同 DATA_DIR 防线有效
[cross-log_dir] alive=False    ← 跨 DATA_DIR：B 判「可再审」→ 双审穿透
markersA=['w1-audit.running'] / markersB=absent
```

### 加固 diff 要旨（commit de08ca4bc，+247/-2）

- 新增 `_audit_inflight_registry_dir()`（main.py）：用户级全局机审注册表锚点，`CCC_AUDIT_REGISTRY_DIR` 环境变量优先（测试隔离），默认 `~/.ccc/data/audit-inflight`——生产所有 engine 同机同用户必互见，配错 DATA_DIR 也逃不出锚点；条目格式与 running 标记一致。
- `_write_running_marker()`：`{id}-audit` 标记原子镜像进注册表（认领 :3282 与子进程刷新两路都经此函数自动覆盖；best-effort 失败仅告警不打断派发）。
- `_clear_running_marker()`：机审收尾同步清注册表条目，防跨 DATA_DIR 假在途。
- `_audit_marker_alive()`：本地未命中「或判死」后追加查注册表（`_marker_raw_alive` 单一判定源：排除 engine 自身 PID、工作者 PID 存活优先、宽限期兜底），任一共享面判在途即在途；死条目顺手回收，mx055 可重审语义不回退。
- 向后兼容：单 DATA_DIR 行为逐字不变（本地命中即短路）；旧版 engine 混跑时行为退回现状不变差；孤儿清扫器零新增（死条目由判定路径顺手回收）。

### 自测结果

- `python3 -m pytest server/tests/test_engine_audit_cross_datadir.py -q` → 6 passed（跨目录挡双审/同目录语义不变/注册表兜底挡双审/死条目过期回收并清理/收尾双清/plain 执行标记不镜像）。
- `python3 -m pytest server/tests/test_engine_audit_marker.py -q` → 7 passed（既有 mx055 回归无回退）。
- `python3 -m pytest server/tests/test_engine_{main,dispatch,scheduler,audit_backfill,v2v3_gate,runtime_contract}.py server/tests/test_infra_resilience.py -q` → 206 passed。
- `python3 -m ruff check server/engine/main.py server/tests/test_engine_audit_cross_datadir.py server/tests/conftest.py` → All checks passed。
- test_http_api 2 个失败（TestConversation 配置类）经 git stash 基线复跑证实为预存失败，与本改动无关。

### push 证据

分支 `codex/ccc082-audit-storm-cross-datarir`，实现提交 `de08ca4bc`，push 后 `git rev-list --left-right --count origin/codex/ccc082-audit-storm-cross-datarir...HEAD = 0 0`（远端零偏差）；工作区干净（git status 空）。

### 第2轮回写（2026-08-25 · 机审打回后修复）

**打回原因（实锤取证）**：第1轮机审未进入实质审查即被机械门禁拦下——`~/.ccc/logs/exec/ccc082.audit.log`：`[dsh-auditor] 机械门禁：维护区未完成 → 机审打回（不跑 DSH）／机审：不通过（维护区未完成）`；对应引擎自动落分支信封提交 `08bf7ea2f`（状态→待分派·重试中）。本地用 docgate 复现同因：

```
python3 -c "from server.board.docgate import verify_maintenance; print(verify_maintenance('docs/dispatch/ccc/ccc082-audit-storm-cross-datarir.md', '.'))"
→ (False, ['Q2 声明了有教训沉淀[有]，但说明中未引用任何 docs/notes/*.md 或 lessons.md 文件'])
```

根因：第1轮 Q2 勾 [有] 但说明只称「落 docstring 与回写区」，未引用任何 lessons 文件路径，违反 docgate.py:329-341 契约。

**修复内容（本轮全部改动，代码零变更）**：

- `docs/lessons.md`：追加 Lesson 58「跨进程互斥面若全锚定同一可配置目录，多实例各配各的目录即全线失效（ccc082）」，四段式（问题/根因/修复/如何应用）——把第1轮已声明的教训沉淀做成事实。
- 本卡维护区 Q2 说明行改为引用 `docs/lessons.md` Lesson 58；状态行→已回写（第2轮）；回写区补本节。`server/engine/main.py` 与 `server/tests/` 相对第1轮实现提交 `de08ca4bc` 零改动。

**docgate 复测**：同命令 → `(True, [])` PASS（修复前 FAIL 证据见上）。

### 第2轮自测结果（实现未变，全量复跑）

- `python3 -m pytest server/tests/test_engine_audit_cross_datadir.py -q` → exit=0，6 passed in 0.58s。
- `python3 -m pytest server/tests/test_engine_audit_marker.py server/tests/test_engine_{main,dispatch,scheduler,audit_backfill,v2v3_gate,runtime_contract}.py server/tests/test_infra_resilience.py -q` → exit=0，213 passed in 38.79s。
- `python3 -m ruff check server/engine/main.py server/tests/test_engine_audit_cross_datadir.py server/tests/conftest.py` → All checks passed。
- 生产零触碰复核：测试全程前后 `ls ~/.ccc/data/audit-inflight` → No such file or directory（conftest 将 `CCC_AUDIT_REGISTRY_DIR` setdefault 到临时目录生效）。

### 第2轮 push 证据

分支 `codex/ccc082-audit-storm-cross-datarir`，本轮提交为 HEAD（docs: lessons+卡回写），push 后核验 `git rev-list --left-right --count origin/codex/ccc082-audit-storm-cross-datarir...HEAD` 应为 `0 0`；工作区干净。

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。环节②交接指令(S116-01)直派核验加固卡，无关联方案页面需同步。
2. **教训沉淀**：[有]
   - 说明：[有]。机制级教训「跨进程互斥面若全锚定同一可配置目录，多实例各配各的目录即全线失效；至少一处须锚定用户级固定点」已沉淀至 docs/lessons.md Lesson 58（问题/根因/修复/如何应用四段式，2026-08-25 追加），代码侧同步落 `_audit_inflight_registry_dir` docstring 与本卡回写区。
3. **档案/README**：[否]
   - 说明：[否]。纯 engine 内部 marker 机制加固，配置经环境变量覆盖，不改任何对外文档口径。
4. **线路图**：[否]
   - 说明：[否]。单点防线收口，不构成新里程。
