(node:70912) ExperimentalWarning: stripTypeScriptTypes is an experimental feature and might change at any time
(Use `node --trace-warnings ...` to show where the warning was created)
扫描完成（21/30 次调用，时间盒内收口）。以下为已核实发现清单。

---

# CCC × qx-map 合规红线扫描报告（只读 · Mac2017 视角）

**总判断**：现行**配置与脚本层面无旧端口引用、无明文密钥、无 git add -A 违规**；真正的问题集中在**一处现行文档死档**（CCC `docs/relay/KEY-POOL.md`）——它同时违反「中转站现行引用」与「落点表外文档树」两条红线。另有一处 qx-map 路径权威文档的退役标注缺失（低危）。

## 发现清单

| 面 | 位置 file:行号 | 现象 | 证据(命令输出) | 建议处置 | 置信度 |
|---|---|---|---|---|---|
| 中转站 | CCC `docs/relay/KEY-POOL.md:4-7,18,28` | 现行路径文档把**已冷冻**的 M1 `:4100/:4102` 仍写成「权威主机」，附现行操作命令；最后修改 2026-08-01，早于 08-06 冷冻决议 | 见证据① | **改**（标注冷冻/改写为 2017 `:6100/:6102`）或整档迁 `docs/archive/` | 高 |
| 文档落点 | CCC `docs/relay/` 整树 | `docs/relay/` 不在 DOC-PROTOCOL §1 落点表内；表外新建树属明文禁止；且 KEY-POOL.md:8 引用的 `docs/product/loop-engineer-authority.md` **已不存在**（死引用） | 见证据② | **删**（并入 archive）+ 修死引用 | 高 |
| 文档一致性 | qx-map `cluster/path-authority.md:39,99`（+ `AGENTS.md:128`） | 唯一路径基准中 `ccc-relay-runtime`「本机 4000」无退役标注（对比同表 loop-router 有 🧊 冷冻标注）；与同仓 AGENTS.md:147「:4000 已退役离线」不一致 | 见证据③ | **改**（补「已退役」标注） | 中 |
| git 纪律 | CCC `docs/archive/legacy-phase2-plan.md:70`、`docs/archive/dev-workflow.md:59`、`docs/archive/patrol-v4.md:61` | 归档区历史文档出现实际 `git add -A` 用法（归档豁免，非现行违规） | 见证据④ | **留**（归档区豁免；如需彻底可加「史」标） | 低 |

## 通过项（已核实无违规）

| 检查项 | 结论 | 证据 |
|---|---|---|
| 卡命名 `NNN-slug.md` | ✅ 75 个方案文件**全部合规**，prefix 内无重复编号（此前误报是我正则写错，已修正复核） | `find …/plans/*.md` + 正则校验：0 不合规、0 重复 |
| 现行配置文件/脚本旧端口 | ✅ 仅 `scripts/check-entry-docs.py:34` 把 `:4102` 列为「退役端口」巡检项（正确做法）；server 侧 json/yaml/plist/example 无旧端口 | `grep -rnE '4100\|4102\|:4000' server/ scripts/` |
| 密钥 | ✅ 两仓 76 处疑似命中**全部为占位/变量名/归档审查记录**，无真实明文 key；qx-map 决策档 `…08-14.md:47` 的 API_KEY 值为 11 字符占位（非 `sk-` 形态） | 脱敏探测：`值长度 11 / 形态: 占位/非key` |
| 2017 shell 明文 key（历史 P0-1） | ✅ 本机 `~/.zshrc` `~/.zshenv` `~/.zprofile` **已无任何 key 变量行**（与 handover 记载的 DEEPSEEK_API_KEY 明文状态不一致 → 已清理或迁移；launchd plist 等**未核实**） | `grep -c` 三文件均 0 行 |
| registry.yaml 唯一事实源 | ✅ 文首「CCC 项目注册表（唯一事实源）…禁止手维第二份真值」+ DOC-PROTOCOL 落点表第 24 行强制 registry 落点 | `registry.yaml:1-4` |

## 关键原文证据

**证据①（KEY-POOL.md 现行旧端口，`read` 原文）**
```
4: > **权威主机**：M1（对话面 + 中转站）· `com.ai-loop-router` · `:4100` / `:4102`
7: > **Mac2017**：通过 `http://192.168.3.140:4100` 连接 M1 的 ai-loop-router；不再本地运行 relay
18: | 看冷却 / 清短冷却 | `GET/POST http://127.0.0.1:4100/admin/cooldowns`（`?force=1` 全清） |
28: **Claude Code + OpenCode 一律打 `flash` / `loop/flash`。** `:4100` 与 `:4102` 共用同一 flash 上游表…
```
时效证据：`git log -1 --format='%ci' -- docs/relay/KEY-POOL.md` → **2026-08-01 12:22 a5ca5800**（早于 08-06 决议 14 天，冷冻后未再更新）。

**证据②（落点表外 + 死引用）**
```
DOC-PROTOCOL.md:11:  2. **先问落点再写**：下表没有的路径 = **禁止新建**；应归档或并入现有页。
DOC-PROTOCOL.md:218: - 新建落点表外的说明/设计树（如 `docs/qb/` 深文档）
KEY-POOL.md:8: > **冲突以** [`docs/product/loop-engineer-authority.md`](../product/loop-engineer-authority.md)…
ls: /Users/fan/program/CCC/docs/product/loop-engineer-authority.md: No such file or directory
```

**证据③（路径权威未标退役）**
```
path-authority.md:37: | ai-loop-router | … | loop-router 源码，本机 4102（🧊 冷冻 2026-08-06） |
path-authority.md:39: | ccc-relay-runtime | /Users/apple/.ccc/relay-runtime/ | M1 | ccc-relay 副本，本机 4000 |
path-authority.md:99: | M1 端口 | 4102 | 4000 |        ← 4000 行无退役标注（AGENTS.md:147 声明已退役）
```

**证据④（归档区 add -A 残留，豁免）**
```
docs/archive/legacy-phase2-plan.md:70: git add -A
docs/archive/dev-workflow.md:59: | Commit | `git add -A && git commit` | …
docs/archive/patrol-v4.md:61: │  → 如果有状态变更 → git add . && git commit │
（现行文档均为「禁 git add -A」表述：CLAUDE.md:65 / AGENTS.md:98 / dev-packets/_TEMPLATE.md:16；test-qx-redlines.py:65-69 有硬拦测试）
```

## 未核实项（明确标注）
- 2017 全盘明文 key：仅查了 `~/.zshrc/.zshenv/.zprofile` 三文件，launchd plist / 其他 shell 文件未核实。
- `docs/relay/` 树内其余文件（如无 KEY-POOL 的配套档）未逐一核内容。
- 两仓近期 commit 是否真的发生过 `git add -A` 操作无法从 git 历史直接证明（该命令不留痕），仅以文档残留判据核查。

**建议下一步（若需）**：处置 F1 = 把 `docs/relay/KEY-POOL.md` 迁入 `docs/archive/` 并加「史」标（或改写为 2017 :6100/:6102 版），同时修掉第 8 行死引用；F2 = path-authority.md 第 39/99 行补「已退役」标注。均为文档层小改，不涉运行面。
loop-code.md:52「M1 → ai-loop-router `http://127.0.0.1:4100`」；:54「端口 `:4100`/`:4102`」 | 改/删：标「史」或按基础设施.md 现行口径重写 | 高 |
| 2-3 口径漂移 | qx-map `AGENTS.md:140` vs `__archive__/decisions/ClaudeCode直连OpenCode-go套餐-配置经验-2026-08-14.md:11,79`、`DSH配置OpenCode-go直连通道-2026-08-16.md:8` | AGENTS.md 仍宣称「唯一中转站…M1 与 2017 的 Claude Code / OpenCode **全部指向这里**」，但 08-14 决策已把 M1/Win/2017 三机 Claude Code 改为 **opencode.ai/zen/go 直连默认**（6100 降为备用），08-16 DSH 又新增直连通道——「唯一出口」口径已与现行决策冲突（需老板裁决：直连=例外并修订口径，或回归唯一中转） | AGENTS.md:140「**唯一中转站**｜Mac2017 `:6100`(Anthropic)+`:6102`(OpenAI)｜M1 与 2017 的 Claude Code / OpenCode 全部指向这里」；决策:11「…绕开中转站。`claude -p` 实测…已设为 M1 Claude Code 默认出口」；:79「Mac2017（fan@）的 Claude Code 从**本机中转站**换为 **OpenCode 官方直连**」；DSH 决策:8「新增一条 **opencode-go 直连通道**…现有 loop-6102（中转）通道与默认模型**原样保留**」 | 留待裁决：修订红线口径或回退直连 | 中（运行面未核实） |
| 2-4 旧端口无退役标注 | qx-map `AGENTS.md:128` | 仓库分布表 ccc-relay-runtime 行写「M1，`:4000`（与 loop-router **独立**）」无「已退役」标注，同文件 :147 已写「ccc-relay（:4000/:4002）已退役离线」，且 CCC registry.yaml:232 标 archived | AGENTS.md:128「| ccc-relay-runtime | `/Users/apple/.ccc/relay-runtime/` | M1，`:4000`（与 loop-router **独立**）|」；registry.yaml:232-234「status: archived … 旧中转副本（已离线）」 | 改：该行补「已离线/史」标注 | 中 |
| 2-5 合规确认 | CCC `server/config/config.env:8-9,19`、`.ccc/infrastructure.md:22-33`、qx-map `REASONIX.md:14`、`projects/manifest.md:25-26` | 现行配置与权威文档的 6100/6102 口径一致；4100/4102/4000 均以冷冻/退役/❌ 形式出现 | config.env:8-9「WEB_PORT=7788 … RELAY_PORT=6102」；:19「RELAY_UPSTREAM_URL=http://127.0.0.1:6102」；infrastructure.md:24-26「6100 ai-loop-router（Anthropic）… 6102 ai-loop-router（openai-chat）」；manifest.md:25-26「M1 ai-loop-router 4100/4102 ❌」。验证命令 `grep "4100|4102|4000|4002" server -g '*.py'` → 仅 1 条测试注释（test_kb_seed_integrity.py:256） | 留 | 高 |

### 红线 3：文档落点 / registry.yaml 唯一事实源 / 禁双写

| 面 | 位置 file:行号 | 现象 | 证据（原文+验证输出） | 建议处置 | 置信度 |
|---|---|---|---|---|---|
| 3-1 落点表外新建目录 | qx-map `__dev__/`（3 文件：dsh-eval-checklist.md / dsh-lan-access-plan.md / dsh-behavior-rules-injection.md） | qx-map 顶层出现未登记目录 `__dev__/`（不在 AGENTS.md 目录结构、无任何权威文档引用，唯一自引用在文件内部）；按 CONVERGENCE-GOVERNANCE §五，方案/流程细则应落 CCC plans/ 或 `__archive__/decisions/` | `glob * /Users/fan/qx-map/__dev__` → 3 文件；`grep "__dev__" /Users/fan/qx-map` → 仅 `__dev__/dsh-eval-checklist.md:84` 自引用；dsh-lan-access-plan.md:3「起草：DSH（DeepSeek Harness）本体 · 2026-08-15」（DSH 自起草方案落 qx-map） | 改：迁入 `__archive__/decisions/` 或 CCC `docs/projects/ccc/plans/`（如 ccc-plan-029 关联） | 中 |
| 3-2 落点表外现行文档 | CCC `docs/relay/KEY-POOL.md`、`docs/executors/*`、`docs/runbooks/pre-test-dual-host-sync.md` | 这些目录不在 DOC-PROTOCOL §1 落点表（INDEX/roadmap/registry/dispatch/plans/product白名单/deploy/notes/archive）内，却含**无「史」标记的现行文档**；INDEX.md §0/§1 均未引用它们（孤儿文档） | `grep "KEY-POOL|executors/|relay/|runbooks/" docs/INDEX.md` → 0 命中；DOC-PROTOCOL.md:18-30 落点表无 relay/executors/runbooks 路径；创建时间未核实（git 不可用） | 改/删：逐篇判定「标史」或并入落点表 | 中 |
| 3-3 合规确认（SSOT 成立） | CCC `docs/projects/registry.yaml`（唯一 yaml）、`server/board/models.py:21-23`、`server/tests/test_project_registry.py:20-35`、`docs/dispatch/T-mapping.md:9` | registry.yaml 唯一事实源机制成立：代码侧 PREFIXES 从 registry 派生、SSOT 测试断言、T-mapping 只作历史对照；未发现第二份真值 | `glob *.yaml docs/projects` → 仅 registry.yaml；models.py:21「T54：PREFIXES / FORBIDDEN ← docs/projects/registry.yaml（禁止手维第二份）」；test:20「assert set(models.PREFIXES) == set(from_reg)」 | 留 | 高 |
| 3-4 跨仓登记缺口 | CCC `docs/projects/registry.yaml:184-186` vs qx-map `command-post/workers.md:68-69` | registry 中 qx-map 的 mac2017 路径为 `null`（只登记 M1），但 workers.md 登记 2017 两个席位 LoadLocal=`/Users/fan/qx-map` 且本机确实存在该副本——registry 未登记 2017 qx-map 副本 | registry.yaml:185-186「paths: m1: /Users/apple/qx-map, mac2017: null」；workers.md:68「S116-01 … LoadLocal: /Users/fan/qx-map」；`ls -d /Users/fan/qx-map` 存在 | 改：registry qx-map 条目补 mac2017 路径或标注副本 | 中 |
| 3-5 观察 | CCC `docs/dispatch/cards.index.jsonl.lock` | dispatch 目录残留索引锁文件（`.lock` 不应入库；是否为 git 追踪未核实） | `glob * docs/dispatch` 末尾两项：`cards.index.jsonl`、`cards.index.jsonl.lock` | 留观察/确认 git 状态后清理 | 低 |

### 红线 4：卡命名 prefixNNN-slug.md 定死

| 面 | 位置 file:行号 | 现象 | 证据（原文+验证输出） | 建议处置 | 置信度 |
|---|---|---|---|---|---|
| 4-1 合规确认 | CCC `docs/dispatch/**`（275 项） | 188 张前缀子目录卡文件名**全部**匹配 `^[a-z]{2,4}\d{3}-[a-z0-9-]+\.md$`；dispatch 根目录无非 T 新卡（87 项根文件均为 T 历史卡/T-mapping/索引）；卡头「项目」字段 519 处解析均属合法前缀 | 验证命令：`glob * docs/dispatch` → 正则过滤 0 违规；`grep "项目：" docs/dispatch -g '*.md'` → 519 命中，非法命中均出自正文描述（如 mx040:144 审查清单）非卡头；卡头样例 ccc005:3「…项目：ccc · 日期：2026-08-06」 | 留 | 高 |
| 4-2 合规确认 | CCC `docs/DOC-PROTOCOL.md:43-135`、`docs/AGENTS.md:24-32`、`docs/dispatch/T-mapping.md:5` | 命名规则定死且门禁在位（new-card.sh + validate.py），T 卡只读保留不批量改名 | DOC-PROTOCOL.md:51「路径 = docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md」；:90「禁止新出 T<数字>-*.md（旧 T 卡只读保留）」；AGENTS.md:32「禁根目录新卡；禁新 T*.md；禁 qh」 | 留 | 高 |
| 4-3 观察 | 编号连续性 | ccc 前缀存在跳号（如 ccc011/018/021→022 中 021 单独存在、ccc017/021/059 等），属历史关闭/删除留空，未见手造冲突 | `glob * docs/dispatch/ccc` 对照编号序列（ccc001-067 区间内 011/030 等缺失） | 留（规则允许） | 中 |

### 红线 5：git 纪律（禁 git add -A · 显式路径）

| 面 | 位置 file:行号 | 现象 | 证据（原文+验证输出） | 建议处置 | 置信度 |
|---|---|---|---|---|---|
| 5-1 🔴 现行文档含违规用法 | CCC `docs/runbooks/pre-test-dual-host-sync.md:20` | 非 archive 的现行 runbook 明示 `git add -A`（且内容为 2026-08-02 重构前旧服务名 `com.ccc.chat-server`/`routers/desktop.py`，明显过期）；:32 另有 `git reset --hard origin/main` | 原文：:20「git add -A && git commit -m "…" && git push origin main」；:17-21「cd ~/program/CCC … 确认只含本次意图改动后」；验证命令 `grep "git add -A|git add \\.|add --all" docs -g '*.md'`（排除 archive）→ runbooks 命中 | 改/删：标「史」或改写为显式路径 | 高 |
| 5-2 合规确认（门禁/代码） | CCC `server/engine/main.py:410`；qx-map `sync/tests/test-qx-redlines.py:64-67`；CCC/CLAUDE/AGENTS 规则行 | 引擎 git add 为显式路径；qx-map 红线测试硬拦 `git add -A/--all/.`（42 用例接入 daily-patrol）；两仓规则文档均禁 `git add -A` | main.py:410「["git", "add", "--", work.card_path]」；test-qx-redlines.py:65-67「("git add -A", "deny")…」；CCC AGENTS.md:98「禁 `git add -A`」；qx-map CLAUDE.md:49「禁 `git add -A`」 | 留 | 高 |
| 5-3 未核实 | 两仓 git 提交历史 | 是否曾有 `git add -A` 实况提交无法核实——bash 故障无法跑 `git log`，.git 元数据被 glob 排除 | 本会话 `git -C … log` 多次调用均返回 `Error: invalid arguments: missing required property "description"` | 留待后续 bash 恢复后补查 | 未核实 |

### 红线 6：密钥（不碰明文 · 只占位引用）

| 面 | 位置 file:行号 | 现象 | 证据（原文+验证输出） | 建议处置 | 置信度 |
|---|---|---|---|---|---|
| 6-1 合规确认 | 两仓全文 | 未发现真实密钥明文/私钥/高熵 token；仅 archive 测试夹具假钥与截断前缀 | 验证命令：`grep "sk-[A-Za-z0-9]{10,}|BEGIN PRIVATE|AKIA|ghp_" /Users/fan/program/CCC` → 3 命中均为 archive 测试假钥（test_security_hardening.py:18「API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456」）+ 1 误报（dispatchCard.js:387「sk-dispatched」假阳性）；qx-map 同 pattern 0 命中；两仓 `glob .env*` 均为空 | 留 | 高 |
| 6-2 观察（占位标准） | qx-map `__archive__/decisions/ClaudeCode直连OpenCode-go套餐-配置经验-2026-08-14.md:47,79`、`DSH配置OpenCode-go直连通道-2026-08-16.md:38` | 决策档含**截断密钥前缀** `sk-Wnoey…` / `sk-cW9KiN…`——非完整明文但泄露前缀 7-8 位，建议统一为尾 4 位掩码 | 决策:47「export ANTHROPIC_API_KEY="sk-Wnoey…"」；:79「新 key `sk-cW9KiN…`（老板提供…）」；DSH:38「值=go 套餐 key，占位 `sk-Wnoey…`」 | 改：截断为 `sk-***noey` 类掩码 | 中 |
| 6-3 观察 | CCC `server/config/config.env:35-37`（gitignored 本地生产文件） | 本地生产配置含弱 Web 凭据（账号 ccc、口令哈希=sha256("ccc")，注释自曝口令），另有占位 token `ccc-relay-flash`；文件被 .gitignore:24 覆盖未入库 | config.env:35-37「CCC_WEB_USERNAME=ccc / CCC_WEB_PASSWORD_HASH=64daa4…（= sha256("ccc")）／CCC_WEB_TOKEN_TTL=3600」；.gitignore:24「server/config/config.env」 | 留（本地）+ 建议口令加强（运维项） | 中 |
| 6-4 合规确认 | CCC 引擎/文档 | 密钥处理符合「只占位引用」：KEY-POOL.md:22「密钥只进 `~/.ccc/relay/*`；仓内文档只写账号名 / key_tail / 角色，永不写完整 sk-」；loop-code.md:71「`CCC_AGENT_118INK_KEY` = `sk-…`（本机 env，勿提交）」 | 见左列原文 | 留 | 高 |

### 红线 7：一票否决（业务意图违背 / 系统性越界 / 安全漏洞）

| 面 | 位置 file:行号 | 现象 | 证据（原文+验证输出） | 建议处置 | 置信度 |
|---|---|---|---|---|---|
| 7-1 安全风险（已接受型） | qx-map `__archive__/decisions/dsh-web-局域网暴露-全接口绑定-2026-08-15.md:40-41` | DSH Web 绑 `0.0.0.0:3080`，文档自认「RCE 级」风险且明确「信任栅栏是可达性策略不是认证」；老板已拍板、内网确认无不可信设备——属**已文档化的已接受风险**，非静默越权，但建议持续跟踪官方认证层并确认无暴露到公网 | :41「绑 0.0.0.0 = 内网任意设备可驱动 DSH 执行代码（RCE 级）…栅栏是可达性策略不是认证。已确认内网无可信设备」；:21-30 上线方案（cordis.patch.yml webserver 0.0.0.0:3080） | 留（老板已拍板）+ 建议确认 3080 无公网端口映射、认证层落地后收敛 | 中 |
| 7-2 口径冲突（需裁决） | qx-map `__archive__/decisions/ClaudeCode直连…2026-08-14.md`、`DSH配置OpenCode-go直连通道-2026-08-16.md` vs AGENTS.md:140 | 直连出口（绕 6100/6102）为老板批准的配置变更，与红线 2「唯一出口」口径冲突——是否触发一票否决由老板判定；本审计判定为**口径漂移**而非系统越权（均有决策留痕） | 证据同 2-3 | 留待裁决 | 中 |
| 7-3 合规确认 | 全仓 | 未发现「业务意图违背 / 系统性越界」类现行违规（机审打回标准即含三红线：executors.json:42「只有原则性红线问题（业务意图违背/系统性越界/安全漏洞）才打回」） | 见左列原文 + 各红线逐项核查结论 | 留 | 高 |

---

## 2. 「查过、无异常」清单（附验证命令）

| 项 | 验证命令（工具调用） | 输出摘要 | 结论 |
|---|---|---|---|
| 卡头「项目」字段=前缀 | `grep "项目：" docs/dispatch -g '*.md'` | 519 命中；头部字段全部合法，非法命中均在正文 | 无异常 |
| registry.yaml 唯一 yaml | `glob *.yaml docs/projects` | 仅 1 个文件 | 无异常 |
| 两仓无 .env 入库 | `glob .env*`（两仓） | 均为空 | 无异常 |
| 引擎 git add 显式路径 | `read server/engine/main.py:410` | `["git","add","--",work.card_path]` | 无异常 |
| 6100/6102 为代码现行值 | `grep "6100" server -g '*.py'` | 22 命中（config/loader、brain、probe 等现行引用） | 无异常 |
| server/ 无旧端口现行 | `grep "4100|4102|4000|4002" server -g '*.py'` | 仅 1 条测试注释 | 无异常 |
| 机审区/开发禁令在位 | `read server/config/executors.json:10,42,53` | 开发提示含「禁止自置已关闭、禁止写验收区/机审区」；机审提示含「禁止 ## 验收区、禁止已关闭」 | 无异常 |
| 入口文档零硬编码门禁 | `read scripts/check-entry-docs.py:26-35` | FORBIDDEN_PATTERNS 含 `/Users/`、IP、`:6100/:6102/:4102` 等 | 机制在位 |
| qx-map 红线测试 | `read sync/tests/test-qx-redlines.py:64-67` | `git add -A/--all/.` 均 deny，42 用例 | 机制在位 |
| 方案命名 prefixNNN-slug | `glob *.md docs/projects/ccc/plans` | 33 个方案文件名均 `<NNN>-<slug>.md` | 无异常 |

---

## 3. 覆盖度自评

**读了（实读原文）**：
- qx-map：AGENTS.md（全文 430 行关键段）、CLAUDE.md、REASONIX.md、ide/tool-roles.md（74 行全读）、command-post/workers.md（91 行全读）、ide/doc-hygiene.py、sync/tests/test-qx-redlines.py、sync/board-live.md、`__dev__/` 3 文件（dsh-behavior-rules-injection.md 全读）、`__archive__/decisions/` 关键 8 篇（DSH 局域网暴露/ClaudeCode 直连/DSH 直连/机审双轨/模型出口统一/OpenCode 接管等）、目录结构全量 glob（276 文件）。
- CCC：docs/DOC-PROTOCOL.md（231 行全读）、INDEX.md §0/§1、registry.yaml（234 行全读）、AGENTS.md、CLAUDE.md、CONVERGENCE-GOVERNANCE.md、machine-audit-flow.md、dev-channel.md、executors.json（71 行全读）、config.env、.gitignore、.ccc/infrastructure.md、archive/loop-engineer-authority.md（头部）、scripts/check-entry-docs.py、references/red-lines.md（头部）、server/engine/main.py 关键段（3270-3350 / 2747-2850 / 395-425）、server/board/models.py、server/board/roles.py、server/config/config.env、docs/relay/KEY-POOL.md（151 行全读）、docs/executors/overview.md + loop-code.md（全读）、docs/runbooks/pre-test-dual-host-sync.md（头部）、docs/dispatch 全量 275 项（文件名级正则校验）+ 样例卡头（ccc005/ccc057/xy009 等）。

**没读（明确列出）**：
- CCC 9866 文件中的绝大多数正文（按红线条目做了模式级 grep：端口/密钥/卡命名/机审）；qx-map 276 文件中的非关键正文。
- **git 历史**（两仓 commit log / 是否曾用 `git add -A` / 文档创建时间）——bash 故障，**未核实**。
- **运行面**：2017 端口监听实况（6100/6102/3080/7788）、launchd 状态、`~/.claude/settings.json`、`~/.dsh/settings.yaml`、plist、看板 API 实时值（board-live.md 快照为 2026-08-15 16:36 生成，已超 15 分钟，按 AGENTS.md 规则应刷新，但刷新脚本会写盘、审计只读故未执行）。
- M1（192.168.3.140）与 Windows/HP 侧文件（本机无访问通道）。

**推断（非实读）**：
- KEY-POOL/overview/loop-code/runbook 的**创建时间**与「是否为落点表规则落地后新建」（无 git，无法确证）——判定依据为内容与现行权威的矛盾本身。
- 6 张 audit-log-restore 卡的实际机审过程（未读 engine 日志）。
- 直连出口的**运行时生效状态**（决策档为文本证据，settings.yaml/settings.json 在仓外）。

**工具限制声明**：本会话 bash 工具绝大部分时间返回 `invalid arguments: missing required property "description"`（疑似 harness 侧故障），故验证命令以 read/glob/grep 工具调用替代；凡需 bash 的验证（git log、curl、lsof、ssh）一律标「未核实」，未作任何推测性断言。

---

## 4. 结论（结论先行）

1. **红线 2 有两处实锤**（高置信）：CCC `docs/relay/KEY-POOL.md` 与 `docs/executors/{overview,loop-code}.md` 仍把 4100/4102 写成「现行」且无「史」标记——违反「旧端口只许历史标注」，应标史/重写。
2. **红线 5 有一处实锤**（高置信）：现行 runbook `docs/runbooks/pre-test-dual-host-sync.md:20` 明示 `git add -A`——违反显式路径提交纪律，应标史或改写。
3. **红线 1 代码合规、文档残留**（高置信）：2017 机审固定交叉配对已在引擎硬编码（main.py:2827-2831），但 dev-channel/machine-audit-flow/executors.json 三处文档仍残留「自验收」旧口径，建议同步修订。
4. **红线 2 口径漂移需老板裁决**（中置信）：08-14/08-16 决策已把 Claude Code（三机）与 DSH 改为 opencode.ai/zen/go **直连默认**，AGENTS.md「唯一出口 6100/6102」已事实过期——要么把直连定为例外并修订红线口径，要么回退直连。
5. **红线 3/4/6 基本合规**：registry.yaml SSOT 机制成立、卡命名 188 张零违规、两仓无密钥明文；遗留项为 qx-map `__dev__/` 落点表外目录（中）与决策档截断密钥前缀（中）。
6. **红线 7 无静默越权**：唯一高影响项为 DSH Web 0.0.0.0 绑定（RCE 级），但已文档化且老板拍板，属已接受风险，建议跟踪认证层落地。

**建议动作（按优先级）**：① 处理 2-1/2-2/5-1 三处实锤（标史或重写）；② 老板裁决 2-3 直连口径并同步 AGENTS.md；③ 修订 1-1 三处文档残留口径；④ 补 DSH 到 workers.md/tool-roles.md（1-4）；⑤ 处置 `__dev__/` 落点（3-1）。
EXIT=0
