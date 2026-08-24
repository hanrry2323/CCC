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

## 机审区

**DSH 机审席 · 2026-08-25 · severity：中**

### 范围核对

提交 ca94bae9a 仅触 scripts/approve-merge.sh、scripts/validate-plans.sh 及本卡回写，均在白名单内，无越界。server/board/models.py 真值函数零改动（`git diff ca94bae9a^ ca94bae9a -- server/board/models.py` 为空）。validate-plans.sh 仅注释改动（-2/+3 行），注释勘误的字节事实独立实证吻合：（ EF BC 88 尾字节 0x88；分 E5 88 86 含 0x88 续字节；派 E6 B4 BE、关 E5 85 B3 不含。

### 认可面（逐项复核）

- ① 归一化管线方向正确：A/B 探针亲手复现旧 grep 对粗体信封行不命中、新管线（UTF-8 locale 下）命中变体。
- ② 信封纯度校验逻辑成立：逐信封提交核对文件集，混合提交拒绝；批建卡等历史提交因不含结论行不入 env_commits、不受累。
- ③ fail-closed 安全网真实生效：C locale 下 T1-T6 场景全部显式阻断而非静默跳过（见下）。
- ④ 多轮审计语义不变：env_commits[0] 取最新信封，与旧 break-first 等价；调用点 :533 传参正确；函数内无残留散装逻辑；bash -n 双过（本席亲跑）。
- ⑤ ledger 兜底链完整：machine_audit_pass 门禁（approve-merge.sh:641-655）位于 gate 之后，卡文自写不算真值。

### P1 发现（本卡引入 · 已复现）

**F1 信封定位的 grep 多字节括号 `[：:]`（approve-merge.sh:406）locale 敏感**：LC_ALL=C 下 BSD grep 的多字节括号表达式不匹配全角冒号，规范字形「机审：通过」「> 结论：通过」（全部在用卡的结论行主字形）漏认 → env_commits 空 → fail-closed 网 → 该环境下合入被全量阻断。

证据（全部可复现）：
- 本沙箱默认 LC_ALL=C：`bash /tmp/v6gate-test.sh` → **PASS=2 FAIL=5**，其中 T5（规范信封+被审钉+卡回写放行的回归场景）被误拦；
- `LC_ALL=en_US.UTF-8 bash /tmp/v6gate-test.sh` → PASS=7 FAIL=0——回写声明的七场景全过仅在 UTF-8 locale 成立；
- 仓内先例：validate-plans.sh:25-34 因同类字节/locale 问题已硬钉 LC_ALL=en_US.UTF-8（ccc068，8.2 漏判复活事故），本卡未沿用该既定模式，脚本亦未钉 locale；
- 回归性质：旧代码字面量匹配 `^\+[[:space:]]*机审：通过` 在 C locale 下反而工作——本卡在其宣称加严的「识别口径」维度引入了环境敏感回归。

影响评估：失败方向为 fail-closed（不产生错误放行，红线安全）；但触发即整条合入链路不可用，且 merge-executor 自动化路径（server/config/merge-executor-instruction.md）的运行环境 locale 不保证 UTF-8。修复建议（供重试轮执行体参考，本席不代改）：括号类改字节字面量交替 `(：|:)`（两种 locale 下语义一致），或按 ccc068 先例在脚本头部钉 LC_ALL。

### 轻微项（不单独计分）

- 回写区引用行号 :385-479/:531 与实际 389-481/:533 有 ±2 偏差；函数名唯一，不影响定位复现。
- 自测摘要缺 locale 前提：「PASS=7 FAIL=0」「新管线全命中」均为 UTF-8 locale 下结果，证据完整性存瑕疵（非造假，UTF-8 下可复现）。
- 理论残余面（非本卡引入，既有设计边界）：卡文伪造结论行可将漂移基线前推越过其前的纯代码提交；ledger 按 id 记录不钉 commit。建议后续加固卡考虑 ledger 钉 commit。
- rename 边缘：`git show --name-only` 对重命名显示 `{old => new}` 格式可能误拒（fail-closed 方向，罕见）。

### severity 判定

影响面 2（合入必经门禁；缺陷触发条件环境相关、方向 fail-closed）＋ 改动深度 2（核心门禁段函数化重构，净新增判定逻辑约 30 行）＋ 红线邻近 2（机审真值邻域，真值语义零改动有实证）＝ 6 → 中；无任一维度 3 分。

### 维护区四问核对

四问均单选已填、说明非占位且抽查属实：方案同步[否]（卡头关联字段确无 prefix-plan-NNN）；教训沉淀[无]；档案/README[否]（对外用法未变属实）；线路图[否]。引用工件抽查：/tmp/v6gate-test.sh 存在（2026-08-25 00:12）、scripts/tests/test-card-resolve.sh 存在、models.py 零改动属实、字节事实属实；唯自测输出摘要缺 locale 前提标注（见轻微项）。

机审：不通过（P1-F1：v6_drift_gate 信封定位 [：:] 多字节括号在 LC_ALL=C 下漏认规范字形「机审：通过」，fail-closed 网致该环境合入全量阻断，T5 回归场景实测 FAIL；自测 PASS=7 证据仅在 UTF-8 locale 成立且仓内已有 ccc068 钉 locale 先例未沿用。修复后重新机审）
