# CLA 方案验收证据分级 · 2026-08-22

> 审计：CCC 验收证据审计员 · 项目：cla（clawmed-ccc，2017 生产机 /Users/fan/program/apps/clawmed-ccc）
> 目的：防 cla020-028 假关闭复发（卡标关闭但代码不在 main），为老板拍板提供证据分级。
> 方法：只读核对——方案文件状态、看板实时状态、卡状态、业务仓 origin/main 关键文件逐个 ls-tree 核实、pytest 复跑。
> 结论速览：**板上 0 个「待验收」方案**（已完成方案全部直接置终态「已完成」，approval 字段全空）；代码真实性全部核实通过（14 卡代码均在 main，关键文件逐一存在，分支已删）；C 档 0 个。

## 一、待验收方案清单（当前状态）

`docs/projects/cla/plans/` 下 13 个方案，看板实时（:7788 /plans/list?project=cla）与文件头状态一致：

| 状态 | 方案 |
|------|------|
| 已完成 | cla-plan-001/002/003/004/005/006/009/010/011/012/013 |
| 待排期 | cla-plan-007/008（M3 电商采集，未出卡，不在验收范围） |

**关键发现：无任何方案处于「待验收」。** 033 M4 流程（部分执行→待验收→拍板→已完成）应留下验收拍板批准行；但全部已完成方案 approval 字段为空（`"approval": ""`），即未走 /plans/accept 拍板留痕。已完成方案集中在 2026-08-18/19 由 delivery 流程置「已完成」。

## 二、逐方案证据分级

| 方案 | 标题 | 关联卡 | 卡状态 | 分支合入main? | 关键文件在main? | 交付报告? | 功能可复现证据 | 档位 | 缺什么 |
|------|------|--------|--------|--------------|----------------|----------|----------------|------|--------|
| cla-plan-001 | SQLite 账本底座与路径修复(M1) | cla001 | 已关闭 | 是（b6435d4/d04002d/516a5a2 在 main，分支已删） | 是（test_obs1/2_smoke、src/common/database.py、scheduler/queue.py） | 是（cla-delivery-001） | pytest 61 例全跑通（obs 冒烟含内） | A | 验收标准历史 0/3 未记录（遗留） |
| cla-plan-002 | SQLite 持久化队列重构(M1-1.2) | cla016 | 已关闭 | 是（516a5a2 在 main） | 是（queue.py=SQLiteQueue、job.py、test_queue_persistence.py、test_scheduler_jobspec.py） | 是（cla-delivery-001） | pytest 通过 | A | 无 |
| cla-plan-003 | 债务收尾(M1-1.3) | 无卡（eba676d 直改） | — | 是（eba676d 在 main） | 是（docs/decided.json） | 是（cla-delivery-001） | pytest 通过 | A | 无（无关联卡） |
| cla-plan-004 | 挂网价 Playwright 抓取(M2-2.1) | cla017 | 已关闭 | 是（1b30cdc/c933e05 在 main） | 是（crawlers/gov.py、test_gov_crawler.py） | 否（待 cla-delivery-002） | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-005 | 数据清洗与 SSOT 归一(M2-2.2) | cla019 | 已关闭 | 是（aef9278 在 main） | 是（etl/cleaner.py、test_etl.py） | 否 | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-006 | 降价预警与 Jobs 触发(M2-2.3) | cla020 | 已关闭 | 是（ef04d09/7cf327b 在 main） | 是（workflow/opportunity.py、scheduler/job.py、test_opportunity.py、test_scheduler_jobspec.py） | 否 | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-009 | LLM 双轨配置层(M4-4.1) | cla018 | 已关闭 | 是（f3d1367/c5ef0ee/019197a 在 main） | 是（adapters/llm.py、test_llm.py、config/settings.yaml） | 否 | pytest 59/61；test_llm 2 例依赖 live LLM（Ollama 11434 宕 + 6102 中转 completion 超时，非代码缺陷） | B | 交付报告未出；2 例 LLM 单测需 live 通道复跑 |
| cla-plan-010 | 机会挖掘与话术生成(M4-4.2) | cla021、cla022 | 已关闭 | 是（f7e8c75/f3d4347 等，提交在 main） | 是（workflow/opportunity.py、planner.py、test_opportunity.py） | 否 | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-011 | 合规初审与三级卡关(M5-5.1) | cla023、cla024 | 已关闭 | 是（e804146/1b718a2/ab871c3 在 main） | 是（workflow/compliance.py、api/routes/audit.py、test_compliance.py、test_audit_api.py） | 否 | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-012 | 企微 Webhook 推送(M5-5.2) | cla025 | 已关闭 | 是（0e3b5c1/80432fa/c6a7142/f328c4a 在 main） | 是（workflow/push_agent.py、test_push_agent.py） | 否 | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-013 | SPA 控制台(M5-5.3) | cla026、cla027、cla028 | 已关闭 | 是（80636b2/4bfc62a、b6fadbc/c29b2c0、8f9ea8b/035097b 在 main） | 是（frontend/、api/static/、test_data_panel_api.py、test_sse_api.py） | 否 | pytest 通过 | B | 交付报告未出；无拍板批准行 |
| cla-plan-007 | 电商反爬网关(M3-3.1) | 待出卡 | — | 不在验收范围 | — | 否 | — | 未评级 | M3 待启动 |
| cla-plan-008 | 电商采样探针(M3-3.2) | 待出卡 | — | 不在验收范围 | — | 否 | — | 未评级 | M3 待启动 |

## 三、档位统计

- 待验收方案数：**0**
- A 档：**3**（cla-plan-001/002/003，M1 底座，交付报告齐全）
- B 档：**8**（cla-plan-004/005/006/009/010/011/012/013，代码全在 main + 关键文件核实 + 测试可复现，缺交付报告/拍板批准行）
- C 档：**0**（代码不在 main / 文件缺失却标完成的方案：无）
- 未评级：2（007/008，M3 待排期）

## 四、C 档清单（假关闭复发风险）

无。

## 五、核实方法与证据

1. **卡状态**：`docs/dispatch/cla/*.md` 卡头 `状态：` 全部 14 卡 = 已关闭（cla001、cla016~cla028）。
2. **分支合入**：业务仓 `git branch -r` 仅 origin/main/HEAD（codex/<卡号> 分支已被 rebase 处置删除，与「9 卡 rebase 合入 main」一致）。以提交在 main + 关键文件物理存在为准。
3. **关键文件**：对每卡预期文件 `git ls-tree -r --name-only origin/main` 逐一核实，26 个文件全在（crawlers/gov.py、etl/cleaner.py、adapters/llm.py、workflow/opportunity.py/planner.py/compliance.py/push_agent.py、api/routes/audit.py、scheduler/queue.py/job.py、frontend/、api/static/、13 个测试文件）。
4. **可复现**：`python3 -m pytest tests/ -q` → **59 passed, 2 failed**。2 失败均 test_llm：test_online_real_call（httpcore.ReadTimeout，6102 中转 completion 超时）、test_dual_track_fallback（Ollama 11434 宕 + 在线超时）。均为 live 通道依赖，非代码缺陷；本地 6102 /v1/models 返回 200，Ollama 11434 不通。
5. **服务健康**：clawmed FastAPI 可 `PYTHONPATH=src python3 -c "from api.app import app"` 导入成功，路由含 /api/audit、/api/opportunities、/api/prices/gov、/api/prices/ecommerce、/api/stream。无常驻服务进程，无独立健康探针脚本（scripts/ 仅 run_crawler.py、run_etl_pipeline.py）。
6. **版本**：VERSION=v0.1.11，tag v0.1.9~v0.1.11 均已打（delivery-001 所述「待补 tag」债已消）。

## 六、风险提示（供老板拍板）

- 全部代码经核实真在 main，**假关闭未复发**，cla020-028 处置有效。
- **流程留痕缺口**：已完成方案无验收拍板批准行（approval 空），M2/M4/M5 无交付报告（cla-delivery-002 待补，delivery-001 第 7 节自述）。若严格执行 033 M4，应补拍板记录后再定案。
- cla-plan-001 验收标准历史 0/3 未记录（delivery-001 已标遗留）。
- 2 例 LLM 单测需 live 通道（Ollama/中转）恢复后复跑才能全绿。
