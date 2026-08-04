# 任务卡 T54 · T-A1 命名与目录迁移（Claude Code 执行）

> 关联：阶段 3（T-A1 命名规则落地，Codex 决策 2026-08-04）· 执行体：Claude Code · 验收：Codex · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-04
> 工作目录：`/Users/fan/program/ccc-dev-ws`；分支：`codex/t54-auto-naming`（先 `git fetch origin main && git checkout -b codex/t54-auto-naming origin/main`）
> **分步提交纪律（硬）**：每完成一个逻辑块立即 commit+push，禁止攒批；执行超时 7200s。

## 目标

落地任务卡命名规则（`docs/dispatch/<前缀>/<前缀><三位序号>-<slug>.md`）与目录迁移能力：loader/Engine 支持子目录扫描，旧卡不动（T-mapping 映射），新卡按新规则生成。

## 具体项

### A. 命名规则与映射

1. `docs/dispatch/T-mapping.md`：历史 T1–T54 卡映射表（`T<全局> → <前缀><序号>`，旧卡不批量重命名，保持 git 历史）。
2. 前缀表：qb / qh（QuantHive）/ ccc / mx（medio-0）/ xy（xianyu）/ hp（知识库）/ tst（临时测试，禁止合入）。

### B. 子目录扫描（核心路径，必须测试任务先行验证）

3. `server/board/loader.py` + `server/engine/store.py`（FileBoardStore）：扫描 `docs/dispatch/` 含**一层子目录**（`<prefix>/` 下 `*.md`），平铺旧卡兼容；索引/导出同步。
4. 命名校验（validate.py）：新卡必须 `<prefix><NNN>-<slug>.md` 且位于对应子目录；编号跨项目唯一；旧卡（根目录 T*.md）仅警告不拦截。
5. `scripts/new-card.sh`：升级为按新命名生成（项目子目录 + 前缀序号自增 + slug 校验）。

### C. 测试任务先行（硬）

6. 迁移后必须验证：新旧卡混合目录下 loader/Engine 扫描正确、看板派生正确、Engine 派发正常——用临时目录 + T9x-test 占位卡验证，跑通后才算完成。

## 红线

1. 只在 ccc-dev-ws 工作；禁止改 2017 运行副本。
2. **旧卡（根目录 T*.md）零改动**（只新增 T-mapping.md）；新卡才开始用子目录规则。
3. loader/Engine 目录扫描改动不得破坏现有平铺解析（向后兼容）。
4. 回写前 push 分支成功并附证据。

## 验收标准

1. T-mapping.md 覆盖全部历史卡（T1–T54）。
2. 新旧混合目录实测：loader 扫描正确（子目录 + 平铺）、Engine 派发正常（测试任务先行占位卡端到端）、看板派生无错乱。
3. validate 新命名规则生效（新卡按子目录+前缀命名通过；错误命名被拦）；旧卡零拦截。
4. new-card.sh 生成新规则卡（子目录 + validate 过）。
5. pytest 全绿、ruff/py_compile clean、push 证据。

## 回写要求

卡头状态更新为「已回写」；回写区填：A/B/C 实现说明、测试任务先行验证记录（新旧混合扫描/派发/看板）、命名校验演示、pytest/build、push 证据。

## 回写区

**执行体**：Claude Code（2017）· 日期：
