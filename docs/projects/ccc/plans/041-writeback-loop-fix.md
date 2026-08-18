# 方案 · CCC 回写闭环综合修复（断链 #1-5 + 子项目映射）

> 项目：ccc · 编号：ccc-plan-041 · 状态：已确定 · 作者：Claude Code（W1·S140-01@M1）· 工具：Claude Code
> 创建：2026-08-19 · 更新：2026-08-19
> 关联卡：无（平台自研，不走 engine 出卡）
> 关联方案：ccc-plan-040（标准化审计全景，本方案细化其断点①）、ccc-plan-017（Delivery Gate）、033（人审节点）
> 依据：DSH 报告 `__archive__/research/CCC回写机制断链深度排查报告-2026-08-19.md`（2017 副本，839 行）+ 本会话六项目审计
> 里程碑：标准化体系加固
> 子项目：040.1 状态回写闭环修复
> 环境准备：M1 主窗口 + 异席机审（Codex）；平台自研红线适用

## 目标

修复 CCC「任务卡开发→合入→方案进度/里程碑状态回写」的闭环断裂。当前卡合入后，方案进度行和 roadmap 里程碑/子项目状态不更新（实测 mx-plan-005 关联 mx052 已关闭，方案却写「0/1 (0%)」）。本方案综合 DSH 深度排查的五层断链 + Claude Code 审计发现的子项目映射缺陷，给出有优先级的修复执行计划。

## 背景

老板指令（2026-08-19）：将「闭环回写」任务从 DSH 窗口转交 Claude Code，综合 DSH 报告 + 本会话审计发现统一处理。

**两路调查的合并**：
- **DSH**（独立只读审查，2017，839行报告）：五层断链（approve-merge 时序/observer 停/Engine 无 sync/历史债/35卡绕过），含代码行号+实测证据+修法代码示例。本方案核验其两处 P0 行号准确（approve-merge.sh:527/535、main.py:3099、0处 transition(CLOSED)）。
- **Claude Code**（本会话六项目审计）：四系统性断点，其中断点①=状态回写断裂，独立发现 roadmap 子项目映射缺陷（roadmap.py:812，DSH 未覆盖）。

## 综合断链全景（DSH 五层 + Claude Code 映射缺陷）

| 断链 | 来源 | 位置 | 现象 | 优先级 |
|------|------|------|------|--------|
| #1 approve-merge 时序 | DSH | approve-merge.sh:527→535 | close_card 改 .md 不刷 cards.index.jsonl → sync 读旧值 → closed=0 | **P0** |
| #1b 子项目映射缺陷 | Claude Code | roadmap.py:812-817 | `_sync_subproject_statuses` 把方案「待验收」归子项目「计划中」→ 视觉断裂 | **P0** |
| #3 Engine 无 sync | DSH | main.py:3099 | transition(DONE) 后不调任何 sync；全文 0 处 transition(CLOSED) | P1（见判断） |
| #2 observer 停 | DSH | observer + launchd | observer 6 天没跑（last-run 停 8-13 23:57），延迟补偿失效；com.ccc.scheduler 未挂载 | P1 |
| #4 历史债 | DSH | mx-plan-001 等 | 29 张卡在 ccc062(sync_plan_cards) 引入前关闭，方案无进度行 | P2 |
| #5 35卡绕过 | DSH | mx 45卡 | 35 张没走 approve-merge.sh（无批准行/无 ledger），绕过 sync | P2 |

**断链#1 实测证据**（DSH + 本人核验）：
- `load_index_file`（loader.py:248-268）直接读 cards.index.jsonl 缓存，无 mtime 检测、不实时扫 .md
- mx-plan-005 关联 mx052：cards.index.jsonl 已「已关闭」，实算 1/1=100%，方案文件却写「进度：0/1 (0%)」
- mx-plan-004 关联 mx045/046/047：实算 3/3=100%，方案写「2/3 (66%)」
- 对照组 mx-plan-003（进度正确 6/6）：也是合入后手动补跑 `sync_plan_progress` 修正的，非自动回写——证明断链#1 每次合入都发生

## 修复执行计划（按优先级）

### P0-1：approve-merge.sh 时序修复（断链 #1 · 主路径）

**根因**：close_card（527 行）改卡 .md 为「已关闭」但不刷新 cards.index.jsonl；sync_plan_cards（535 行）→ sync_plan_progress → load_index_file 读旧 index（「已回写」）→ closed=0 → 进度不更新。

**修法**（DSH 步骤1，已核验可行）：在 527 close_card 之后、535 sync_plan_cards 之前插入索引刷新：
```bash
close_card "$path"
# ★ 新增：刷新 cards.index.jsonl（close_card 改了 .md 但索引未同步）
"$PYTHON_BIN" -c "import sys; sys.path.insert(0,'.')
from server.board.loader import load_dispatch_cards
load_dispatch_cards('docs/dispatch')" 2>/dev/null || echo "[WARN] 索引刷新失败（不阻断合入）" >&2
# （原 529-533 audit_ledger / 535 sync_plan_cards 不变）
```
**原理**：load_dispatch_cards 重新扫描卡 .md 刷新 index → sync 读到最新「已关闭」→ closed 计数正确。

**验证**：合入一张卡后方案进度行立即正确（1/1 而非 0/1）；cards.index.jsonl mtime 在 close_card 后、sync_plan_cards 前变化。用 mx-plan-005/mx052 实测复现。

### P0-2：roadmap 子项目「待验收」态（断链 #1b · Claude Code 独有发现）

**根因**：`_sync_subproject_statuses`（roadmap.py:812-817）只认方案「已完成」→子项目「已完成」，把「待验收」也归「计划中」。卡全关、方案已待验收，roadmap 永远显示「计划中」——视觉断裂。

**修法**：三态扩四态。方案「待验收」→子项目「待验收」（非「计划中」）：
```python
if plan_status == "已完成":
    target = "已完成"
elif plan_status == "待验收":        # ★ 新增
    target = "待验收"                 # 区分"已开发待拍板"与"未开发计划中"
elif plan_status in ("作废", "已覆盖"):
    target = "未启动"
else:
    target = "计划中"
```
同步 `compute_milestone_progress` / 前端 `_enrich_subproject_statuses`（roadmap.py:850+ dev_status）认「待验收」。

**验证**：HP 11 个待验收方案对应子项目应从「计划中」变「待验收」；前端 dev_status 不再把待验收归「未开发」。

### P1-1：Engine DONE 后回写（断链 #3 · 冗余双保险 · 含判断）

**DSH 判断**：P0，DONE 后插 `_sync_plan_after_state_change` 调 sync_plan_progress + sync_milestone_progress。

**Claude Code 独立判断（待异席复核）**：**此条应降为 P1 冗余双保险，非进度更新主路径**。理由：
- plans.py:921 `sync_plan_progress` 只计「已关闭」卡为 closed，**「已回写」不计入**。DONE（已回写）时调 sync，closed 数不变 → 进度行不变。
- CLOSED 流转唯一入口是 approve-merge.sh（grep 确认 main.py 0 处 transition(CLOSED)）。P0-1 修好 approve-merge 时序后，回写主路径已通。
- #3 的价值：Engine 闭环与方案层解耦的设计缺陷，作为 approve-merge 之外的双保险。但单独修 #3（不修 #1）不能解决进度不更新。

**修法**：按 DSH 步骤2 在 main.py:3099 DONE 后插 `_sync_plan_after_state_change`。**但需动手时验证**：DONE 时 sync 是否真能改变进度（疑无效，因已回写不计 closed）；若无效，#3 应改为「Engine 自动关卡路径」（如允许 DONE→CLOSED 自动推进，但违反人审关卡红线，需老板定）或仅作信号通知。

**结论**：#1 是主路径必修；#3 列 P1，实现时据有效性调整或仅作双保险，不阻塞 #1 的修复收益。

### P1-2：observer 恢复（断链 #2）

**根因**：observer 6 天没运行，auto-fix-plan-progress.py 延迟补偿失效；com.ccc.scheduler launchd 未挂载。

**修法**（DSH 步骤3）：恢复 `com.ccc.scheduler` launchd 服务（M1 + 2017 双机）。让 observer 定时跑，对 plan_progress 漂移做幂等机械修复（auto-fix-plan-progress.py 已存在，observer.py:659-728 `_auto_fix_deterministic` 已实现）。

**验证**：last-run.json 时间更新；observer 跑后漂移方案被自动修正。

### P2：历史债清理（断链 #4 + #5 · 一次性）

**断链#4**：mx-plan-001 等 29 张卡在 ccc062 前关闭，方案无进度行。
**断链#5**：35 张卡没走 approve-merge.sh（无批准行/无 ledger），绕过 sync。其中 mx001 的 commit message 格式与 approve-merge 一致，推测走了 approve-merge 但在 ccc062 前。

**修法**（DSH 步骤4）：手动跑 `auto-fix-plan-progress.py` 批量补回写——对每个方案重算 sync_plan_progress + sync_milestone_progress，补进度行。35 张绕过卡的 ledger 缺失单独评估（补记或标注）。

**验证**：mx-plan-001 补进度行 29/29；全 mx 方案进度行与实算一致（DSH 报告 §七 实测表逐一对账）。

## 执行顺序

```
P0-1 approve-merge 时序（#1 主路径）  ← 核心修复，修后回写主路径通
P0-2 子项目待验收态（#1b 映射）       ← 消除 roadmap 视觉断裂
   ↓
P1-1 Engine DONE 回写（#3，双保险，验证有效性后定） 
P1-2 observer 恢复（#2，延迟补偿）     ← 让未来漂移自动修
   ↓
P2 历史债清理（#4#5，auto-fix 批量补）  ← 一次性补齐存量
```

## 验收标准

- [ ] P0-1：合入一张卡后方案进度行立即正确（实测 mx052→mx-plan-005：0/1 变 1/1）
- [ ] P0-2：HP 11 个待验收方案对应子项目状态从「计划中」变「待验收」
- [ ] P1-1：Engine DONE 后 sync 调用存在；有效性（已回写是否计入）经实测确认并据实调整
- [ ] P1-2：observer last-run 刷新，com.ccc.scheduler 双机挂载
- [ ] P2：mx 全方案进度行与实算一致（DSH §七表逐一回账）
- [ ] 全程：pytest 全绿（server/tests/），异席机审（Codex）通过

## 红线（平台自研）

本方案改 `scripts/approve-merge.sh`、`server/engine/main.py`、`server/board/roadmap.py`、launchd 配置——全部平台自研。registry ccc `taskable:false` 断根。一律 **M1 主窗口直接开发 + 直接测试 + 异席机审（Codex）**，不写任务卡走 engine 派发。理由见 AGENTS.md/onboarding §8.5。

## 备注

- **本方案是 040 断点①的专项细化**：040 给四断点全景，本方案给回写闭环的可执行修复计划。
- **DSH 报告权威性**：行号/代码片段/实测证据经本人核验准确（两处 P0 行号、load_index_file 行为、0 处 transition(CLOSED)），修法可照行号动手。DSH 报告全文存 2017 `/Users/fan/qx-map/__archive__/research/CCC回写机制断链深度排查报告-2026-08-19.md`，含完整代码示例。
- **Claude Code 增量**：断链#1b（子项目映射）DSH 未覆盖，是本方案独有；断链#3 的 P0→P1 降级判断是本方案独立结论，待异席复核。
- 040 断点②（交付缺失）/③（机审绕过）/④（合入被绕过·CLA假关闭）不在本方案范围，各自独立处理（见 040 §五-§七、CLA假关闭事故另立）。
