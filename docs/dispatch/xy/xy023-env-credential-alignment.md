# 任务卡 xy023 · 遗留治理②：凭据补全与 .env.example 对齐（P0-CRED）（OpenCode 执行）

> 关联：ccc-plan: xy PRM 批1：硬编码旧规则消灭 / 动态推导 / 凭据补全 · 执行体：OpenCode · 验收：OpenCode · 状态：已关闭· 派发：engine · 项目：xy · 日期：2026-08-08

## 目标

遗留治理②：凭据补全与 .env.example 对齐（P0-CRED）（ccc-plan 切片）。

## 红线（先看）

1. （本卡禁止触碰的边界，验收越界即打回）
2. 若本卡含 `## 人工批注`，执行体必须先读批注并按批注修订目标/步骤后再执行；批注优先于正文。

## 范围

- `.env.example`
- `docs/**/*.md`
- `.ccc/decision.md`

## 步骤

1. （可执行步骤，每步有可验证产物）
2. commit+push 到卡内分支（勿直推 main）；合入前 `git fetch origin && git rebase origin/main`（减 --close-only）；卡头改为「已回写」。
3. **停手**：禁止写 `## 机审区` / `## 验收区` / 置「已关闭」。等 2017 机审 → 老板「合入批准」。

## 验收标准

1. .env.example 补齐代码引用的缺失变量：SAU_API_KEY、SAU_BACKEND_URL、XIAN_E2E、XIANYU_FONT、XIANYU_FONT_DIR、XIANYU_FONTS_DIR、E2E_ROUNDS、OLLAMA_FALLBACK_MODEL、COOKIE_FILE、DRY_RUN（每项含注释说明用途与来源）
2. Settings 内部 27 项参数（发布限频 publish_daily_limit_*、熔断 cb_*、动态码率 dynamic_bitrate_*、智能封面 thumbnail_*、磁盘监控 disk_*_pct、日志 log_total_max_mb 等）在 .env.example 补齐占位与注解
3. grep 比对验证：代码引用的 os.environ.get/os.getenv 变量名集合 ⊆ .env.example 定义集合，遗漏为 0，比对脚本或命令写入回写区
4. PEXELS_API_KEY 相关：确认 .env.local 已配置（xy019 已做），本次只补 .env.example 占位不写真实 key
5. 改动仅限 .env.example 与文档，不改业务逻辑；回写区列全变量清单

## 回写要求

卡头状态更新为「已回写」；回写区填：实现说明、测试结果、push 证据（commit hash）。  
机审由卡头「验收」方自动写 `## 机审区`；人审 diff 后听「合入批准」写 `## 验收区`+已关闭。

## 人工批注

（老板对打回卡/审核的批注意见写这里；执行体先读批注再执行。无批注时保留本节即可。）

## 回写区

**执行体**：OpenCode · 日期：

## 批注落实

（若卡含 `## 人工批注`，这里填写批注如何落实——老板批注是最高开发指令，未落实=机审不通过；无批注可删本节。）
