# 方案 · 电商 B2B 多账户隔离登录与反爬网关（M3-3.1）

> 项目：cla · 编号：cla-plan-007 · 状态：计划中 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：无
> 里程碑：M3 · 各大医药电商平台数据抓取
> 子项目：3.1 电商 B2B 多账户凭证隔离登录与反爬网关
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地电商 B2B（药易购等）采集执行器：多账户凭证隔离登录、动态代理网关（IP 轮换）、频率自适应熔断，为 3.2 竞品价/库存高频采样提供安全的采集通道。

## 背景

架构定稿：
- `src/crawlers/ecommerce.py`：aiohttp + 动态代理（requests 统一走代理网关，动态轮换 IP）。
- 频率自适应熔断：`slots.py` 限流排队，单 B2B 平台每分钟并发硬卡 ≤30 次；HTTP 429 触发熔断 10 分钟（保护账号 + 不损耗 Token）。
- 多账户凭证隔离：settings.yaml + secure_keys.env（不提交 Git），登录态各自独立落盘。

## 方案内容

### 1. 电商爬虫执行器
- `src/crawlers/ecommerce.py`：BaseCrawler 实现——aiohttp 并发请求、代理网关路由、多账户凭证隔离加载（每账户独立 cookie 会话）、登录态落盘与 401 重登。

### 2. 代理网关 + 限流熔断
- `src/common/proxy.py`：代理池轮换（配置化 IP 列表，不内嵌固定代理）。
- `src/scheduler/slots.py`：Slots Semaphore 并发限流（每分钟 ≤30 次/平台）。
- HTTP 429 检测 → 该平台 Worker 熔断 10 分钟（跳过任务不硬退）。

## 验收标准

- [ ] 多账户登录态隔离落盘（单测）
- [ ] 实际站点（药易购）跑通返回结构化数据
- [ ] 限流硬卡生效（并发测试 ≤30/min）
- [ ] 429 熔断 10 分钟生效，熔断期间任务跳过不崩溃

## 功能卡

### 电商爬虫执行器 + 多账户凭证隔离

目标：完成电商爬虫执行器与账户隔离，交付可验收产物。

实现：按「方案内容」1 节落地——ecommerce.py + 配置 + 登录态隔离。

验收：验收标准条款 1-2（账户隔离 / 实际站点跑通）。

颗粒度：子项目内功能卡（约 2 天）。

依赖：无（BaseCrawler 已在 main）

架构位置：`src/crawlers/ecommerce.py`、`config/settings.yaml`、`config/secure_keys.env`

### 代理网关 + 限流熔断

目标：完成反爬网关与限流熔断，交付可验收产物。

实现：按「方案内容」2 节落地——proxy.py + slots.py + 429 熔断。

验收：验收标准条款 3-4（限流硬卡 / 429 熔断）。

颗粒度：子项目内功能卡（约 1.5 天）。

依赖：电商爬虫执行器

架构位置：`src/common/proxy.py`、`src/scheduler/slots.py`

## 转卡计划

电商爬虫执行器（1 卡）/ 代理网关 + 限流熔断（1 卡）

## 备注

- 代理 IP 由配置提供，代码不内嵌具体代理；真实代理资源由老板提供后填入配置。
- 首期平台：药易购（yaoyigou）；平台适配器结构保证后续可插拔。