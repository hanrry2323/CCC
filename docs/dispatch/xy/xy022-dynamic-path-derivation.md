# 任务卡 xy022 · 遗留治理①：硬编码路径动态推导（P0-PATH 深化）（OpenCode 执行）

> 关联：ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-08

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

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
