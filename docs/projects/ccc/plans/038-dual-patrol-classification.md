# 方案 · 双巡查体系分类定稿（LoopObserver 固定程序 / DSH 大模型）

> 项目：ccc · 编号：ccc-plan-038 · 状态：已确认 · 作者：老板 + Claude Code W1 · 工具：Claude Code
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：无
> 关联方案：无
> 里程碑：无（方向性方案；是 DSH 全局巡回 agent 体系的分工基准）
> 决策源：qx-map `sync/notes/dsh-global-patrol-2026-08-17.md` + `sync/notes/dsh-preset-discipline-2026-08-17.md` + 老板 2026-08-17 定调

## 目标

把 CCC 的两套巡查体系——**LoopObserver（固定程序巡查）** 与 **DSH（大模型/IDE 工具巡查）**——的**分类、定位、职能职责、能力边界**定死，形成覆盖矩阵，确保全集群无遗漏。作为后续开发、调度、人审合并的分工依据。

## 背景

CCC 现在有两套并行的巡查能力，但定位边界不清：

1. **LoopObserver**（`server/engine/observer.py`，`scheduler.py` TaskRegistry 注册）——固定程序巡查，已在跑（2026-08-17 产出 1 红旗 + 1 黄旗），确定性规则检查治理一致性。
2. **DSH**（DeepSeek Harness headless，`~/.dsh/run_patrol.sh`）——大模型巡查，已跑通全局跑通核实首单（933 测试实测），纪律已注入 preset（`ccc-verifier`）+ headless cordis.patch.yml。

老板定调（2026-08-17）：**分类和定位一定要清楚，一个固定巡查、一个大模型巡查，职能职责、能做的事情、做好分类，这样基本没有遗漏。**

## 方案内容

### 1. 双巡查分类矩阵（核心定稿）

| 维度 | **LoopObserver（固定程序）** | **DSH（大模型巡查）** |
|---|---|---|
| **本质** | 确定性规则引擎 | 大模型语义理解 + 真实执行 |
| **查什么** | 治理一致性（状态/关系/流程） | 真实应用跑通 / 找 bug / 提升点 |
| **问题类型** | 状态漂移、方案-卡断裂、维护区缺失、技术债、孤儿卡、验收未勾选 | 代码 bug、全局跑通失败、性能/隐患、提升建议 |
| **判断方式** | 规则匹配（确定性、无歧义） | 语义推理（需要理解上下文） |
| **触发** | 定时（24h）+ 新 merge 自动 | 手动/定时，按需 |
| **产出** | 8 列风险表 + 观测指标 | 6 列发现契约 + 证据链 |
| **可靠性** | 100% 确定（规则不会错） | 需人工复核（断言偶有失准，已实证） |
| **成本** | 免费（纯代码） | 免费（code 模型 6102） |
| **落盘** | `DATA_DIR/observer/*.md` | `DATA_DIR/dsh/*.md` → 巡检页 |

### 2. 能力边界（谁做什么）

**LoopObserver 独有**（DSH 不该做，规则确定性 DSH 会臆测）：
- 卡/方案/里程碑状态机一致性校验（drift / broken_link / consistency）
- Doc-Gate 维护区四问覆盖率、教训回流率统计
- 技术债聚合（打回卡、批注未落实、审核引用缺失、死文件、孤儿卡、作废前置）
- 观测指标（ccc-kb 调用量、验收通过率、执行体接入状态）

**DSH 独有**（Loop 永远做不到，需要语义/真实执行）：
- 跑真实应用端到端验证（pytest 实跑、服务探活、链路测试、compileall）
- 读代码找逻辑 bug（需要理解语义）
- 提升点建议（架构优化、重构方向）
- 生产数据巡检（xy 产线定时触发、素材投喂）
- 全局跑通核实（合入 main 后真实应用能不能跑）

**重叠区**（两者都碰但目的不同）：
- 一致性：Loop 查"状态声明"一致性（静态规则）；DSH 可查"声明 vs 实际"一致性（如方案状态 vs 代码实现）

### 3. 无遗漏原则

> **Loop 兜底「结构性遗漏」**（规则必查，绝不漏）；**DSH 兜底「语义性遗漏」**（需要理解/真实跑才查）。

两者发现都进**同一个巡检页**（`#/dsh`），前端按来源可区分（Loop 报告 vs DSH 报告），人审合并决策。

### 4. 协作流（螺旋上升）

```
LoopObserver（定时规则巡查）
   + DSH（大模型/真实执行巡查）
        ↓ 两者都落 DATA_DIR/{observer,dsh}/*.md → 巡检页（#/dsh）按项目分组展示
        ↓
   人审（老板 + Claude 定期沟通）
        ↓ 合并巡检结果 + 草案池 + 未开发方案
        ↓ 制定新计划/里程碑 → 拆任务卡
        ↓
   CCC 出卡 → 开发 → 机审 → 合入 main
        ↓ 合入后触发 DSH 再巡查（全局跑通核实）
        ↓ 回到顶部（螺旋上升）
```

### 5. 调度归属（现状 + 目标）

| 巡查 | 触发 | 落盘 | 备注 |
|---|---|---|---|
| LoopObserver | scheduler TaskRegistry（已注册 `loop-observer`） | `DATA_DIR/observer/` | 已在跑，无需干预 |
| DSH 全局跑通核实 | `~/.dsh/run_patrol.sh`（cron/launchd 待接） | `DATA_DIR/dsh/` → 巡检页 | 通道已实测打通 |
| DSH xy 定时生产 | `run_xy_producer.sh`（Phase 2，待做） | 产线 output | 后续迭代 |
| DSH 验收盯防 | `run_acceptance_watch.sh`（Phase 3，待做） | 巡检页 | 后续迭代 |

## 验收标准

- [x] 双巡查分类矩阵已定稿（Loop=规则，DSH=大模型）
- [x] 能力边界已明确（各自独有 + 重叠区）
- [x] 无遗漏原则已写死（Loop 兜结构性，DSH 兜语义性）
- [ ] DSH 报告自动进巡检页（run_patrol.sh 加 POST /loop/dsh-report）
- [ ] 巡检页按项目分组展示 DSH 结果（补 project 列 + 前端分组）
- [ ] 分类文档已落盘 ccc-plan-038

## 功能卡

> 拆卡原则（ccc-plan-027）：一个功能一张卡。本方案拆 2 张卡（巡检通道 + 按项目分组），均为 ccc 平台侧改动，M1 主窗口直接开发 + 异席机审。

### 卡1 · DSH 报告接入巡检页（通道打通）

目标：DSH 全局巡回 worker 的巡查报告自动进入巡检页（#/dsh），落 DATA_DIR/dsh/。

实现：`~/.dsh/run_patrol.sh` 末尾追加 `curl -s -X POST http://127.0.0.1:7788/loop/dsh-report -d @<报告文件>`（body 传 markdown 或 findings），CCC 服务端已实现该端点（免登录），零服务端改动。报告按 6 列契约组织（| 面 | 位置 | 现象 | 证据 | 建议处置 | 置信度 |）。

验收：跑 run_patrol.sh 后，巡检页出现最新报告；报告 findings 解析正确（表头触发容错）。

颗粒度：脚本加一行 curl + prompt 模板对齐 6 列契约。

依赖：无。

架构位置：DSH worker（2017）→ POST /loop/dsh-report → server.py:3461 → DATA_DIR/dsh/*.md → 巡检页 #/dsh。

### 卡2 · 巡检页按项目分组展示

目标：巡检页的 DSH 发现按项目分组（ccc/qx-map/xy/quant-hive 等），替代当前按置信度平面排。

实现：① 后端 `server/web/server.py:_parse_dsh_md`（1713）扩展 DSH 契约为 7 列加「项目」（`len(cells)>=7` 时取，置信度移列），同步更新测试；② 前端 `dshPage.js` renderFindings 照抄 opsPage.js:337-339 的 byProj 聚合 + 349-360 子组渲染；③ DSH worker 报告模板加「项目」列（patrol_prompt.txt）。

验收：巡检页 DSH 报告按项目分组；老报告（无项目列）兼容（容错解析不报错）；pytest 通过。

颗粒度：后端解析 + 前端分组 + prompt 模板 3 处改动。

依赖：卡1（先有 DSH 报告进页面，再分组）。

架构位置：server.py _parse_dsh_md → dshPage.js 渲染层。
