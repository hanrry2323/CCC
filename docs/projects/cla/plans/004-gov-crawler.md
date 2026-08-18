# 方案 · 挂网价 Playwright 自适应抓取（M2-2.1）

> 项目：cla · 编号：cla-plan-004 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-18（cla017 已回写待合入）
> 关联卡：cla017
> 关联方案：无
> 进度：0/1 (0%)
> 里程碑：M2 · 政府药械招采网价格监测
> 子项目：2.1 挂网价 Playwright 自适应抓取
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地 gov 采集执行器：Playwright 无头浏览器动态抓取四川药械等 gov 招采公示网挂网价（UA 伪造 + 会话持久化 + 自动重登），输出原始异构数据供 2.2 清洗。

## 背景

架构定稿：
- `src/crawlers/gov.py` 继承 `BaseCrawler`（load_credential/login/crawl/extract/run 五契约）。
- 反爬：Playwright 无头 + 伪造 UA + 模拟悬停/滑动绕 JS 指纹；LocalStorage/Cookies 序列化落盘，仅 401/失效时重登。
- 每省一个配置化站点适配器（首期：四川 sc_yjj），适配器结构保证后续省份可插拔。

## 方案内容

### 1. gov 爬虫执行器
- `src/crawlers/gov.py`：BaseCrawler 实现——Playwright 异步抓取、UA 伪造、登录态落盘（`data/sessions/`）、仅 401 重登、解析公示列表与详情页、输出原始异构数据。

### 2. 站点适配器
- 配置化适配器（`config/settings.yaml` 站点段 + 适配器类），首期实现 sichuan/sc_yjj。

## 验收标准

- [ ] pytest 单测（mock 站点）通过
- [ ] 实际站点（四川）手动跑通返回结构化数据
- [ ] 登录态落盘/重登逻辑有测试覆盖
- [ ] 不触碰电商线（3.x 范围外）

## 功能卡

### gov 爬虫执行器（Playwright 自适应抓取）

目标：完成 gov 采集执行器与四川站点适配器，交付可验收产物。

实现：按「方案内容」两节落地——gov.py BaseCrawler 实现 + 站点适配器。

验收：验收标准四条款全过（单测绿 / 实际站点跑通 / 登录态测试 / 范围不越界）。

颗粒度：子项目级（1-2 卡，约 2 天）。

依赖：无（BaseCrawler 已在 main）

架构位置：`src/crawlers/gov.py`、`data/sessions/`、`config/settings.yaml`

## 转卡计划

gov 爬虫执行器（1-2 卡，待出卡）

## 备注

- 首期只做四川（sc_yjj），站点适配器结构保证后续省份可插拔。
- 2.2 数据清洗与 SSOT 药名归一为独立子项目（cla-plan-005），本方案只产原始数据。