# 任务卡 ccc081 · V6 门禁纵深防御——结论行字形/混合提交/注释勘误（DSH 执行）

> 关联：环节②交接指令(S116-01)卡0 · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

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

（执行体回写时填写）
