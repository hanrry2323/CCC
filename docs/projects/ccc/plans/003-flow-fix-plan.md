# 方案 · CCC 流程问题清单与修复计划

> 项目：ccc · 编号：ccc-plan-003 · 状态：已完成 · 作者：老板 · 工具：Claude Code
> 创建：2026-08-09 · 更新：2026-08-10
> 关联卡：ccc008
> 关联方案：无
> 迁移自：docs/notes/2026-08-09-fix-plan.md

---

## 一、问题清单（按严重度排序）

### P0 · 门禁命令在 worktree 环境不可用（8 张卡全部因此打回）

**现象**：8 张开发完成的卡被门禁打回，失败原因全部是环境问题：
- `pytest: command not found`（5 张）
- `cd tests/server: No such file or directory`（2 张）
- `cargo: command not found`（1 张）

**根因**：worktree 是 `git worktree add` 创建的干净 checkout，不包含 venv、Rust 工具链、pytest 等开发环境。出卡时写的门禁命令假设了完整开发环境。

**影响**：所有非 CCC 平台自身的卡都无法通过门禁。门禁 100% 误杀。

### P0 · 编译型语言的 cargo test 在开发槽位运行（mx027）

**现象**：mx027 的 OpenCode 在开发阶段跑了 `cargo test`，触发全量依赖编译（9 个 rustc + 1 个 clang），CPU 占用 >4 小时，最终超时打回。

**根因**：卡步骤中写了 `cargo test -p medio-core`，执行体在实际业务仓（非 worktree）中运行了全量编译。

**影响**：占满 2017 CPU，阻塞其他排队卡。

### P0 · 确定性门禁失败浪费 3 次 retry

**现象**：每张卡打回前都重试了 3 次（retry_count=3），每次都是同样的门禁命令失败。`pytest: command not found` 重试 100 次也不会成功。

**根因**：引擎对所有门禁失败一视同仁，不区分「环境缺失」（确定性失败）和「代码问题」（可重试）。

**影响**：24 次无效 retry（8 张 × 3 次），浪费执行槽位。

### P1 · 机审 prompt 无结构、无项目 SOP（ccc016 审计）

**现象**：机审 prompt 是一段无结构长文，把角色、流程、输出、禁止揉在一起。每次审计都是全量探索（读卡+diff+核验+修复+报告），10+ 轮 LLM 推理。

**根因**：机审没有标准化 SOP，没有注入项目专属审查清单。

**影响**：机审耗时长、token 消耗大。

### P2 · 两张卡只有文档改动无实际代码（qb002、xy029）

**现象**：qb002 只改了 `.ccc/intent-proposals/` 下的 JSON 文件，xy029 只有文档改动。未产生实际业务价值。

**根因**：卡目标过于模糊，或执行体在 worktree 中无法找到正确的业务代码路径。

**影响**：浪费执行槽位。

---

## 二、修复计划

### 卡片 ccc019：门禁命令适配 worktree 环境（P0）

**目标**：修改所有打回卡的门禁命令，使其在 worktree 环境中可执行。

**方案**：
1. 门禁只做「编译检查」和「范围检查」，不做重体力测试
   - Python 项目：`python3 -c "compile(open('file.py').read(), 'file.py', 'exec')"`（无需 pytest）
   - Rust 项目：移除门禁（`cargo` 在 worktree 不可用）
   - 通用：`git diff --name-only origin/main` 范围检查（已有）
2. 门禁命令改为空或轻量级，测试交给独立环节
3. 修改 8 张打回卡的门禁段，重新分派

**改哪些**：
- `docs/dispatch/ccc/ccc017-prompt.md`：门禁 `测试: pytest` → 移除
- `docs/dispatch/hp/hp019-task.md`：门禁 `cd tests/server && pytest` → 移除
- `docs/dispatch/hp/hp020-chunk.md`：同上
- `docs/dispatch/qb/qb002-task.md`：门禁 `pytest` → 移除
- `docs/dispatch/qb/qb003-lint.md`：门禁 `pre-commit` → 移除
- `docs/dispatch/xy/xy028-pytest-3.md`：门禁 `pytest` → 移除
- `docs/dispatch/xy/xy029-task.md`：门禁 `pytest` → 移除
- `docs/dispatch/mx/mx027-core-60.md`：门禁 `cargo check / cargo test` → 移除

### 卡片 ccc020：引擎门禁失败分类分流（P0）

**目标**：引擎区分「环境缺失」和「代码问题」，环境缺失直接打回不重试。

**方案**：
1. 在 `server/engine/main.py` 的 `_dispatch_and_collect` 中，门禁失败后检查失败特征
2. 匹配 `command not found`、`No such file or directory`、`No module named` → 判定为环境缺失 → 直接打回（retry=0）
3. 其他失败 → 走现有 retry 逻辑

**改动**：`server/engine/main.py` ~20 行

### 卡片 ccc021：机审 prompt 结构化 + 注入项目审查清单（P1）

**目标**：机审 prompt 拆分为角色定义 + 项目审查清单 + 处理原则，注入阶段 3 建好的项目知识。

**方案**：
1. 修改 `executors.example.json` 的验收席 prompt：
   - 拆分：角色定义（固定）、审查清单（从卡内 `## 机审提示` 注入）、处理原则（固定）
   - 利用阶段 2 已完成的引擎注入机制
2. 机审 prompt 从「全量探索」改为「聚焦审查」
   - 去掉「加载 code-review 技能」→ 卡内 `## 机审提示` 已包含项目专属审查清单
   - 去掉「独立取证」→ 门禁已做编译检查，机审只做原则性审查

**改动**：`server/config/executors.example.json` ~10 行

### 卡片 ccc022：引擎卡死检测与超时优化（P1）

**目标**：长时间运行的任务（>30 分钟）自动 kill，释放槽位。

**方案**：
1. `_dispatch_and_collect` 的 timeout 从 300s 改为可配置的 per-card timeout
2. 卡内 `## 门禁` 段新增 `超时: <秒>` 字段，支持每卡独立超时
3. 默认超时 600s（10 分钟），超时 → kill + 打回

**改动**：`server/engine/main.py` ~15 行

---

## 三、执行顺序

```
ccc019（修门禁命令）→ 8 张卡重新分派
  ↓
ccc020（门禁分类分流）→ 阻止环境缺失的无效 retry
  ↓
ccc021（机审 prompt 优化）→ 减少机审耗时
  ↓
ccc022（卡死检测）→ 防止编译型任务占槽
```

## 四、预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 门禁通过率 | 11%（1/9） | >80%（仅 CCC 平台卡需门禁） |
| 无效 retry 次数 | 24 次 | 0（环境缺失直接判定） |
| 机审平均耗时 | 10+ 轮 LLM 推理 | 3-5 轮（聚焦审查） |
| 卡死槽位占用 | >4h | 10 分钟自动释放 |