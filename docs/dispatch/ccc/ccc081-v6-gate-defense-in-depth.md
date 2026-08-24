# 任务卡 ccc081 · V6 门禁纵深防御——结论行字形/混合提交/注释勘误（DSH 执行）

> 关联：环节②交接指令(S116-01)卡0 · 执行体：DSH · 验收：DSH · 状态：已回写 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

堵 V6 漂移检查两项 fail-open 与一处注释错误：① approve-merge.sh 结论行 grep 只认单字形「机审：通过」，粗体/变体信封会静默跳过漂移检查；② 信封+代码混合提交可把漂移基准推到自身；③ validate-plans.sh L281 注释字节碰撞描述不准确。

## 红线

- 白名单：scripts/approve-merge.sh、scripts/validate-plans.sh。
- 禁改机审真值判定语义（machine_audit_passed_text 的通过/不通过识别不动）；只加严漂移检查触发条件与信封纯度校验。
- 不动 OPENCODE_GO_API_KEY / engine.lock / 生产 ledger。

## 范围

- approve-merge.sh：pinned 非空而 last_env_commit 为空时显式 ERROR 阻断（或回退钉基线并在输出标注回退）。
- 信封提交单文件校验：合入前核对被钉信封 commit 的改动文件集是否仅含卡文件本身，含代码改动即拒绝并提示拆分。
- validate-plans.sh L281 注释勘误：仅「分」字含 0x88 续字节，删除不准确表述。

## 步骤

1. 读 approve-merge.sh 漂移检查段，定位 pinned/last_env_commit 判定与 grep 字形。
2. 实现两处加严 + 一处注释修正。
3. 自测：合成变体信封（粗体「**机审：通过**」）走漂移检查路径断言不再静默跳过；构造混合提交样例断言被拒；bash -n 全过。

## 验收标准

- [ ] 变体字形信封不再静默跳过漂移检查（测试或探针输出取证）
- [ ] 含代码改动的信封提交被显式拒绝
- [ ] scripts/validate-plans.sh 注释与实际字节事实一致
- [ ] bash -n 通过；既有 approve-merge 相关测试不回归

## 回写要求

- 回写区列改动点、自测命令与输出摘要、每处 diff 要旨。
- 维护区四问如实填写。

## 人工批注

（留空）

## 回写区

**实现说明**（2026-08-24 · DSH 执行体）：V6 漂移检查段函数化为 `v6_drift_gate`（approve-merge.sh:385-479，调用点 :531），在原「钉完整性+漂移 diff」基础上加两道纵深；validate-plans.sh 注释按实测字节事实勘误。机审真值判定语义（server/board/models.py `machine_audit_passed_text`）零改动。

### 改动点与 diff 要旨

1. **①变体字形信封不再漏认**（approve-merge.sh 原 L437-442 grep 段重写）：信封定位从单字形 grep `'^\+[[:space:]]*机审：通过'` 改为归一化管线——剥 diff `+` 前缀 → 剥行首装饰（空格/#/>/-/*/加粗）→ 删行内空白与 `*#>`（对齐真值判定的 strip('**') 与 `\s*` 口径）→ 行首锚定匹配 `^(机审|结论)[：:]通过`。粗体「**机审：通过**」、engine 落盘「> 结论：通过」「机审: 通过」等变体均建立漂移基线；收集全部信封提交（新→旧），[0] 为最后审计信封（多轮审计语义不变）。
2. **①配套 fail-closed 安全网**：分支 tip 已有通过文本却定位不到任何信封提交（字形未识别/历史异常）→ 显式 ERROR 阻断，不再静默跳过整段漂移检查（approve-merge.sh:414-419）。范围①的「pinned 非空而 last_env_commit 为空 → ERROR」实现于 :446-451——因安全网先行触发，此层为防御性冗余（has_branch=true 时不可达），保留作双保险。
3. **②信封纯度校验**（approve-merge.sh:421-434）：逐个信封提交核对改动文件集，仅允许卡文件本身；夹带非卡文件 → 显式拒绝并提示「把代码改动拆出为独立提交并重新机审」。堵住混合提交把基线推到自身、自身代码逃过漂移 diff 的洞（成因面：engine `_commit_and_push_worktree_card` 用裸 `git commit` 会卷入索引中已暂存文件）。
4. **③注释勘误**（validate-plans.sh L281-283）：原「其 0x88 与 分/派/关 续字节碰撞」不准确。实测字节：「（」=EF BC 88 尾字节 0x88；分=E5 88 86 含 0x88 续字节；派=E6 B4 BE、关=E5 85 B3 均不含 0x88。改为「『（』尾字节 0x88 仅与『分』(E5 88 86) 的续字节碰撞即会把状态截断，派/关不含 0x88」。仅动注释，代码逻辑零改动。

### 自测命令与输出摘要

- 七场景 harness（/tmp/v6gate-test.sh，从真实文件 sed 提取 `v6_drift_gate` 于合成 git 仓执行）：T1 粗体信封+信封后代码改动→拒（旧逻辑静默跳过，A/B 对照：旧 grep 对 `+**机审：通过**` 不命中）；T2 纯净粗体信封→放行；T3 同 commit 加结论行+改代码→「信封纯度校验失败」拒；T4 行中变体（clw011 式）+被审钉→基线缺失显式阻断；T5 规范信封+被审钉+卡回写→放行；T6/T7 engine 引用式信封识别、其后夹带代码→拒。结果 PASS=7 FAIL=0（bash 3.2.57 兼容）。
- 字形 A/B 探针：旧 grep 对粗体信封行不命中（复现问题①）；新管线对 `**机审：通过**`/`> 结论：通过`/`机审: 通过`/`**机审**: **通过**` 全命中。
- `bash -n scripts/approve-merge.sh && bash -n scripts/validate-plans.sh` → 双过；`bash scripts/approve-merge.sh` 无参 → usage 退出码 2（端到端解析正常）。
- 回归：`bash scripts/tests/test-card-resolve.sh` → V7 全过；`bash scripts/validate-plans.sh`（仓内全量）→ rc=0 全部通过、0 FAIL（1m13s）。
- 字节事实实证：python3 打印 （/分/派/关 UTF-8 序列，仅「分」含 0x88。

### 验收标准对照

- [x] 变体字形信封不再静默跳过漂移检查 —— T1/T7 拒绝输出取证
- [x] 含代码改动的信封提交被显式拒绝 —— T3 信封纯度拒绝输出取证
- [x] validate-plans.sh 注释与实际字节事实一致 —— 实证 + 勘误 diff
- [x] bash -n 通过；既有测试不回归 —— 双脚本 bash -n 过、test-card-resolve 过、validate-plans 全量 rc=0

## 维护区

1. **方案同步**：[否]
   - 说明：[否]。本卡为环节②交接指令(S116-01)直派加固卡，卡头无 prefix-plan-NNN 关联方案。
2. **教训沉淀**：[无]
   - 说明：[无]。教训已随本卡回写区记录——门禁以文本形态定位证据时，识别口径须与其真值函数的字形口径对齐并配 fail-closed 兜底（本卡实现与七场景自测均已固化该模式），无需另沉淀 docs/notes。
3. **档案/README**：[否]
   - 说明：[否]。纯 scripts 内部门禁加严与注释勘误，未改对外命令用法、配置项或文档口径。
4. **线路图**：[否]
   - 说明：[否]。既有 V6 门禁的纵深防御收口，不构成新里程。
