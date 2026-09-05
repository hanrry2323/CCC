# CCC 工程化 2.0 宪章

> **版本起点**：v2.0.0（2026-09-06）· 状态：P1 执行中
> **地位**：v2.0 阶段（P1–P4）所有开发的最高执行依据，与 `docs/CCC-PRIME-DIRECTIVE.md` 并行（架构层不变，工程层以此为准）。
> **缘起**：v0.x→v0.71 实战（tst900–905、xy060）暴露的结构性缺陷：验收结论靠自由文本正则解析（排版变体即断链）、失败处理无分类无预算（死循环不收敛）、环境依赖靠执行体现场解决（逐卡踩坑）、粘合工作靠人工（token/对账/巡卡）。
> **对标**：fusion（JSON verdict fail-closed / SelfHealing）、gastown（Bors 合并队列 / 四层防卡死）、forge-orchestrator（跨 Agent 交叉验证 / 门禁失败自动 Fix）、swarm-protocol（意图-认领-信号模型）、nxtg-forge（零上下文续传）。分析报告：`docs/notes/2026-09-05-*.md` 系列 + ccc-brain 账本。

---

## 一、架构不变量（v2.0 延续，任何改造不得违背）

1. **任务卡 = 唯一事实源**（`docs/dispatch/<prefix>/`）；
2. **三层架构**：线路图（未来）→ 计划（当前）→ 看板（正在进行时）；
3. **薄驱动 Engine**：只编排不执行；工具皆插件（executors.json 注册表单源）；
4. **前段 DSH / 后段 Claude Code CLI**（2026-09-04 对齐，现役绑定）；
5. **人审节点**：意图确认 / 转卡确认 / 重大合入否决（合入默认自动+老板保留否决）；
6. **CardStateStore 唯一写入门面**（CAS/卡锁/受保护提交）；
7. **插座理念**：一切工具可替换；改造只动契约载体与失败语义，不动架构。

## 二、四阶段路线

### P1 契约结构化（当前阶段）
| 项 | 内容 | 验收标准 |
|---|---|---|
| P1.1 | 验收席 verdict JSON 化：Claude CLI 输出末尾强制 `{"verdict":"PASS\|REJECT","reason":"…","findings":[{id,severity,file,line,note}]}` 工件；**无合法 JSON = 不通过（fail-closed）**；现有整行正则降级为 fallback | xy060 重审产出 JSON verdict 且被 phase2 正确消费（PASS→关闭 或 REJECT→打回） |
| P1.2 | phase2 消费 JSON verdict（读 findings 进打回原因/ledger），正则仅兜底 | phase2 定向测试覆盖 JSON 主路径+正则兜底路径 |
| P1.3 | A1 结果文件 `.ccc-result.md` 升级 JSON sidecar（`.ccc-result.json`），markdown 版保留人读 | 引擎收单读 JSON 不再 split 字符串；新旧双格式过渡期兼容 |

### P2 失败分类 + 重试预算
| 项 | 内容 | 验收标准 |
|---|---|---|
| P2.1 | `failure_class` 枚举落 sidecar/ledger：`infra / business / protocol`；每类独立动作路由：infra=冷却+环境自检清单、business=打回、protocol=一次修复轮 | 引擎日志与 ledger 可见 failure_class 字段 |
| P2.2 | 重试预算：每卡每类 maxRetries=3，耗尽 → 卡头「待人工（<原因>）」终态（新增挂起语义，复用打回态+括号），不再自动重派 | 预算耗尽卡停止自动循环，看板可见 |
| P2.3 | infra 环境自检清单：venv/token/通道/工作目录四项自动探测，结果落 ledger | infra 失败轮自动附自检结果 |

### P3 环境声明式
| 项 | 内容 | 验收标准 |
|---|---|---|
| P3.1 | 业务仓环境声明：`env-manifest`（解释器/venv 路径/测试入口/lint 入口），engine 挂载 worktree 时 fail-fast 校验 | 缺环境=派发前拦截（非执行中暴露） |
| P3.2 | 测试命令声明化：唯一入口=业务仓固定目标（Makefile/env-manifest），卡门禁节只写入口名；test-evidence.sh 改 argv 数组执行、证据落 JSON | xy060 类「反引号残留」假失败结构性消灭 |

### P4 粘合自动化
| 项 | 内容 | 验收标准 |
|---|---|---|
| P4.1 | watchdog 升级：分级 stale（1.5×/3× 心跳）+ 僵尸回收 + spawn 熔断（抄 gastown witness） | 卡死会话自动回收并有台账 |
| P4.2 | reaper 巡卡：每日卡/看板/分支三方对账，差异自动落 ledger + 看板标黄 | 对账无需人工触发 |
| P4.3 | token/凭证自动换发：redispatch/watchdog 内置 /session 登录（凭据源单源），usage-limit 自动冷却 | 重派不再 401 |

## 三、验收席 JSON verdict 契约（P1.1 规范，立即生效）

```json
{"verdict": "PASS | REJECT",
 "reason": "一句话结论",
 "findings": [{"id": "F1", "severity": "P0|P1|P2", "file": "相对路径", "line": 0, "note": "可复现说明"}]}
```
- verdict 工件 = `<work_id>-audit-verdict.json`（新）；markdown verdict 降级为 fallback；
- **无合法 JSON = REJECT（fail-closed，prose 永远推不出 PASS）**；解析失败给一次有界修复轮（重发 JSON）；
- findings 直接进打回原因与 ledger，DSH 修复轮有结构化输入。

### 正反辩论修订（2026-09-06，反方 9 项攻击采纳 6 项）

1. **【同批约束】fail-closed 不得裸奔**：P1.1 与「audit 侧 REJECT/修复轮预算」同批上线（预算模式抄 `_conflict_strikes` 现成实现）；解析失败归 protocol 类走有界重试，不产生业务打回——否则格式偶发失败=无界 DSH 修复轮（新死循环引擎）。
2. **【severity 阈值门】**（fusion review-severity-gate 校准值）：仅 P0/P1 findings 阻断（打回）；P2 findings 落 ledger 留档不打回。
3. **【golden corpus】**：以 09-05 实战畸形 verdict 样本（前导空白/围栏包裹/截断/prose 混排/编码污染）建测试语料，解析器全绿才算过。
4. **【旧口径删除判据】**：JSON 主路径验收后删除 `_claude_verdict_from_output`/stdout 兜底等死口径，grep 判零——禁止第 5 套解析口径增殖。
5. **【影子双跑】**：新解析器先影子模式双跑 ≥3 张卡比对，再切主。
6. **【待人工=结构化字段】**：预算耗尽终态落 sidecar 结构化字段（runtime_state 现成），禁止「打回（待人工…）」括号复用（base_state 剥括号后与业务打回同桶，会被误重派/误冻结）。
7. **【安全收敛】**：验收席 verdict 写入路径白名单；`.ccc-result.md` 标注 untrusted 输入；每卡 audit 预算上限（防 3456 通道争抢）。
8. **【xy060 收口路径修正】**：两个已知 findings（symlink 逃逸、frames 共存漏收）为确定性可断言——直接进业务仓测试/门禁机械闭环，不等 JSON verdict 上线；P1 与 xy060 收口解耦并行。

## 四、现役文档白名单（v2.0 开发只认这些）

| 类 | 文档 |
|---|---|
| 起点 | 本宪章 + CHANGELOG v2.0.0 |
| 架构 | CCC-PRIME-DIRECTIVE.md、docs/architecture.md、INDEX.md §0 |
| 契约 | board-task-schema.md、DOC-PROTOCOL.md、本宪章 §三 |
| 工程 | ENGINEERING-CANON.md、red-lines.md、lessons.md |
| 运行 | registry.yaml、executors.json、config.env（gitignored） |

其余 docs/ 下 v0.x 文档为史实参考；与白名单冲突时以白名单为准。

## 五、xy060 处置（P1 验收载体）

- 当前：`打回（挂起：待 v2.0 P1 结构化验收席上线后重审）`，业务实现保留于 worktree 分支（`1debaa7`…`f769514`）；
- P1.1/P1.2 落地后正规重派：预期后段产出 JSON verdict REJECT（symlink 逃逸 + frames 共存漏收两个已知 findings）→ DSH 修复轮 → PASS → 合入部署关闭；
- 已知待修 findings（Claude CLI 验收席实测产出）：①产出根 symlink 逃逸越界；②`output` 根文件与 `frames/` 子目录共存漏收 `final.mp4`。
