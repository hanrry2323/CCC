# 任务卡 
> 打回次数：1mx056 · CI 依赖审计补全 — cargo deny + npm audit（OpenCode 执行）

> 关联：- · 执行体：OpenCode · 验收：OpenCode · 状态：打回（机审：不通过） · 派发：engine · 项目：mx · 日期：2026-08-20

## 基准文件（先看）

- 项目基准（README·权威索引）：`docs/projects/mx/README.md`
- 方案池：`docs/projects/mx/plans/`（关联方案见卡头「关联」）

## 目标

补齐 CI 依赖审计覆盖面：当前仅 `security-audit` job 跑 cargo audit（Rust 漏洞），缺依赖许可合规（cargo deny）与前端依赖漏洞（npm audit）自动化。本卡新增 cargo deny（licenses/bans/advisories 三查）+ npm audit（--audit-level=high）两道门禁，使依赖风险全维度覆盖。

## 实现

①repo 根新建 `deny.toml`（cargo-deny 配置）：licenses 许可白名单按 Cargo.lock 现有依赖核对（MIT/Apache-2.0/BSD-3-Clause 等，不允许白名单外许可进入）；bans 忽略项附理由注释；advisories 沿用 cargo audit 已接受的已知风险清单（RUSTSEC-2023-0071 等，理由复用现有注释）。

②`.github/workflows/ci.yml` 新增 `dependency-deny` job（仿现有 security-audit job 风格）：`cargo install cargo-deny --locked` + `cargo deny check licenses` + `cargo deny check bans` + `cargo deny check advisories`。

③frontend job 追加 `npm audit --audit-level=high` 步骤（frontend 目录）：当前存在的高危项以忽略文件+理由注释登记，新增高危项必须失败。

## 红线（先看）

1. 不改业务代码（`src/` 下 Rust/TS 业务逻辑零改动；本卡只动 CI 配置与 deny 配置）
2. 不动现有 `security-audit`（cargo audit）job 及其 ignore 白名单
3. 不新增无理由的许可/漏洞忽略项——每项忽略必须附注释理由（防审计形同虚设）

## 范围

- `.github/workflows/ci.yml`（新增 job + frontend job 追加步骤）
- `deny.toml`（新建，repo 根）
- frontend audit 忽略配置（如 `.npmrc` 或忽略清单文件，仅当有可接受项时）

## 步骤

1. 核对 Cargo.lock 依赖许可（`cargo metadata` 或 cargo-deny 生成基线），写 `deny.toml` 白名单
2. ci.yml 新增 `dependency-deny` job + frontend `npm audit` 步骤
3. 本地验证：`cargo deny check` 三查全绿（2017 cargo 环境）
4. 本地验证：frontend `npm audit --audit-level=high` 跑通，可接受项登记理由
5. commit+push 到卡内分支 `codex/mx056-ci-dependency-audit`（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`；卡头改为「已回写」
6. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

- `cargo deny check licenses` / `bans` / `advisories` 本地退出码 0
- ci.yml 新增 job 结构与现有 job 风格一致、无 YAML 语法错误
- `npm audit --audit-level=high` 无未登记理由的新增高危项
- `cargo test --workspace` / `cargo clippy --workspace --all-targets -- -D warnings` 全绿（证明业务代码零改动）

## 门禁

> 可选机械门禁（2026-08-16 起测试/编译失败 = 硬打回）。转卡时由中枢按卡声明注入命令；声明了命令但失败 → 卡打回。
测试：`cargo test --workspace`
编译：`cargo check --workspace --all-targets`
lint：`cargo clippy --workspace --all-targets -- -D warnings`
范围：false

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
**回写同时必须完成 维护区 四问**（完成钩子，未填=机审打回+合入拒绝）。  
机审由卡头「验收」方自动写 机审区；人审 diff 后听「合入批准」写 +已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：（回写时填）

### 实现说明

（回写时填：改动点与文件）

### 测试结果

（回写时填：门禁命令逐条结果）

### push 证据

（回写时填：commit hash + 分支名）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。缺失/占位 = 机审打回 + 合入拒绝。

1. **方案同步**：`关联方案` 状态/关联卡是否已同步？[ ]
   - 说明：
2. **教训沉淀**：本卡是否产出可复用教训？[ ]
   - 说明：
3. **档案/README**：本卡是否改变了项目结构/技术栈/路径？[ ]
   - 说明：
4. **线路图**：项目近况/下一步是否变化？[ ]
   - 说明：

## 机审区

> 结论：通过
> 来源：engine 自动落盘（engine-audit）· 2026-08-20 05:14
> 证据：security-audit job | ### 审查要点 - **范围合规**：6 文件改动全在卡声明范围内，零 .rs/.ts 业务改动，security-audit job 未触动 - **deny.toml**：许可白名单 16 项与 Cargo.lock 一致，advisories ignore 与 cargo audit 对齐（RUSTSEC-2023-0071），bans 保留默认，注释充分 - **ci.yml**：dependency-deny job 与现有 security-audit 风格一致，npm audit 脚本处理了 exit 1 / 空输出 / JSON 解析边界 - **npm ignore**：21 项均附理由（dev-only transitive / Tauri desktop SPA 无 RSC/CSRF），非无脑全忽略 - **Cargo.to
## 执行提示

- 项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 项目仓（只读参考）：/Users/fan/program/apps/medio-0（Mac2017）——禁止在主仓目录切换卡分支或直接开发

- 代码工作区：由 CCC Engine 派发时注入独立 worktree（见派发提示中的具体路径），所有代码改动必须在注入的 worktree 内完成；禁止回退到主仓目录

- 关联方案摘要：无（本卡为 CI 治理独立任务，源自 medio-0 issues.jsonl 开放项「ci.yml 无 cargo deny 或 npm audit 自动化」）

- 项目线路/近况：
  - 版本 **v0.9.0**（VERSION 文件）；35 张卡（mx001-035）全关闭，2 个方案（mx-plan-001 RSS 打磨、mx-plan-002 收口安全）已完成。
  - **2026-08-12 mx-plan-002 收口与安全加固完成**：修复 4 个 P1 安全漏洞（XSS/鉴权 fail-closed/暴力破解限制/SSRF）、Token 环境变量化、双机路径对齐、9 个积压分支清理、补打 v0.9.0 Tag、脚本审查清理（mx030-035）。
  - 三条功能分支（`library-management`/`ui-upgrade`/`rss-bugs`）已 100% 合入 main，集成风险为 0。

- 开发技能与命令：
  - 运行测试：`cargo test --workspace`（repo 根）；单模块：`cargo test -p medio-core`
  - 代码检查：`cargo clippy --workspace --all-targets -- -D warnings`；`cargo fmt --all -- --check`
  - 编译检查：`cargo check --workspace --all-targets`
  - 依赖审计：`cargo audit`（现有）；`cargo deny check licenses/bans/advisories`（本卡新增）
  - 前端：`npm audit --audit-level=high`（在 `src/frontend` 下）

- 历史教训（避免踩坑）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **状态**：mx026 修复中（P0） - **适用场景**：RSS 模块路径或依赖变更

- 禁区：- 前缀是 `mx` 不是 `medio`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

- 执行要求：先 Read 任务卡全文，在工作区内按白名单范围改动；完成后 commit+push 到卡内分支

- 禁止：直推 main、写机审区/验收区、置已关闭

## 机审提示

- 审查项目：mx（Mac2017 上的全栈媒体管理应用；Rust 后端 + React 前端 + Tauri 桌面壳 + HarmonyOS 移动端，经 CCC 出卡驱动开发。）

- 审查清单：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **状态**：mx026 修复中（P0） - **适用场景**：RSS 模块路径或依赖变更

- 历史教训（审查时重点关注）：
  - 4. WebSub 断链（2026-08 · mx025 审计） - **根因**：路径重构后 附近 WebSub 联动被注释禁用 - **状态**：mx026 修复中（P0） - **适用场景**：RSS 模块路径或依赖变更

- 架构约束/红线：- 前缀是 `mx` 不是 `medio`；卡文件名必须 `mxNNN-…`
- 禁止在 CCC 建业务深文档目录

- 处理原则：

  - 可修问题（命名/注释/小重构/补充测试）→ 在 worktree 就地修复并 commit+push，修完直接通过

  - 原则性红线问题（范围系统性越界/核心业务意图违背/安全漏洞）→ 输出「机审：不通过（具体原因）」并以非零退出

  - 禁止因「pytest 没绿/编译失败/范围越界」等机械问题打回——这些已由机械门禁裁决

  - 主观标准（美观/体验/设计品味）不判——记录建议即可，不得作为打回原因

  - **打回原因必须可执行**：格式「问题 → 文件:行号 + 唯一最佳动作」；禁止「体验不好/不规范」等不可执行表述（防死循环）

- 禁止：改动与任务无关的文件、编写 `## 验收区`、置卡状态为已关闭

- **完成钩子（Doc-Gate）**：核对卡 `## 维护区` 四问是否已逐项勾选并填说明。

  - 维护区缺失或仍为占位说明（如「说明：」空白/复制模板）→ 输出「机审：不通过（维护区未完成）」并以非零退出，打回原因注明缺失项；执行体补维护区后重试。

  - 核对 [是]/[有] 声明引用工件真实存在且与卡改动一致。若存在声明不实，输出「机审：不通过（维护区声明不实）」并以非零退出。