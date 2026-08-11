# 方案 · medio-0 收口与安全加固（v0.9.0 → v0.10.0）

> 项目：mx · 编号：mx-plan-002 · 状态：部分执行 · 作者：OpenCode 中枢 · 工具：opencode
> 创建：2026-08-12 · 更新：2026-08-12
> 关联卡：mx030-mx034（出卡后回填）, mx035
> 关联方案：mx-plan-001（已完结）

## 目标

把 2026-08-11 深度探查（Claude Code 探针）发现的三类债务一次收口：安全（10 个 open issue + token 硬编码）、文档脱节（4 处版本/路径矛盾）、工程积压（9 个未合并分支 + 异常脚本），为下一阶段功能开发铺干净地基。执行机：Mac2017，代码根 `/Users/fan/program/apps/medio-0`。

## 背景

- v0.9.0 代码质量高（零 TODO/FIXME/HACK，Rust ~21K 行 + 前端 ~25K 行），但存在债务：
  - **安全**：`config-test.toml` 明文 token 入库；issues.jsonl 有 10 个 open（含 4 个 P1：RSS dangerouslySetInnerHTML XSS、POST 鉴权白名单脆性、认证端点无暴力破解防护、远程图片下载无超时/重试 SSRF）；鸿蒙签名证书 `.p7b.pem` 曾推 4 个远端分支（独立敏感流程，本方案只挂账）。
  - **文档**：AGENTS.md 路径指向废弃 M1 路径（CLAUDE.md 已声明 2017 权威）；SECURITY_AUDIT.md 停在 v0.3.1；ARCHITECTURE.md 缺 Harmony 端；根 package.json v0.5.1 ≠ VERSION v0.9.0；README 引用可能不存在的 GitHub Releases/deploy-package README。
  - **工程**：9 个未合并分支（mx006/010/011/012/024/026/027/028/029），4 个旧命名分支无 `codex/` 前缀；`scripts/delete_videos.sh` 644KB 异常大待审查；≥9 个个人运维脚本与项目核心无关；tag 缺 v0.9.0。

## 方案内容

五张卡顺序推进（收口为主，无新功能）：

1. **安全 P1 修复**：RSS 渲染 XSS 改造（去 dangerouslySetInnerHTML）、POST 鉴权白名单 fail-closed、认证暴力破解防护、远程图片下载超时/重试/大小上限。
2. **敏感信息清理**：config-test.toml token 环境变量化；git 历史敏感痕迹复核出结论。
3. **文档版本对齐**：修正 4 处脱节点 + README 外部引用核对。
4. **分支收口**：9 个分支逐个审（功能完整性 + 测试 + 与 main 差异）→ 合入或关闭；旧命名分支规范化；补打 v0.9.0 tag。
5. **脚本审查清理**：delete_videos.sh 644KB 内容审查与敏感路径排查；个人运维脚本迁出仓，scripts/ 仅留项目核心。

**独立挂账（不进自动流程）**：鸿蒙证书泄露处置——换证 + git filter-repo 历史清洗，涉及密钥与远端重写，老板确认后独立执行。

## 验收标准

- [ ] 10 个 open 安全 issue 的 4 个 P1 项全部关闭，issues.jsonl 更新
- [ ] 文档脱节点清零：AGENTS.md/CLAUDE.md 双机路径唯一权威，SECURITY_AUDIT 对齐 v0.9.0，ARCHITECTURE 覆盖 Harmony，package.json 与 VERSION 一致
- [ ] 分支积压清零（9 分支各有合入或关闭结论），tag 补打 v0.9.0
- [ ] 脚本审查有结论：delete_videos.sh 内容分类与敏感排查记录，scripts/ 仅留项目核心脚本
- [ ] 全仓回归：cargo test + 前端 vitest + pytest 全绿，ruff/clippy/eslint 干净

## 转卡计划

```ccc-plan
title: medio-0 收口与安全加固（v0.9.0 → v0.10.0）
project: mx
slices:
  - title: 安全 P1 修复（XSS/鉴权白名单/暴力破解/SSRF）
    slug: security-p1-fixes
    acceptance:
      - RSS 渲染移除 dangerouslySetInnerHTML（改白名单过滤组件），script 标签注入用例通过前端测试
      - POST 鉴权白名单 fail-closed：未注册端点默认拒绝，新增端点注册集中管理，测试覆盖
      - 认证端点有暴力破解防护（速率限制/退避/锁定），pytest 覆盖连续失败场景
      - 远程图片下载增加超时、重试与大小上限，SSRF 防护用例通过
      - issues.jsonl 中 4 个 P1 项更新为 closed，全仓回归（cargo test + vitest + pytest）绿
    whitelist:
      - src/backend/core/src/
      - src/frontend/src/
      - tests/
      - issues.jsonl
  - title: 敏感信息清理（token 环境变量化 + 历史痕迹复核）
    slug: sensitive-info-cleanup
    acceptance:
      - config-test.toml 的 admin_token 改为环境变量注入，git grep 无明文残留
      - git log -S token/password 复核结论写入 docs/security/，明确剩余风险清单
      - 全仓回归绿
    whitelist:
      - config-test.toml
      - tests/
      - docs/security/
  - title: 文档版本对齐（路径/审计/架构/版本号）
    slug: doc-alignment
    acceptance:
      - AGENTS.md 项目路径修正为 /Users/fan/program/apps/medio-0，与 CLAUDE.md 声明一致
      - SECURITY_AUDIT.md 更新至 v0.9.0，漏洞清单与 issues.jsonl 对齐
      - ARCHITECTURE.md 补充 Harmony 端交付形态与目录结构
      - 根 package.json version 与 VERSION 文件一致（v0.9.0）
      - README.md 外部引用核对（GitHub Releases 链接、deploy-package/README.md），无效引用修正或移除
    whitelist:
      - AGENTS.md
      - CLAUDE.md
      - README.md
      - ARCHITECTURE.md
      - SECURITY_AUDIT.md
      - package.json
      - docs/
  - title: 分支收口（未合并分支审查合入 + tag 补打）
    slug: branch-consolidation
    acceptance:
      - 9 个未合并分支（mx006/010/011/012/024/026/027/028/029）逐个审查：功能完整性 + 测试 + 与 main 差异，合入 main 或关闭归档，结论记录
      - 旧命名分支（mx010/011/012/015 无 codex/ 前缀）规范化或清理
      - 补打 v0.9.0 tag 并推送
      - 合入后全仓回归绿
    whitelist:
      - CHANGELOG.md
      - docs/
  - title: 脚本审查清理（异常大脚本 + 个人运维脚本迁出）
    slug: script-audit-cleanup
    acceptance:
      - scripts/delete_videos.sh（644KB）内容审查完成：用途分类、敏感路径排查，结论记录到 docs/
      - 个人运维脚本（merge_bilibili*/clean_usb_hd/clean-ghost-mounts/hash_check/full_hash*/generate_covers 等）迁出仓或归档，scripts/ 仅留项目核心脚本
      - scripts-inventory.md 更新，脚本清单与仓内一致
    whitelist:
      - scripts/
      - docs/scripts-inventory.md
```

## 备注

- 执行 cwd：`/Users/fan/program/apps/medio-0`（Mac2017）；访问 `ssh -i ~/.ssh/id_ed25519_xianyu fan@192.168.3.116`
- 各卡验收后走标准流程：执行体回写 → 机审 → 合入批准
- 证书换发独立挂账，不拆卡；若老板中途要求并入自动流程再补卡
- 分支收口卡风险：合入冲突需逐个解决，预计耗时最长
