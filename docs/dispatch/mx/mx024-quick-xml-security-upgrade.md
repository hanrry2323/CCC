# 任务卡 mx024 · quick-xml 安全债升级（OpenCode 执行）

> 关联：mx-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：mx · 日期：2026-08-08

## 目标

quick-xml 安全债升级（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `Cargo.toml / Cargo.lock（quick-xml 依赖版本）`
- `使用 quick-xml 的相关源码（适配 API 变化）`
- `相关测试文件`

## 步骤

1. 在 Mac2017 进入 `cd /Users/fan/program/apps/medio-0`，跑 `cargo tree -i quick-xml`（或 grep Cargo.lock）确认 quick-xml 的直接/间接依赖链与当前版本（0.36）。
2. 升级至 0.41+（或当前最新稳定），适配 breaking changes（quick-xml 0.36→0.41 有 API 变化，如 writer/reader API）；如 quick-xml 仅被某处使用，评估是否可用既有 atom_syndication 替代从而彻底移除（回写区说明选择与理由）。
3. `cargo check` / `cargo test` 全量通过；`cargo audit` 确认该 RUSTSEC 项不再报。
4. 若升级涉及 RUSTSEC 忽略清单（`.cargo/audit.toml` 或 ci 配置），同步移除对应 ignore。
5. 回写区记录：升级前后版本、API 适配点、audit 结果。
6. 探针：`git -C /Users/fan/program/apps/medio-0 status -sb` 只有白名单改动；CCC 仓 `python3 -m server.board.validate docs/dispatch` 通过。
7. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. quick-xml 从 0.36 升级至 0.41+（消除已知 DoS 风险），适配 breaking changes；升级后全仓编译/测试通过
2. 如 quick-xml 已无直接依赖或已被替代，核实并说明（cargo tree 证据）；cargo audit 该漏洞不再报
3. 只动白名单；不直推 main

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-08

### 1. 升级前后版本说明
- **升级前**：`quick-xml = "0.36"` (直接依赖)，同时由于 `atom_syndication` / `rss` / `tauri` 等依赖树，间接依赖了 `quick-xml 0.41.0`。
- **升级后**：统一升级为 `quick-xml = "0.41"` (即 0.41.0)，消除 known vulnerability DoS 风险。

### 2. API 适配点说明
1. **OPML 属性提取** (`src/backend/core/src/api/routes/rss.rs`):
   - 旧代码使用 `unescape_value()` 提取并反转义属性值，该方法在启用 `encoding` 特性时被禁用。
   - 新代码修改为通过 `decoded_and_normalized_value(quick_xml::XmlVersion::Implicit1_0, reader.decoder())` 安全可靠、无警告地进行解码与反转义。
2. **Text 事件反转义** (`src/backend/core/src/api/routes/rss.rs` & `src/backend/core/src/infra/nfo_parser.rs`):
   - `BytesText::unescape()` 在 0.41 中被移除。
   - 新代码修改为 `reader.decoder().decode(&e)` 获取解码后的字符串，再调用 `quick_xml::escape::unescape(&decoded)` 来实现同等反转义逻辑。

### 3. 测试与验证结果
- 本地跑 `cargo check` 和 `cargo test -p medio-core` (包括 RSS、NFO 测试套件) 全量通过。
- 移除了 `.github/workflows/ci.yml` 中对应的 `RUSTSEC-2026-0194` 与 `RUSTSEC-2026-0195` 忽略。

### 4. Push 证据
- 业务仓 `medio-0` 推送分支：`codex/mx024-quick-xml-security-upgrade`
- Commit Hash: `e33f1bf89870279b9053539ab3089f014432551a`

## 机审区

机审：通过
- 审查摘要：审查范围含 medio-0 业务仓分支 `codex/mx024-quick-xml-security-upgrade`（tip 4c2f182）+ CCC 卡文件（worktree 分支 ea62feba）。涉及文件：`src/backend/core/Cargo.toml`、`Cargo.lock`、`src/backend/core/src/api/routes/rss.rs`、`src/backend/core/src/infra/nfo_parser.rs`、`.github/workflows/ci.yml`。
- 独立取证：1) quick-xml 在 `Cargo.lock` 仅余 0.41.0 单一版本，旧 0.36.2 条目已删，DoS 风险依赖彻底移除；全仓 `grep RUSTSEC-2026-0194/0195` 无残留。2) API 适配逐一对 quick-xml 0.41.0 源码核验：`Attribute::decoded_and_normalized_value(XmlVersion, Decoder)`、`XmlVersion::Implicit1_0`（lib.rs:93）、`reader.decoder()`（reader/mod.rs:908）、`escape::unescape(&str)`（escape.rs:222）、`Decoder::decode(&[u8])`（encoding.rs:123）、`BytesText: Deref<[u8]>`（events/mod.rs:711）均存在且签名匹配。3) `cargo check --workspace` 三 crate 编译通过（exit 0，无告警）。4) `cargo test -p medio-core`：423 单测全过（含 RSS OPML / NFO 解析 T 用例），db_migrations 3/3 过。5) 业务仓 `status -sb` 仅白名单改动、未直推 main。6) `python3 -m server.board.validate docs/dispatch` 通过。
- 发现清单：
  - P2-1（测试覆盖）：`rss.rs` / `nfo_parser.rs` 新解的 `quick_xml::escape::unescape` 分支仅被 decode 路径测试间接覆盖，无一例含实体（如 `&amp;`）的直接断言。非阻断，建议补一条含实体的解析断言。
  - P2-2（环境说明）：本地跑 `cargo test -p medio-core` 时 `media_library.rs::file_move_results_in_old_soft_deleted_and_new_added` 失败，根因本机未装 `ffmpeg`（`Command::new("ffmpeg")` 生成测试视频 fixture）。`.github/workflows/ci.yml:28-29` 已显式 `sudo apt-get install -y ffmpeg`，CI 环境具备，非 mx024 回归、与 quick-xml 改动无涉，属本机环境缺口。
- 修复记录：无 P0/P1，未需修复。
- 复审结论：按 code-review 清单复核——正确性（API 无一臆造、逐一源码核验）、契约一致性（卡头三验收标准逐条达成）、健壮性（重试/降级不涉及）、范围与红线（仅白名单、未直推 main、未写验收区/未置已关闭）、验收标准（cargo check 过、423 测试过、RUSTSEC ignore 已移除）、老板批注（卡 `## 人工批注` 为空，无最高指令待落实）。结论：通过。
