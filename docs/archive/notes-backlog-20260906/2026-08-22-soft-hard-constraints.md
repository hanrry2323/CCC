# CCC 软约束 → 硬约束 全面排查清单（2026-08-22）

> 范围：server/board、server/engine、server/web、scripts/ 全仓「靠人工拍板 / 字符串匹配 / 事后核验」把关的检查点。
> 证据优先：每条均带 文件:行号。状态标注：软=可被绕过/依赖人工；硬=代码级强制阻断。
> 已两个先例：① --close-only 业务仓分叉硬阻断（approve-merge.sh:513-517）；② 机审 ledger provenance 硬阻断（approve-merge.sh:479-499 主路径）。

| # | 检查点 | 位置(文件:行) | 当前机制 | 【当前状态:软/硬】 | 风险（若被绕过会怎样） | 【改造方案】 | 【改造后状态】 | 工作量(S/M/L) |
|---|--------|--------------|----------|-------------------|------------------------|--------------|----------------|--------------|
| 1 | --close-only 无分支时回退本地卡机审 | scripts/approve-merge.sh:419-424 | 分支不存在时回退读本地 main 卡 `machine_audit_passed_text`，WARN「请人工确认机审证据」后放行 | 软 | 分支已删但 main 卡文本被改写「机审：通过」→ 无真实机审也放行假关闭 | 去掉文本回退；--close-only 无分支时强制查 ledger `has_action('machine_audit_pass', id)`，无记录=拒绝 | 硬 | S |
| 2 | 机审后漂移 --close-only 放行 | scripts/approve-merge.sh:451-456 | 被审 sha..tip 存在非卡改动 diff 时，--close-only 模式 WARN「人工已确认无害」放行 | 软 | 机审后改业务代码绕过复审直接合入 | 漂移一律 return 1（与普通模式一致）；确需放行须走二轮机审留第二条 machine_audit_pass ledger | 硬 | S |
| 3 | 完成钩子(维护区) --close-only 放行 | scripts/approve-merge.sh:462-468 | 维护区校验失败（分支排版/声明冲突）--close-only WARN「人工已确认」放行 | 软 | 完成钩子被 --close-only 绕过 → 未填四问也合入 | 去掉放行分支；维护区失败=拒绝合入，与普通模式一致 | 硬 | S |
| 4 | 机审 ledger provenance 日期边界降级 | scripts/approve-merge.sh:485-494 | 无 machine_audit_pass 记录时，从卡文本正则取 `日期：` 字段，<2026-08-16 则 WARN 降级放行 | 软 | 8-16 后新卡复制旧卡「日期」字段 → 混过 ledger 门禁（假 provenance） | **✅ 已修（P0-3 2026-08-22）**：降级判据改为「账本是否为空」（`_machine_audit_pass_ids()`），卡文日期不再参与 → 伪造免疫 | 硬 | S |
| 5 | approve_merge 账本写失败不阻断 | scripts/approve-merge.sh:550-555 | `record_action('approve_merge', ...)` 失败仅 echo WARN「不影响合入，建议补记」 | 软 | 合入批准无账本证据，三节点证据链断，后续审计不可追溯 | 写账本失败=整卡合入失败回滚（写入在 close_card 后，改为先写账本再关卡） | 硬 | S |
| 6 | --ready 队列判定靠卡文本「机审：通过」 | scripts/approve-merge.sh:90 + server/board/models.py:66-125 | ready 队列用 `machine_audit_passed_text`（纯正则）筛分支卡，无 ledger 校验 | 软（入口软，最终合入有 ledger 兜底） | 假「机审：通过」文本卡进 ready 队列，污染合入批次面 | ready 扫描同时查 ledger `has_action('machine_audit_pass', id)` 才入队 | 硬 | S |
| 7 | Doc-Gate 维护区四问=自声明 + 字符串/存在性校验 | server/board/docgate.py:219-398（说明非空 262-264；Q1 查方案 266-320；Q2 查文件存在 329-341；Q3/Q4 查 git diff 343-396） | 四问勾选与「说明」为执行体自声明；校验仅查字符串非空/文件存在/diff 有无，不核验说明内容真实性 | 软 | 执行体填「是」+空泛说明谎报方案同步/教训沉淀/档案更新，无真实产物也过关 | Q1 已硬（查方案状态+关联卡）；Q2/Q3/Q4 保持文件+diff 硬校验；说明内容真实性需机审席 LLM 交叉+人工抽查，难全自动 | 部分硬 | L |
| 8 | 维护区检查双实现（docgate vs observer） | server/engine/observer.py:1185-1207 `is_maintenance_complete`、123-165 `check_missing_four_questions` vs server/board/docgate.py:219 | 同一检查点两套正则实现，各自解析维护区 | 软 | 两实现规则漂移（2026-08-22 F3 已对齐一次）→ 覆盖率与门禁结论打架 | **✅ 已修（F3 2026-08-22）**：`is_maintenance_complete` 对齐 docgate 的 `[x]` checkbox 容忍（`x/X/✓/√`）；完全合并为单实现待后续 | 硬 | S |
| 9 | 机审通过判定=纯字符串正则 | server/board/models.py:66-125；server/web/audit_evidence.py:27-51；server/engine/main.py:1506-1516 | `machine_audit_passed_text` 正则匹配「机审：通过/结论：通过」，任何 AI 可在卡文本写此行即判通过 | 软 | 卡文本伪造机审通过（合入已被 ledger 兜底，但看板列/audit_evidence/ready 队列仍信文本） | **✅ 主体已修（P0-3 2026-08-22）**：`parse_card` 的 machine_audit_passed 改从 ledger `has_action` 派生（账本为空才降级卡文）；audit_evidence / ready 队列仍用文本正则，待迁移 | 硬 | M |
| 10 | 方案功能卡三要素：旧方案 WARN | scripts/validate-plans.sh:50-67 | 旧方案功能卡缺 颗粒度/依赖/架构位置 仅 WARN；新模型子项目方案 FAIL | 软 | 旧方案无限期缺三要素，新老标准长期并存 | 给 WARN 设过渡截止日期，到期后旧方案也转硬 | 硬 | S |
| 11 | 方案关联卡活跃检查依赖本地卡文件+状态 | scripts/validate-plans.sh:244-296 | find 本地卡文件 + head 卡头状态判断；文件缺失按活跃算（安全向）；「待分派/已回写」远端滞后仅 WARN | 软 | 本地滞后误判「关联卡未关」→ 方案误 FAIL 或误放行 | 改读 cards.index.jsonl 或 git 权威（与 loader 同源），消除本地 find 双解析 | 硬 | M |
| 12 | 自验收交叉检查仅 WARN | server/board/validate.py:397-407 | 新卡执行体≠验收席 2026-08-07 起仅 warn（历史卡兼容）；仅禁席（Codex/Cursor）error | 软 | 新卡混入交叉验收，「谁开发谁验收」红线被绕过 | 新卡（new 类型）交叉=error 硬阻断；仅旧卡保留 warn | 硬 | S |
| 13 | 验收区通过=字符串「✅」/「判定：通过」 | server/board/validate.py:92-117 + server/board/card_header.py:182-230 | validate 判「已关闭但验收区无 ✅/判定：通过」为 error；有标记即信 | 软 | 卡文本伪造「判定：通过」+「状态：已关闭」即通过一致性检查，无 accept 账本校验 | validate/机审/合入增加查 ledger `has_action('accept')`；文本仅作展示 | 硬 | M |
| 14 | web 鉴权默认关闭 + 写接口无老板角色区分 | server/web/server.py:128-139（`CCC_WEB_AUTH_REQUIRED` 默认 0 免登录）+ 283（NO_AUTH_PATHS）+ 3047-3162（transition 作废/重派）+ 3164-3270（audit 触发） | 默认免登录；开启后任何持有 token 用户可作废卡/重派/触发机审/改方案，无老板级授权区分 | 软 | 写操作面（作废、合入类动作、机审触发）可被非老板触发，破坏「老板合入批准/验收拍板」权威 | 写接口强制 auth；作废/验收/合入类动作加老板级 token 或二次确认 | 硬 | M |
| 15 | 部署端健康检查仅 WARN 不阻断 | scripts/approve-merge.sh:724-782 | 合入后检查 xy/mx/hp 部署端，异常仅 WARN「需人工确认」，注释明示「不阻断合卡」 | 软 | 合入后部署端失联无人跟进 → 线上与代码漂移 | 部署端异常=合入回执标记 BLOCKED 进待办；或关联机器人自动拉起/回滚 | 硬 | M |
| 16 | sync_plan_cards 方案关联卡同步失败仅 WARN | scripts/approve-merge.sh:375-377 | 卡关闭后把卡 ID 写入方案「关联卡」；失败仅 print warn，不阻断 | 软 | 卡关了但方案关联卡/进度不同步 → 方案进度漏算 | 失败=整卡合入失败（与 close_card 同事务） | 硬 | S |

## 补充说明

- 已为硬（未列改造）：业务仓分叉阻断（approve-merge.sh:513-517）、8-16 后 ledger provenance 主路径阻断（479-499）、机审区格式校验（card_header.py:182-230）、Engine 派发门禁链（main.py:3516-3715 11 个 gate）、工作树须在 main + ff-only（501-507）。
- 行 1/2/3 属于同一类「--close-only 人审放行后门」，可合并改造：把 `--close-only` 语义从「绕过校验」收敛为「仅关卡不重审」。
- 行 4 是当前最容易被利用的软点：日期降级判据取自卡文本，纯字符串可控。
- 行 9/13 是「文本自证」类，建议统一向 ledger 迁移：机审=has_action(machine_audit_pass)、验收=has_action(accept)、批准=has_action(approve_merge)。
