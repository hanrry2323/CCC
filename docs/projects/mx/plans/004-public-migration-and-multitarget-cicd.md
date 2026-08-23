# 方案 · medio-0 公开化搬迁与多端 CI/CD

> 项目：mx · 编号：mx-plan-004 · 状态：待验收 · 作者：CCC 中枢 · 工具：ccc
> 批准：老板确认转卡 · 2026-08-17
> 创建：2026-08-14 · 更新：2026-08-24
> 验收（2026-08-24 · DSH 受老板临时授权代行核验）：**不通过，维持待验收**。卡 mx045/046/047 均已合入 main，但两条核心验收准则与远端事实不符——①「历史敏感 commit 已 filter-repo 抹除」不成立：fresh fetch 后 origin/main 可达对象中仍含签名材料 blob 三个（combined.jks 1382B、medio.p7b 2754B/2687B，`git rev-list origin/main --objects | grep p7b|jks` 可复现）；②「公开仓库可访问」未发生（GitHub 匿名 API 404 = private）。Phase 2 敏感清零、LICENSE/README、CI 补齐等项已落地。**需老板单独拍板**：真·filter-repo + 全分支 force push + 签名密钥轮换（破坏性动作，超出本次授权范围）
> 关联卡：mx045, mx046, mx047
> 关联方案：mx-plan-003（底座解耦 · 建议先完成 003 再执行本方案）
> 进度：3/3 (100%)
> 里程碑：公开化搬迁与多端 CI/CD

## 目标

把 medio-0 从私有仓迁为公开 GitHub 仓库（Public），接入免费 Actions CI/CD（后端/前端/HarmonyOS 多端构建），彻底清除历史敏感信息（鸿蒙签名私钥等），补 LICENSE/README 公开说明。**本方案仅起草，执行须等签名私钥清洗的单独人工确认**（涉及 git filter-repo 重写历史）。

## 背景

- 当前私有仓库 CI 计费/支付报错，Actions 全 job 未启动（roadmap 挂账）。
- 历史 commit 含鸿蒙签名私钥 `medio.p7b.pem`（mx005 清单第 5 项）→ 公开前须 `git filter-repo` 抹除 + 签名密钥重签（鸿蒙搁置，可延后）。
- 全仓需敏感信息扫描清零：密钥/token/.env/内部 IP（`feiniu`、`192.168.*`）/本地路径（`/Users/fan/...`）。
- `release.yml` 内部路径需清理。

## 方案内容

### Phase 1 · 敏感历史清洗（单独人工确认后执行）

1. `git filter-repo` 抹除含 `medio.p7b.pem` 的历史 commit（重写 commit hash，须在批次卡收口后单独执行，不打断自动流程）。
2. 签名密钥处置：鸿蒙搁置可延后；确认无其它密钥泄露。

### Phase 2 · 敏感信息清零

1. 全仓扫描清零：密钥 / token / .env / 内部 IP（`feiniu`、`192.168.*`）/ 本地路径（`/Users/fan/...`）。
2. 补 `.gitignore` 确认运行时敏感文件不入库。

### Phase 3 · 公开化与多端 CI/CD

1. 补 LICENSE + README 公开说明。
2. `release.yml` 内部路径清理。
3. 接入多端 CI：后端 cargo（test/clippy/fmt）、前端 vitest、HarmonyOS hvigor 构建。
4. 切 Private → Public → 验证 CI 全绿。

### 约束

- 依赖 mx-plan-003 底座解耦完成后（干净的构建基线）再执行。
- filter-repo 重写历史是破坏性动作，须单独人工确认、备份后执行。

## 验收标准

- [ ] 公开仓库可访问，Actions CI/CD 全绿（后端/前端/HarmonyOS 三端）<!-- 未满足：仓库仍 private -->
- [x] 全仓敏感信息扫描清零（密钥/token/内部 IP/本地路径）
- [x] LICENSE + README 公开说明补齐
- [x] `release.yml` 内部路径清理完成
- [ ] 历史敏感 commit（含 `medio.p7b.pem`）已 filter-repo 抹除 <!-- 未满足：签名 blob 仍可从 origin/main 可达（2026-08-24 复现命令见验收行） -->

## 功能卡

> 一个功能一张卡（ccc-plan-027）。本方案功能卡段供节点② 确认；**实际转卡执行待人工确认敏感清洗后**。

### 敏感历史清洗（filter-repo）

目标：抹除历史 commit 中的鸿蒙签名私钥 `medio.p7b.pem`，重写历史后验证无残留。

实现：git filter-repo 定向抹除；备份；重写后 clone 验证。

验收：`git log --all` 无 `medio.p7b.pem`，仓库可正常构建。

颗粒度：单仓历史重写（破坏性，须备份 + 单独人工确认）

依赖：无

架构位置：mx 仓 git 历史层（filter-repo 重写）

### 敏感信息扫描清零

目标：全仓清零密钥/token/.env/内部 IP/本地路径。

实现：全仓 grep 扫描 + 修复 + 复核。

验收：扫描报告 0 命中（除授权占位）。

颗粒度：全仓跨模块扫描 + 修复

依赖：敏感历史清洗（filter-repo）

架构位置：全仓敏感面（.env / 内部 IP / 本地路径 / 签名材料）

### 公开化与多端 CI/CD

目标：补 LICENSE/README、清理 release.yml、接入三端 CI、切 Public 验证。

实现：LICENSE/README；release.yml 路径清理；ci.yml 补 HarmonyOS；切 Public。

验收：Actions 三端全绿，Public 仓可访问。

颗粒度：CI/CD 与发布配置层

依赖：敏感信息扫描清零

架构位置：.github/workflows + release 配置 + 公开仓边界

## 转卡计划

新方案优先用「## 功能卡」段；**转卡执行须在敏感清洗人工确认后**（本方案当前仅起草）。

## 备注

- 风险：filter-repo 重写历史会改 commit hash，破坏性动作，须备份 + 单独人工确认。
- 依赖：建议 mx-plan-003 底座解耦完成后再执行（干净的构建基线）。
- 本方案当前仅起草（D2 决策：只起草不动代码），待老板单独确认敏感清洗后再转卡执行。
