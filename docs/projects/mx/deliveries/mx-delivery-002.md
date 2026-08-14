# 交付报告 · medio-0 收口与安全加固（v0.9.0）

> 项目：mx · 编号：mx-delivery-002 · 方案：mx-plan-002 · 作者：CCC 中枢 · 交付日期：2026-08-12 · 软件版本：v0.9.0 · 对应 Git Tag：v0.9.0

## 1. 交付目标与背景

medio-0 收口与安全加固：修复 4 个 P1 安全漏洞（RSS XSS / 鉴权白名单脆弱 fail-closed / 无暴力破解防护 / SSRF）、Token 环境变量化（消除硬编码）、双机路径对齐、9 个积压分支清理、补打 v0.9.0 Tag、脚本审查清理。共 6 张卡（mx030-035）全部关闭，生产环境安全基线建立。

## 2. 交付物清单（Delivery Checklist）

- [x] **交付报告**：本报告已归档至 `docs/projects/mx/deliveries/`
- [x] **CHANGELOG**：业务仓 CHANGELOG.md 已记录（v0.9.0 安全加固）
- [x] **RELEASE**：业务仓发布记录
- [x] **Git Tag**：v0.9.0 补打并 push（mx033）
- [x] **可复跑安装验证**：业务仓 scripts/ 可复跑（health_probe / test_api_smoke / test_rss）

## 3. 方案与卡状态对齐（Gate Checklist）

- [x] **方案状态置为「已完成」**：mx-plan-002 状态=已完成（标题版本号已对齐 v0.9.0）
- [x] **方案验收标准全勾**：mx-plan-002 验收 5 项全 `[x]`，进度 6/6 (100%)
- [x] **关联任务卡全关闭**：mx030-035 全部已关闭
- [x] **项目档案近况同步**：README 线路/近况已刷新（2026-08-14）
- [x] **全局线路图挂账同步**：docs/roadmap.md 已补 mx-plan-002 段（2026-08-14）

## 4. 版本与发布信息

- 软件版本：`v0.9.0`
- 发布渠道：Mac2017 生产机（`/Users/fan/program/apps/medio-0`）
- 关联卡：mx030-mx035

## 5. 可复跑安装与部署验证

- 安全探针：`scripts/health_probe.sh`（健康检查）
- API 冒烟：`scripts/test_api_smoke.sh`（鉴权/接口）
- RSS 链路：`scripts/test_rss.sh`
- 依赖：Mac2017 生产机，`deploy-package/start.sh` 拉起常驻服务

## 6. 备注

- 交付收尾由 2026-08-14 新体系全量梳理补做（此前卡全关但缺交付报告）。
- 公开化（mx-plan-004）涉及签名私钥历史清洗，待单独人工确认后另排。
