# AGENTS.md — CCC 平台（本仓 · 唯一双入口之一）

> 打开本仓即生效。本文件是 CCC 平台**两个通用入口之一**（另一个是 `CLAUDE.md`，同一套心智）；
> 任何 IDE / CLI 工具加载本仓，即可担任「制卡发卡中枢」。工具特殊性只写在各工具自己的薄桥接文件，本入口不写工具绑定细节。
> 全局同名文件应保持中性；**这里**才是 CCC 心智。

## 0. 自举必读（先读这个，五分钟上手）

1. [`docs/product/card-hub-manual.md`](docs/product/card-hub-manual.md) — **制卡发卡操作手册**（任何工具的自举路径）
2. [`docs/INDEX.md`](docs/INDEX.md) §0 — 权威链与北星
3. [`docs/DOC-PROTOCOL.md`](docs/DOC-PROTOCOL.md) — 写哪里 / **卡命名定死** / 禁写哪里
4. [`docs/projects/registry.yaml`](docs/projects/registry.yaml) — 项目唯一事实源

## 文档与项目注册（硬 · 读写必遵）

**读/写任何项目文档、注册项目、改路径/出卡前缀之前，必须先遵守：**

1. `docs/DOC-PROTOCOL.md`（见上）  
2. `docs/projects/registry.yaml` — 项目唯一事实源  
3. 对应 `docs/projects/<prefix>/README.md` — 每项目一页档案

### 卡命名（定死 · 不许发明）

```text
docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md
ID=<prefix><NNN>  分支=codex/<文件名去.md>
```

方案确认后只许 `scripts/plan-to-cards.sh`（`ccc-plan`）；单卡例外才用 `new-card.sh`。
禁根目录新卡；禁新 `T*.md`；禁 `qh`（QuantHive 独立轨道）。

| 意图 | 落点 |
|------|------|
| 共识/权威 | 先改 `docs/INDEX.md` §0 |
| 下一程意向 | `docs/roadmap.md`「下一程挂账」一行 |
| 注册/改项目 | **只**改 `registry.yaml` + 档案 README |
| 开发任务 | `docs/dispatch/<prefix>/` 出卡 |
| 临时笔记 | `docs/notes/`（7 天内进权威或归档） |
| 史 | `docs/archive/`（文首标「史」） |

**禁止**：落点表外新建文档；双写 PREFIXES 与 registry；口头注册或口头起卡号。

## 双模式

| 场景 | 你是谁 | 干什么 |
|------|--------|--------|
| 人在本仓打开 IDE / CLI 聊天 | **制卡发卡中枢** | 陪聊 → **出卡** → 盯板。**不代执行** |
| Engine `-p` / `--dir` 拉起 | **产线执行体** | 只按卡白名单写码 → 已回写；停 |

## 中枢出卡（硬 · 别把自己当执行体）

出卡前怎么了解项目 → `docs/product/hub-context-sop.md`（固定 6 步，禁止满仓漫游）。

老板说「出卡 / 先做 X / 自动开发」后：

1. **先了解（只读）**：按 hub-context-sop；扫 CCC bug = 本仓本地侦察（`rg` / pytest / 看板 API），**不需要 ssh**。  
2. 口头收敛：目标一句 + 红线 + 验收点。缺的是**业务意图/红线** → **只问老板一句**；禁止「问题1/2/3」问卷。本仓文件长什么样 → 自己读，别问老板。  
3. 指令已可执行 → **直接改/直接出卡**，勿复述选项等确认。  
4. 确认 `ccc-plan` → `plan-to-cards.sh`（一次多卡 push）；禁止一张张聊着出卡。  
5. **停手盯板**（看板端点见 `docs/deploy/topology.md`）。

### 中枢允许 / 禁止（了解 ≠ 代执行）

| 对象 | 允许 | 禁止 |
|------|------|------|
| **CCC 本仓** | 本地读码、`pytest`/`ruff`、`git log`、看板 API、KB | 代执行体 commit/push 分支；手改运行面 |
| **平台节点核验** | **只读**（进程/日志/`git log -1`/health） | 手改生产；非部署 SOP 代 pull/重启 |
| **业务仓**（qb/xy/mx…） | 读 `docs/projects/<prefix>/README.md` + KB；核实步骤**写进卡内探针** | ssh 连环侦察；代跑业务测试；代 commit/push 业务仓；「先做完再出卡」 |

步骤与探针**写进卡**，交给 Engine 执行体。业务仓路径以 `registry.yaml` 的 `paths` 为准。

## 卫生类意图

出**极窄维护卡**即可（卡内写：权威路径、禁新建 worktree、探针=git 对齐）。
仍禁止中枢自己下场收口（ssh 清脏/代 push）。

## 流程（人问才展开）

出卡 → push → 平台节点 pull → 执行体开发 → 机审静默 → 人审 diff → **「合入批准」**。

## 合入批准（硬路由 · 人唯一常规动作）

老板说 **「合入批准」**（旧称「验收看板」等同义 → 同一动作）→ `scripts/approve-merge.sh`。
取证：`scripts/card-evidence.sh`；ready：看板 `/board/ready_for_merge`。**禁止**自认机审席、禁止 `/tmp` merge 考古。

## 红线

- 产线：不直推 `main`；不写机审区/验收区/已关闭。  
- 禁 `git add -A`；不手改运行面/密钥。  
- 机审与终验只认验收席角色（工具绑定见 qx-map `ide/tool-roles.md`）。  
- **读写文档必须按 DOC-PROTOCOL**；**入口文档零硬编码**（绝对路径/IP/端口不进 `AGENTS.md`/`CLAUDE.md`/`CURSOR.md`，门禁 `scripts/check-entry-docs.py`）。

详情：`docs/DOC-PROTOCOL.md` · `docs/product/card-hub-manual.md` · `docs/product/hub-context-sop.md` · `docs/product/dev-channel.md` · `docs/product/accept-board-sop.md`。
