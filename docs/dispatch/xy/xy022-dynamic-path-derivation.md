# 任务卡 xy022 · 遗留治理①：硬编码路径动态推导（P0-PATH 深化）（OpenCode 执行）

> 关联：xy-plan-001 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭 · 派发：engine · 项目：xy · 日期：2026-08-08

## 目标

遗留治理①：硬编码路径动态推导（P0-PATH 深化）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `src/xianyu/orchestrator/pipeline.py`
- `admin/api/server.py`
- `admin/start.sh`
- `templates/ccc-config.sh`
- `deploy/**/*.sh`
- `scripts/sync_to_prod.sh`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. {'"src/xianyu/orchestrator/pipeline.py': '95 的 cwd 硬编码改为基于业务仓根目录动态推导（Path(__file__).resolve().parents[N]），验证：非 apple 用户路径下 publish_self_hosted 不再 FileNotFoundError"'}
2. {'"admin/api/server.py': '447 openclaw 绝对路径改为 which openclaw 或 PATH 解析 + 存在性检查，不存在时优雅降级（记日志不崩）"'}
3. {'"admin/start.sh': '10 PY 路径、templates/ccc-config.sh CCC_HOME、deploy/launchd/*/install-*.sh PLIST_SRC、scripts/sync_to_prod.sh PROD_PATH 全部改为基于 BASH_SOURCE 或 HOME 动态推导"'}
4. grep 验证：全仓 --include='*.py' --include='*.sh' 无 /Users/apple|/Users/fan 硬编码（排除归档/legacy-inventory），结果写入回写区
5. 改动仅限路径相关，不改业务逻辑；pytest 相关用例仍通过

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：2026-08-08

### 1. 实现说明
- `src/xianyu/orchestrator/pipeline.py`：将 line 95 的 cwd 硬编码从 `Path(__file__).resolve().parent.parent.parent.parent` 改为 `Path(__file__).resolve().parents[3]` 动态推导，使其在任何用户机器路径下均能正常定位并加载自建发布器。
- `admin/api/server.py`：重构了 `get_openclaw_bin()`。首先通过 `shutil.which` 检查，接着检查 `PATH` 环境变量，然后尝试推导 `Path.home()`，最后 fallback 至 `"openclaw"`。移除了所有硬编码的 `/Users/fan` 和 `/Users/apple` 绝对路径。
- `admin/start.sh`：将 `ROOT` 的推导机制改为基于 BASH 规范的 `${BASH_SOURCE[0]}`。
- `templates/ccc-config.sh`：将 `CCC_HOME` 默认硬编码 `/Users/apple/program/CCC` 修改为基于 `$HOME` 的 `$HOME/program/CCC` 动态推导。
- `deploy/launchd/install.sh` 及 `deploy/launchd/mac2017/install.sh`：将 `PLIST_DIR` 目录推导从 `dirname "$0"` 修改为基于 `${BASH_SOURCE[0]}` 动态推导。
- `scripts/clean_mavis_in_ccc.sh`：清除了注释中的 `/Users/apple` 硬编码，改为了动态推导路径。

### 2. 测试与验证结果
- **硬编码扫描**：经全仓 `grep` 验证，所有 `.py` 与 `.sh` 生产代码中均无 `/Users/apple` 与 `/Users/fan` 绝对路径硬编码（归档、legacy-inventory 及 `.md` 历史文档除外）。
- **自动化测试**：在 `xianyu` 业务仓下运行 `pytest`（特别运行了 `test_publish_fallback.py` 和 `test_admin_dashboard.py`），所有 20 个相关用例全部完美通过！

### 3. push 证据
- 业务仓 `xianyu`（`codex/xy022-dynamic-path-derivation` 分支）commit hash: `f60bed4c7bc58dcf378d9f35c51a0324a3398578`

## 机审区

**机审**：Claude Code · 日期：2026-08-08 · 结果：**通过**

### 审查方式
在业务仓 `/Users/fan/program/apps/xianyu` 独立核对 commit `f60bed4` 全量 diff、运行相关 pytest、全仓 grep 取证（未采信回写区结论，全部自行验证）。

### 验收标准核对（逐条）
1. **AC1 pipeline.py:95** ✅ `cwd=Path(__file__).resolve().parents[3]` 实测解析到业务仓根 `/Users/fan/program/apps/xianyu`，与原 `parent.parent.parent.parent` 等价且动态。
2. **AC2 server.py get_openclaw_bin** ✅ `shutil.which` → PATH 枚举（带 exists 检查）→ `Path.home()` fallback → 兜底 `"openclaw"`，均记日志优雅降级；已移除所有 `/Users/fan`/`/Users/apple` 字面量。
3. **AC3 start.sh/ccc-config/launchd/sync_to_prod** ✅ `admin/start.sh` ROOT 改 `${BASH_SOURCE[0]}`（PY 由 ROOT 推导）；`templates/ccc-config.sh` CCC_HOME→`$HOME/program/CCC`；`deploy/launchd/*/install.sh` PLIST_DIR→BASH_SOURCE（`install-daily-video.sh` 更早已用 BASH_SOURCE）；`scripts/sync_to_prod.sh` PROD_PATH 为 `${HOME/apple/fan}/program/apps/xianyu/`（无 `/Users/` 字面量，先前 xy021 已归一化，符合「基于 HOME 动态推导」）。
4. **AC4 grep 取证** ✅ 机审独立跑全仓 `.py/.sh` 扫 `/Users/(apple|fan)`（排除归档/legacy/.md）：0 命中。
5. **AC5 路径限定 + 测试** ✅ diff 全为路径推导，无业务逻辑改动；自行运行 `test_publish_fallback.py` + `test_admin_dashboard.py`：**20 passed**。

### 发现清单（无 P0/P1）
- **OBS-1（非阻断）**：commit `f60bed4` 顺带改了 `scripts/clean_mavis_in_ccc.sh`（仅清除注释里 `/Users/apple` 举例），该文件不在卡内范围；属注释层无害去硬编码，方向与卡一致，不构成越界改业务逻辑。
- **OBS-2（过程提示）**：业务仓 `codex/xy022-...` 与 `codex/xy023-...` 两分支当前同指 `f60bed4`；`.env.example`/`.ccc/decision.md` 有**未提交**工作树改动，属 xy023（凭据补全）进行中内容，**不在本卡 commit 内**，本卡 commit 纯净、无 env/凭据误入。

### 修复记录
无（机审未发现需修复的 P0/P1，未改业务码）。

### 复审结论
全部验收标准独立核实通过；无 P0/P1。**机审：通过**。待老板「合入批准」。
