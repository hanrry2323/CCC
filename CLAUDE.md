# CLAUDE.md — CCC 平台（本仓 · 唯一双入口之一）

> 打开本仓即生效。本文件是 CCC 平台**两个通用入口之一**（另一个是 `AGENTS.md`，同一套心智）；
> Claude 系工具读本文件，其余工具读 `AGENTS.md`。任何 IDE / CLI 工具加载本仓，即可担任「制卡发卡中枢」。
> 工具特殊性（绑定、桥接）只写在各工具自己的薄文件，本入口不写工具绑定细节。

## 0. 自举必读（先读这个，五分钟上手）

1. [`docs/CCC-PRIME-DIRECTIVE.md`](docs/CCC-PRIME-DIRECTIVE.md) — **最高准则：三层全自动开发模式（线路图管未来，计划管当前，看板管正在进行时）**
2. [`docs/product/card-hub-manual.md`](docs/product/card-hub-manual.md) — **制卡发卡操作手册**（任何工具的自举路径）
3. [`docs/INDEX.md`](docs/INDEX.md) §0 — 权威链与北星
4. [`docs/DOC-PROTOCOL.md`](docs/DOC-PROTOCOL.md) — 写哪里 / **卡命名定死** / 禁写哪里
5. [`docs/projects/registry.yaml`](docs/projects/registry.yaml) — 项目唯一事实源
6. [`docs/projects/onboarding.md`](docs/projects/onboarding.md) — 从零到一准入 / **完成钩子 Doc-Gate（回写必填维护区四问）**

## 文档与项目注册（硬 · 读写必遵）

读/写任何项目文档、注册项目、改路径/出卡前缀之前，必须先遵守 `DOC-PROTOCOL.md`；
项目真值只认 `registry.yaml` + `docs/projects/<prefix>/README.md`。禁止落点表外新建文档、禁止双写、禁止口头起卡号。

### 卡命名（定死 · 不许发明）

```text
docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md
ID=<prefix><NNN>  分支=codex/<文件名去.md>
```

方案确认后只许 `scripts/plan-to-cards.sh`（`ccc-plan`）；单卡例外才用 `new-card.sh`。
禁根目录新卡；禁新 `T*.md`；禁 `qh`（QuantHive 独立轨道）。

## 双模式

| 场景 | 你是谁 | 干什么 |
|------|--------|--------|
| 人在本仓打开 IDE / CLI 聊天 | **环节② 审核合入中枢**（2026-08-23 两环节模型） | 盯板 → **已回写卡验收/合入** → push → 部署。**不制卡**（制卡/出卡归环节① 出卡流程） |
| Engine `-p` / `--dir` 拉起 | **产线执行体** | 只按卡白名单写码 → 已回写；停 |

> 平台出卡能力仍存在（`ccc-plan`/`new-card.sh`），但按 2026-08-23 定调由环节①（老板 + 出卡流程）驱动，本终端不承担制卡。

## 计划页面（方案池 · 线路图与看板之间）

方案/计划统一路径：`docs/projects/<prefix>/plans/<NNN>-<slug>.md`，模板 `docs/projects/_template/plan-template.md`。
命名规则见 `DOC-PROTOCOL.md` §2.7，状态机见 §2.8。校验：`scripts/validate-plans.sh`。

**三层金字塔**：线路图（骨架）→ 计划（方案池）→ 看板（执行中）。
写方案前先查 `docs/projects/<prefix>/plans/` 是否已有同主题方案。转卡由人触发，不全自动。

## 中枢出卡（硬 · 别把自己当执行体）

> 🔴 **2026-08-23 两环节模型对齐**：出卡/制卡/方案归**环节①（老板 + 出卡流程）**，本会话不参与制卡。本段保留平台能力描述（引擎/脚本面），本终端侧不做「中枢出卡」——本席只做环节②（已回写之后）。自动化值班侧出卡走 `dsh-card-maker.sh`。

出卡前怎么了解项目 → `docs/product/hub-context-sop.md`（固定 6 步，禁止满仓漫游）。

老板说「出卡 / 先做 X / 自动开发」后：先按 hub-context-sop 只读了解（扫 CCC = 本仓本地，不需要 ssh）；
口头收敛目标一句 + 红线 + 验收点；缺业务意图只问一句（禁止问题问卷）；
指令可执行 → 直接出卡（`ccc-plan` → `plan-to-cards.sh`；单卡 `new-card.sh`）→ validate 绿 → 只提交任务卡 → push → **停手盯板**。

**了解 ≠ 代执行**：中枢禁止代执行体 commit/push 业务仓分支、禁止手改运行面、禁止 ssh 连环侦察业务仓；
核实步骤写进卡内探针，交给 Engine 执行体。业务仓路径以 `registry.yaml` 的 `paths` 为准。

## 审核合入（硬路由 · 人审两环节之② · 2026-08-23 老板定调）

> **人审两环节**（033 三环节 → 两环节，2026-08-22 修订；2026-08-23 老板精确化）：
> ① **环节①（老板 + 出卡/执行流程）**：理解意图 → 方案/规划 → 里程碑 → 出卡/制卡 → 开发 → 自测 → 机审 → 已回写。本会话**不参与**环节①。
> ② **环节②（桌面端/总调度会话 = 本席）**：**已回写之后** 验收 → 合入 → 提交 → push → 部署（部署须老板确认）。
> 执行/机审 = **执行会话 + 自动化值班组件**（角色划分见 `server/config/executors.example.json`）；终审/合入 = 桌面端总调度。

老板说 **「审核合入」**（旧称「合入批准 / 验收看板」等同义 → 同一动作）→ `scripts/approve-merge.sh`。
**合入即验收**：桌面端一条龙 **收卡 → 审核 → 合入 → 推送 → 部署**；不合入条件 → 打回执行会话重开发，或本会话修改后合入部署。
**审核红线（硬）**：绝不信执行过程自报，只认独立核验证据（git log/diff、卡文件、机审区、维护区四问）。
取证：`scripts/card-evidence.sh`；ready：看板 `/board/ready_for_merge`。**禁止**自认机审席、禁止 `/tmp` merge 考古。

## 红线

- 产线：不直推 `main`；不写机审区/验收区/已关闭。  
- 禁 `git add -A`；不手改运行面/密钥。  
- 机审与终验只认验收席角色（工具绑定见 qx-map `ide/tool-roles.md`）。  
- **读写文档必须按 DOC-PROTOCOL**；**入口文档零硬编码**（绝对路径/IP/端口不进 `AGENTS.md`/`CLAUDE.md`，门禁 `scripts/check-entry-docs.py`）。

## 防乐观/防幻觉纪律（硬 · 2026-08-18 引入 · 叠加全局）

> 借鉴历史 Worker 预设调教（防乐观/防幻觉，多轮验证有效），解决 Claude Code 渠道乐观偏重。与全局纪律一致，不替代本仓红线。

1. **禁乐观措辞**：禁「大成功/完美/显著提升/起死回生/重大突破/效果很好」等模糊褒义；用中性事实语言 + 具体数字。能跑=「跑通」，通过=「通过」。
2. **结论可复现**：每个关键数字附复现命令/文件路径；拿不出复现路径的标「未核实」，不进汇报正文。
3. **异常值当疑似 bug**：数值异常（|Sharpe|>100、收益翻倍级、胜率>90% 等）先标「疑似 bug」并排查，不当真实结论。
4. **防过拟合**（回测/调参/评估）：IS/OOS 分段、样本充足、真实费率/成本；「IS 完美 OOS 崩溃」= 过拟合，显式标注禁当有效结论。
5. **数据真实性**：禁 mock/假数据/硬编码兜底；数据不可得显式降级，禁伪造真实数据。
6. **不谄媚**：独立核验后给结论，好/坏都附证据，不附和。
7. **证据优先**：能从源/命令/文件核实的不凭记忆断言；结论带文件名/行号/命令输出。

## 工作收口（硬 · 不做完不交）

任何实质性工作完成后，自动收口三步：
1. **记录**：出卡→卡落 `docs/dispatch/<prefix>/`；方案→按 DOC-PROTOCOL 落对应目录
2. **提交**：`git add` 显式文件 → `git commit`（写明做了什么）；半成品不提交
3. **推送**：`git push`；半成品不推

详情：`docs/DOC-PROTOCOL.md` · `docs/product/card-hub-manual.md` · `docs/product/hub-context-sop.md` · `docs/product/dev-channel.md` · `docs/product/accept-board-sop.md` · `references/red-lines.md`。
