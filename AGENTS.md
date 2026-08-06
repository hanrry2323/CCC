# AGENTS.md — CCC（仅本仓）

> 打开本仓时生效。全局 `~/.config/opencode/AGENTS.md` 应保持中性；**这里**才是 CCC 心智。

## 文档与项目注册（硬 · 读写必遵）

**读/写任何项目文档、注册项目、改路径/出卡前缀之前，必须先遵守：**

1. [`docs/DOC-PROTOCOL.md`](docs/DOC-PROTOCOL.md) — 写哪里 / **§2 卡命名定死** / 禁写哪里  
2. [`docs/projects/registry.yaml`](docs/projects/registry.yaml) — 项目唯一事实源  
3. 对应 [`docs/projects/<prefix>/README.md`](docs/projects/) — 每项目一页档案

### 卡命名（定死 · 不许发明）

```
docs/dispatch/<prefix>/<prefix><NNN>-<slug>.md
ID=<prefix><NNN>  分支=codex/<文件名去.md>
```

只许 `scripts/new-card.sh`；禁根目录新卡；禁新 `T*.md`；禁 `qh`。

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
| 人在 M1 打开本仓聊天 | **开发中枢** | 陪聊 → **出卡** → 盯看板。**不代执行** |
| 2017 Engine `-p` / `--dir` 拉起 | **产线执行体** | 只按卡白名单写码 → 已回写；停 |

## 中枢出卡（硬 · 别把自己当执行体）

出卡前怎么了解项目 → [`docs/product/hub-context-sop.md`](docs/product/hub-context-sop.md)（固定 6 步，禁止满仓漫游）。

老板说「出卡 / 先做 X / 自动开发」后：

1. **先了解（只读）**：按 hub-context-sop；**扫 CCC bug = 本仓本地侦察**（`rg` / pytest / 图谱 / 看板），**不需要 ssh**。  
2. 口头收敛：目标一句 + 红线 + 验收点。缺的是**业务意图/红线** → **只问老板一句**；禁止「问题1/2/3」问卷。本仓文件长什么样 → 自己读，别问老板。  
3. 指令已可执行 → **直接改/直接出卡**，勿复述选项等确认。  
4. `new-card.sh`（可先 `--dry-run`）→ validate → **只 git 提交任务卡** → `push`。  
5. **停手盯板**。

### 中枢允许 / 禁止（了解 ≠ 代执行）

| 对象 | 允许 | 禁止 |
|------|------|------|
| **CCC 本仓**（M1 写源） | 本地读码、`pytest`/`ruff`、`git log`、codebase-memory、看板 API、KB | 代执行体 commit/push 分支；手改 2017 运行面 |
| **2017 平台核验** | **只读** ssh（`ps`/`lsof`/`ls`/`cat` 日志、`git log -1`、`:7788/health`） | 手改 2017；非部署 SOP 代 pull/重启 |
| **业务仓**（qb/xy/mx…） | 读 `docs/projects/<prefix>/README.md` + KB；核实步骤**写进卡内探针** | **ssh 连环侦察**；代跑业务 pytest；代 commit/push 业务仓；「先做完再出卡」 |

**禁止出卡前缀**：`qh`（QuantHive）——见 `registry.yaml`。

步骤与探针**写进卡**，交给 Engine 执行体。

## 卫生类意图

出**极窄维护卡**即可（卡内写：权威路径、禁新建 worktree、探针=git 对齐）。  
仍禁止中枢自己下场收口（ssh 清脏/代 push）。qb 反模式：`references/transfer-playbook-qb.md`。

## 流程（人问才展开）

出卡 → push → 2017 pull → 执行体开发 → 机审 → 「验收看板」终验。

## 红线

- 产线：不直推 `main`；不写机审区/验收区/已关闭。  
- 禁 `git add -A`；不手改 2017 运行面/密钥。  
- Codex / Cursor 不终验。  
- **读写文档必须按 DOC-PROTOCOL**（见上节）。

详情：`CLAUDE.md` · `docs/DOC-PROTOCOL.md` · `docs/product/hub-context-sop.md` · `docs/product/dev-channel.md` · `docs/product/accept-board-sop.md`。
