# 任务卡 xy077 · A/B 质量对比报告闭环（同主题多模板 + 人工打分表 + 报告入库）

> 关联：xy-plan-008（5.3 A/B 质量评估）· 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：xy · 日期：2026-09-14 · 版本：xy077 · 状态版本：0
> 业务仓：`/Users/fan/program/apps/xianyu`（Mac2017 权威仓）

## 目标
按 xy-plan-008 5.3「A/B 质量评估」验收点「A/B 报告结构化可复现（量化 + 打分），≥1 组对比完成」补全闭环：把现有 `video-pipeline/render_all_templates.py`（已做多模板渲染+quality 检查但结果仅 stdout 打印、主题各异）扩展为**同主题多模板 A/B 对比 + 人工打分表 + 结构化报告落盘**。

## 实现要求
1. `video-pipeline/render_all_templates.py`：支持 `--topic <主题>` 参数，同一主题用 ≥2 个模板逐一出片（沿用现有 6 模板集与 config 交替逻辑），量化检测（`scripts/check_video_quality.py`）接通 `--json` 输出。
2. 对比报告落盘 `video-pipeline/output/ab-report-<ts>/`：`report.json`（每模板 {template, rendered, quality: {7x指标明细, pass/fail}, 文件}）+ `report.md`（Markdown 汇总表：模板 | 渲染 | 各指标 | 整体）。
3. 新增人工打分表模板 `video-pipeline/templates/ab_scorecard.md`：四维度打分（结构 / 画面 / 文案适配 / 整体），每维 1-5 分 + 备注列，Markdown 表格可填。
4. 跑通 ≥1 组同主题对比（任选 1 主题 × ≥2 模板），产出报告文件与打分表作为回执证据。
5. **方案关联卡登记（Q1 前置，模板纪律第5条）**：同 commit 把 xy077 追加进 CCC 仓 `docs/projects/xy/plans/008-high-expression-v2.md` 头部「关联卡」行（先 grep 实际行再 replace）。

## 红线
1. 只动：xianyu 业务仓 `video-pipeline/render_all_templates.py`、`video-pipeline/templates/ab_scorecard.md`（新增）、输出目录 `video-pipeline/output/ab-report-*`、CCC 仓 008 关联卡行。不动 pipeline 引擎、渲染核心、check_video_quality.py 本体。
2. 报告与打分表为「人工评估辅助」，不接入自动改码/质量门；不消费生产数据（用测试样片）。
3. 不引入新依赖；不强改现有但保留原 CLI 行为（无参运行兼容既有）。
4. diff 全检查：改 ≤2 文件 + 新增 ≤2 文件。

## 范围
- /Users/fan/program/apps/xianyu/video-pipeline/render_all_templates.py
- /Users/fan/program/apps/xianyu/video-pipeline/templates/ab_scorecard.md
- /Users/fan/program/apps/xianyu/video-pipeline/output/ab-report-*（产物）

## 步骤
1. 读 `render_all_templates.py` 现有结构 + `check_video_quality.py --json` 输出格式。
2. 加 `--topic` 参数：`render_all_templates.py` 在每个模板 config 中统一写该主题（除 template/style_seed 外）；量化接通 `--json`。
3. 实现 `report.json` / `report.md` 汇总（含 7 项指标 pass/fail 表）。
4. 新增 `ab_scorecard.md` 人工打分表模板。
5. 跑 1 组同主题对比（≥2 模板），产出 ab-report-<ts>/ 报告 + 打分表填写样例。
6. 008 关联卡补 xy077（grep 实际行后 replace）。
7. 写 .ccc-result.md（五段）交回写。

## 验收标准
1. `render_all_templates.py --topic <T>` 同主题 ≥2 模板出片，`output/ab-report-*/report.json` 含每模板量化指标（grep 命中 template + bitrate 等字段）。
2. `output/ab-report-*/report.md` 为 Markdown 汇总表（含模板、渲染、指标列）。
3. `video-pipeline/templates/ab_scorecard.md` 存在且含四维度打分（结构/画面/文案适配/整体）。
4. 回执含 ≥1 组同主题对比实际产出（报告文件路径 + 打分表样例）。
5. `pytest`（相关测试目录）无新失败。
6. 008「关联卡」行含 xy077。

## 门禁
- card_gate 五项校验（必填齐全、状态=待分派、项目 xy 在 registry、验收=DSH、范围路径在仓内存在）——卡满足。

## 回写要求
- 回写区四问逐项填；教训沉淀引用业务仓 docs/lessons.md 具体文件。

## 人工批注
无批注。

## 回写区

## 0. 卡标题复述

任务卡标题：**任务卡 xy077 · A/B 质量对比报告闭环（同主题多模板 + 人工打分表 + 报告入库）**

## 1. 探针输出

（执行体填写：基线现状 URL/不存在项证据）

## 2. 自测输出

（执行体填写：关键命令输出）

## 维护区

1. **方案同步**：[ ]
2. **教训沉淀**：[ ]
3. **档案/README**：[ ]
4. **线路图**：[ ]

## 机审区

（预留）
