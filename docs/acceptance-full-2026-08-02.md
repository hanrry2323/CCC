# T17 全量验收报告 · CCC 重构（INT-120）

> 执行体：Claude Code（CLI）· 关联：T17 任务卡 · 日期：2026-08-02 · 验收：Codex
> 定位：M4 前最后一道大闸。独立取证（不看回写、只信取证），对照契约/决策/M4 门槛找问题，修复 P0/P1，产出本报告。
> 纪律遵守：本报告只记录「发现的问题」与「已修复项」，不含自我验收结论；最终验收由 Codex 判定。

---

## 0. 契约/决策来源说明

契约正文与 `ccc-refactor-方案-定稿 v2` 存于 qx-map 外脑（`__archive__/decisions/`），按 T17 红线「不读写外脑」未读取。
本报告 L4 对照表基于**任务卡内联引用**（T1–T16 卡头 `契约：…（§N …）`）与 `docs/kb-seed/03-key-decisions.json`（D1–D10 决策清单）重建契约各节承诺，逐节以取证对照。
若 Codex 以 qx-map 契约正文复核发现偏差，以正文为准——本报告已注明每节承诺的推断来源。

---

## 1. 取证结果（只读）

### 1.1 提交链与工作树

- 重构区间：`201781b..HEAD`（71 commits，T0 清场至 T17 任务书）。
- 工作树：仅 2 个预存无关改动，与任务卡声明一致，未带入提交：
  - `M  .ccc/agent-mind/decided.json`（Hub 运行时数据，预存）
  - `?? _update_handoff.py`（QuantHive 一次性回写脚本，预存）
- 分支：`main`，领先 `origin/main` 129 commits（重构区间均未推送，符合「不部署不迁移」）。

### 1.2 旧代码隔离检查

| 目录 | 重构区间改动 | 判定 |
|------|--------------|------|
| `scripts/` | **0 次** | ✅ 零改动 |
| `app/` `lib/` `db/` `skills/` | 仅 T15 授权 `git mv` → `docs/archive/legacy-retired-2026-08-02/`（重命名，内容零丢失） | ✅ 授权动作 |
| `desktop/` | 仅 T16 授权 `desktop/Sources/CCCDesktop/APIClient.swift`（+148 行，壳代码） | ✅ 授权动作 |
| `server/` | 全部重构实现 | ✅ 预期 |

### 1.3 三扫描（修复后全量重跑，零命中）

扫描范围：`server/` 生产代码/模板（`.py/.sh/.plist/.env`）；排除 `tests/`（测试夹具合法值）与 `config/executors.example.json`（配置，工具名允许）。

| # | 扫描项 | 修复前 | 修复后 |
|---|--------|--------|--------|
| S1 | 绝对路径 `/Users` | 0 | 0 ✅ |
| S2 | 字面端口 `:[4-9][0-9]{3}` | 1（cluster.py:72 docstring 示例） | 0 ✅ |
| S3 | 模型名 `claude/gpt-/gemini/llama` | 0 | 0 ✅ |
| S4 | 工具名 `python3/opencode/ollama/launchd/codex/trae` | 6（web/server.py、kb/mcp_server.py、kb/__init__.py docstring 用法示例；com.ccc.router.plist 注释） | 0 ✅ |
| — | 明文密钥（password=/api_key=/token= + 字面值） | 0（唯一命中 `password = body.get("password", "")` 为读取请求体，正常逻辑） | 0 ✅ |
| — | 外脑依赖（hp_pg/qx-map/192.168） | 2（cluster.py docstring 独立性声明=合法；executors.example.json 管理席备注含 QXMAP） | 2（同上，均合法）✅ |

### 1.4 关键模块冒烟

| 模块 | 命令 | 结果 |
|------|------|------|
| Engine 缺配置退出码 | `server.engine.main --once`（缺 `--config`） | exit 2 + usage ✅ |
| Engine 配置不存在 | `--config /nonexistent` | exit 2 + `[FATAL]` ✅ |
| Engine 缺注册表 | `--config config.example.env`（占位空值） | exit 2 + 缺失键清单 + 修复后附提示 ✅ |
| Engine 有效配置 | `--config <有效> --once` | exit 0 + `{"mode":"once","scanned":0,...}` ✅ |
| KB MCP | `server.kb.mcp_server --selftest` | 索引 62 文档 · 三工具 + 空结果 · `ALL PASSED` ✅ |
| Web API 鉴权三态 | 未鉴权 401 / 错误密码 401 / 正确登录 200+token / 带 token board 200 | ✅ |
| Web API 只读接口 | /health 200（免鉴权）；board 五接口 200（带 token） | ✅ |
| Board 导出 | `server.board.export` | exported 24 cards ✅ |
| 三视图/线路图一致性 | 实时 24 = 项目 24 = 线路图 24（每卡唯一桶）；recent 6（7 天窗口） | ✅ |

### 1.5 全量测试

| 套件 | 结果 |
|------|------|
| `server/tests/`（T17 验收命令） | **171 passed · 0 failed** ✅ |
| `tests/scripts/`（旧套件，只读核查） | 1014 passed · **2 failed** · 2 skipped |

`tests/scripts` 2 个失败均为 `test_authority_patrol.py`，根因是 T0 清场（`134c647`）归档 `docs/briefs/2026-07-22-opencode-lifecycle-stall.md` 所致——**预存遗留、与本次无关**；修复需改 `scripts/` 测试，违反「scripts/ 零改动」纪律，登记遗留（见 §5）。

---

## 2. L4 对照表

> 承诺列 = 任务卡内联引用重建（注明来源）；实际列 = 本次取证；判定 ✅=一致 / ⚠️=有偏差（已修或已登记）。

### 2.1 契约 §1–§10

| 节 | 承诺（来源） | 实际取证 | 判定 |
|----|--------------|----------|------|
| §1 总则/定位 | 新服务端 `server/` 替代旧 `scripts/` 散装实现；只写骨架模板、不部署不碰运行面；旧代码互不引用零改动（T1 卡） | `server/` 独立新栈 T1–T16 完整落地；`scripts/` 重构区间 0 改动；未注册 launchd/未启动服务 | ✅ |
| §2 状态模型 | 五态 `待分派→执行中→已回写→已关闭`；失败 `→打回`（附问题清单）；非法转移报错；括号变体允许（T2/T3-R/T14-R 卡） | `engine/task.py` `State` 五态 + `_LEGAL_TRANSITIONS` + `IllegalTransitionError`（打回必附问题）；`models.base_state` 处理括号变体；测试锁定 | ✅ |
| §3 任务卡纪律 | 回写必须同步卡头「状态」元数据：接单→执行中、回写→已回写、验收→已关闭；禁止只写回写区不动状态行（T3-R/T6/T7 卡） | 24 卡全量抽查：已关闭卡均有验收记录；T1/T12/T14 打回（替换卡 T1-R/T12-R/T14-R 已关闭）；T4/T5 打回次数 1+已关闭；T17 待分派（本卡接单后转 执行中→已回写） | ✅（本卡回写同卡执行） |
| §4 看板数据模型 | 视图字段：ID/状态/项目/执行体/分派时间/回写时间/打回次数；三视图（实时/7天/项目）+ 线路图（T3/T5/T6 卡） | `board/models.py` `BoardItem` 七字段 + `queries` 三视图 + `export`；24 卡三视图/线路图一致性校验通过 | ✅ 小偏差：T8-X 无独立 `执行体` 字段 → 解析为「未知」（P2，见 §3.2） |
| §5 退役/归档纪律 | 退役清单 + 分阶段处置 + 放行条件（T12/T15 卡） | `legacy-retirement-list.md` 完整（8 目录+依赖方实测证据）；第一阶段 6/7 项完成（`relay/dist/` 待执行）；第二阶段清单含放行条件与回滚（`legacy-phase2-plan.md`） | ✅ 偏差：T15 归档 git mv 混入 T16 commit（P2 提交卫生） |
| §6 配置/部署基线 | 配置化、零硬编码、部署模板占位变量化（T1/T1-R/T4-R 卡） | `config.loader` + `config.example.env` + 部署 plist/run.sh/health.sh 全部占位变量；三扫描零命中 | ✅ |
| §7 执行体注册表 | 五角色 schema（开发执行体×2 / 维护执行体 / 管理席 / 验收席），分类∈{可后台CLI, 手动GUI, —}，version=2（T1-R 卡） | `executors.example.json` 五角色精确；`dispatch.py` 分类校验 + 派发决策；schema 测试锁定 | ✅ |
| §8 拓扑 | 壳经 HTTP 直连、多壳锁门；中转站 6100/6102 独立实例，M1 4100/4102 不动（T3/T4/T8/T13/T16 卡） | T13/T16 HTTP API（5 GET + /session + /conversation + Bearer 鉴权）；Desktop APIClient 指向配置化 + 认证；T8 双实例清单（M1 4100/4102 未动、2017 6100/6102 配置一致） | ✅ 偏差：web 前端 `?api=` 模式未适配鉴权（P1，已修） |
| §9 红线 | 杜绝硬编码；不落密钥；不碰运行面；不读写外脑（T1/T4-R 卡） | 三扫描零命中；明文密钥 0；未部署未迁移；外脑零读取 | ✅ |
| §10 验收/提交纪律 | 验收标准不可自行解释；真实提交；工作树仅剩预存项（各卡红线） | 各卡均有真实 commit；工作树仅剩 2 个预存项 | ✅ |

### 2.2 决策 D1–D10（来源：kb-seed/03-key-decisions.json）

| 决策 | 承诺 | 实际 | 判定 |
|------|------|------|------|
| D1 薄驱动 Engine + 文档流转 + 看板/HTTP 界面 | Engine 只传话记账，不评价输出质量 | `engine.main --once` 派发/收单统计；看板导出 + HTTP 查询页 | ✅ |
| D2 CCC 与 QXMAP 绝对独立（运行时零依赖） | 运行时零依赖 | `server/` 无 hp_pg/qx-map 引用；仅 executors 备注含 QXMAP（改造期对话管理描述，D7） | ✅ |
| D3 自建知识库，移植后独立运行 | 知识库独立 | `kb/` MCP + BM25（62 文档 selftest 通过） | ✅ |
| D4 定时任务由 Engine 承担 | 定时/巡检 Engine 负责 | `engine/scheduler.py`（readonly 巡检 + 变更类走卡）+ `board/scheduler.py`（定时重导出） | ✅ |
| D5 看板 = 总调度台（实时/7天/项目） | 三视图 + 集群 | 三视图 + 线路图 + 集群/运维页（app.js） | ✅ |
| D6 验收层仅安全三件套 + 基础编译/测试 | 深度验收归验收 Agent | 本卡执行全量验收，深度判定归 Codex | ✅ |
| D7 改造期 QXMAP 对话管理，Trae 执行，Codex 验收 | 过渡期分工 | 任务卡执行体记录一致（Trae 执行 / Claude Code 执行 / Codex 验收） | ✅ |
| D8 外脑治理：决策落盘强制影响声明 | 决策记录在案 | `kb-seed/03-key-decisions.json` D1–D10 | ✅ |
| D9 中转站作为 CCC 基建并入 | 自带中转站 | `deploy/upstreams.json.example`（6100/6102）+ T8 切换清单/回滚 | ✅ |
| D10 杜绝硬编码（工具/路径/地址/任务逻辑） | 零硬编码 | 三扫描零命中；⚠️ 见 §3.2 P2：`engine/cluster.py` `DEFAULT_SERVICES` 硬编码服务清单 | ⚠️ P2 |

### 2.3 M4 三门槛（退役 / 壳对接 / E2E）

| 门槛 | 承诺 | 实际 | 判定 |
|------|------|------|------|
| 退役 | 退役清单完整 + 第一阶段执行 + 第二阶段计划（放行条件未满足不执行） | 清单 8 目录完整；第一阶段 6/7 完成（`relay/dist/` 待执行）；第二阶段含 2017 引擎停止/qb 切换/老板放行条件与回滚，**未执行**（正确） | ✅ |
| 壳对接 | 服务端鉴权/对话 API + Desktop 指向配置化 + 多壳锁门 | T16 完成（鉴权三态 19 测试 + APIClient.swift 148 行）；**web 前端 `?api=` 模式此前未适配鉴权（已修）** | ✅（修后） |
| E2E | 新栈全链路：任务卡→Engine 派发→回写→export→三视图 | T14-R 证据为新栈命令输出；本次重跑 24 卡导出 + 三视图/线路图一致性通过 | ✅ |

---

## 3. 问题清单

### 3.1 P0（阻断/缺陷）

**无。** 全链路可运行、`server/tests/` 171 全绿、三扫描零命中、运行面零接触。

### 3.2 P1（应修，本次已修）

| ID | 问题 | 证据 | 修复 |
|----|------|------|------|
| P1-1 | **test_board_loader 状态断言未按基础态**（已知线索）：`test_real_dispatch_cards` 断言 `item.state in {五态+未知}`，契约 §2 允许括号变体（如 `打回（原因）`），此前已两次触发失败 | `server/tests/test_board_loader.py:97` | 断言改用 `base_state(item.state)`（与 `board/models.py` 归桶逻辑一致） |
| P1-2 | **web 前端 `?api=` 模式与 T16 鉴权不兼容**：`app.js` fetch 无 `Authorization` 头，board 接口全 401 → 静默回退本地数据，API 模式失效（多壳锁门只锁住 Desktop，未锁住 web 壳） | 实测：未带 token 请求 `/board/*` 均 401 | `index.html` 支持 `?token=` 参数；`app.js` 注入 `Authorization: Bearer <token>` 到全部 board fetch；`web/README.md` 补 API 模式鉴权说明 |
| P1-3 | **web/README.md 鉴权章节过期**：声称「本卡仅实现只读接口，未加鉴权」，与 T16 已实现（POST /session + Bearer 中间件）矛盾，误导部署 | `server/web/README.md` 原「鉴权」章节 | 更新为「鉴权（T16 已实现）」；API 表补 `/session` `/conversation` 与鉴权标注；数据源可切换节补 token 用法 |

### 3.3 P2（登记；零风险顺手修的已修，其余仅登记）

| ID | 问题 | 证据 | 处理 |
|----|------|------|------|
| P2-1 | **T15 归档 mv 混入 T16 commit `88cf04a`**：app/lib/db/skills 的 git mv 与 T16 服务端 API 同 commit，message 未提及归档 | `git show 88cf04a --stat` 含 18 个 `archive/legacy-retired-2026-08-02/` 重命名 + server/desktop 改动 | 登记不修（历史提交不重写；不影响内容/追溯，git mv 可追溯） |
| P2-2 | **`com.ccc.router.plist` 注释含 `launchd` 字面量**：T1-R 纪律「plist 注释去 launchd」未延续到 T4 新增 plist | S4 扫描命中 | 已修：注释改为「进程编排配置」 |
| P2-3 | **docstring 用法示例含 `python3` 字面量**：web/server.py、kb/mcp_server.py、kb/__init__.py 用法示例用 `python3`，与既有 docstring 惯例 `$PYTHON_BIN` 不一致且命中 S4 | S4 扫描命中 | 已修：统一为 `$PYTHON_BIN` |
| P2-4 | **cluster.py docstring 端口示例命中 S2**：`"localhost:7777,localhost:7775"` 为配置格式文档示例 | S2 扫描命中 | 已修：改为 `"localhost:PORT1,localhost:PORT2"` 占位 |
| P2-5 | **web/server.py 启动警告过期**：`serve_forever` 打印「本服务仅只读，未加鉴权」，服务已加鉴权 | `server/web/server.py` 原行 285 | 已修：文案改为「board 接口已启用 Bearer token 鉴权」 |
| P2-6 | **Engine 缺 `EXECUTOR_REGISTRY_PATH` 提示不友好**（T14-R 遗留）：缺注册表时仅报缺失键 | 实测：`required config keys are empty: … EXECUTOR_REGISTRY_PATH …` | 已修：`config/loader.py` 缺该键时附「复制 executors.example.json」提示 |
| P2-7 | **T8-X 卡无独立 `执行体` 字段**：卡头用「管理席/执行体：Claude Code」合并字段，loader 解析执行体为「未知」 | 24 卡抽查 | 登记不修（卡头格式为其自身设计，验收已过；若需统一可后续改卡头） |
| P2-8 | **executors.example.json 管理席备注含 QXMAP**：D2 独立性下为改造期对话管理描述（D7 过渡安排），非运行时依赖 | 外脑扫描命中（config 允许） | 登记不修（D7 授权描述；如需绝对干净可改文案） |
| P2-9 | **`engine/cluster.py` `DEFAULT_SERVICES` 硬编码服务清单**：服务名→进程关键词在代码内，D10 杜绝任务逻辑硬编码 | `server/engine/cluster.py:34-39` | 登记不修（只读巡检默认清单，有注释说明；建议后续改 config 驱动） |
| P2-10 | **server/ 存在 16 处 W292（无尾换行）**：预存风格债，CI ruff 仅覆盖 scripts/tests/examples 不含 server/ | `ruff check server/ --select W292` | 登记不修（非 CI 门槛、非本次引入；顺手可后续统一） |

---

## 4. 修复记录

授权范围：`server/` + `docs/`（含任务卡状态回写）。`scripts/` 零改动，运行面零接触。

| 文件 | 改动 |
|------|------|
| `server/tests/test_board_loader.py` | 断言改 `base_state`（P1-1） |
| `server/web/js/app.js` | `?token=` 注入 Bearer 头（P1-2） |
| `server/web/index.html` | 解析 `?token=` 参数（P1-2） |
| `server/web/README.md` | 鉴权章节/API 表/token 用法更新（P1-2/P1-3） |
| `server/deploy/com.ccc.router.plist` | 注释去 launchd（P2-2） |
| `server/web/server.py` | docstring `$PYTHON_BIN` + 启动警告更新（P2-3/P2-5） |
| `server/kb/mcp_server.py` | docstring `$PYTHON_BIN`（P2-3） |
| `server/kb/__init__.py` | docstring `$PYTHON_BIN`（P2-3） |
| `server/engine/cluster.py` | docstring 端口占位（P2-4） |
| `server/config/loader.py` | 缺注册表附提示（P2-6） |
| `docs/acceptance-full-2026-08-02.md` | 本报告 |
| `docs/dispatch/T17-full-acceptance.md` | 卡头状态 接单→执行中 / 回写→已回写 + 回写区（§3） |

**验证（修复后）**：
- `python3 -m pytest server/tests/ -q` → **171 passed** ✅
- 三扫描 S1–S4 全 0 命中 ✅
- 模块冒烟全过（engine 退出码 / kb selftest / web 鉴权三态 / board export 一致性）✅
- `ruff check <改动 .py>` 无新增错误（仅预存 W292）✅
- `python3 -m py_compile` / `plutil -lint` 通过 ✅

**提交**：
- 修复提交：`5a19fd6` `chore(acceptance): T17 全量验收——取证/对照/修复 + 报告`（13 文件：server 修复 + 报告 + 卡头执行中 + board.js 重导出）
- 回写提交：`docs(dispatch): T17 回写——卡头状态 + 回写区 + board.js 重导出`（T17 卡 → 已回写）

---

## 5. 遗留（未放行项与理由）

| 项 | 状态 | 理由 |
|----|------|------|
| `scripts/` 退役（第二阶段） | 未放行、未执行 | 放行条件未满足：2017 旧引擎仍运行（PID 28004 等）、qb 产线仍引用 `scripts/`、老板未放行。`legacy-phase2-plan.md` 已含完整步骤与回滚，可作后续卡直接输入 |
| `relay/dist/` 清理 | 未执行 | 第一阶段待执行项（188KB 编译产物），需确认旧 relay 彻底停止后清理 |
| `tests/scripts/test_authority_patrol.py` 2 失败 | 未修 | T0 清场归档所致预存遗留；修复需改 `scripts/` 测试，违反「scripts/ 零改动」纪律；建议退役第二阶段一并处理 |
| 2017 旧引擎停止 | 未执行 | 会停 qb 产线，须新栈接管确认 + 老板放行 |
| M1/2017 中转站双实例 | M1 4100/4102 未动 | 契约/决策要求 M1 对话面不动；2017 6100/6102 为独立实例，调用方切换（T8）待老板放行 |

---

## 6. 结论摘要（人话一句）

CCC 重构 T0–T16 全链路独立验收：无 P0；修复 3 个 P1（loader 状态断言、web API 模式鉴权适配、README 鉴权章节过期）与 6 个零风险 P2（字面量/文案/提示），`server/tests/` 171 全绿、三扫描零命中、`scripts/` 零改动、运行面零接触；遗留以退役第二阶段放行条件与预存 patrol 失败为主，均已登记。
