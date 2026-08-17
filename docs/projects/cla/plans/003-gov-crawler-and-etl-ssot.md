# 方案 · 政府挂网价 Playwright 抓取 + 数据清洗与 SSOT 药名归一 (M2)
> 项目：cla · 编号：cla-plan-003 · 状态：草案 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：待出卡
> 关联方案：无
> 里程碑：M2 · 政府药械招采网价格监测
> 子项目：2.1 挂网价 Playwright 自适应抓取, 2.2 数据清洗与 SSOT 药名归一
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

落地 gov 采集线：Playwright 无头浏览器动态抓取四川药械等 gov 招采公示网挂网价（UA 伪造 + 会话持久化 + 自动重登），经数据清洗（标准化字段 + SSOT 药名归一）写入 `gov_prices` 表，为 M2-2.3 降价预警提供数据。

## 背景

架构定稿要求：
- `src/crawlers/gov.py` 继承 `BaseCrawler`（load_credential/login/crawl/extract/run 五契约）。
- 反爬：Playwright 无头 + 伪造 UA + 模拟悬停/滑动绕 JS 指纹；LocalStorage/Cookies 序列化落盘，仅 401/失效时重登。
- 数据清洗：Levenshtein 模糊距离把「西格列汀片」与「磷酸西格列汀片」类差异归一到企业级 SSOT 通用药名大辞典。
- `gov_prices` 表：generic_name/specification/packaging/manufacturer/gov_price/region/announcement_url/fetched_at，唯一约束 (generic_name, specification, manufacturer, region) 防重复。

## 方案内容

### 1. gov 爬虫执行器（2.1）
- `src/crawlers/gov.py`：BaseCrawler 实现——Playwright 异步抓取、UA 伪造、登录态落盘（`data/sessions/`）、仅 401 重登、解析公示列表与详情页、输出原始异构数据。
- 每省一个配置化站点适配器（首期：sichuan sc_yjj）。

### 2. 数据清洗与 SSOT 归一（2.2）
- `src/etl/cleaner.py`：字段标准化（名称/规格/包装/厂商/价格/省份/来源 URL）+ fetched_at 注入。
- `data/ssot_dict.json`（药名大辞典种子库）：Levenshtein 匹配归一；未命中打「待人工确认」标记。
- 落库：`gov_prices` 唯一约束防重复，upsert 语义（价格变化更新）。

## 转卡计划

### cla004 | gov 爬虫执行器（Playwright 自适应抓取）
* 颗粒度：2.0 天（4 文件 + 配置）
* 依赖：无（BaseCrawler 已在 main）
* 架构位置：`src/crawlers/gov.py`、`data/sessions/`、`config/settings.yaml`
* 验收：pytest 单测（mock 站点）；实际站点手动跑通返回结构化数据；登录态落盘/重登逻辑有测试。

### cla005 | 数据清洗管线 + SSOT 药名归一 + 落库
* 颗粒度：1.5 天（3 文件）
* 依赖：--depends cla004
* 架构位置：`src/etl/cleaner.py`、`data/ssot_dict.json`、`gov_prices` 表
* 验收：同一药品不同写法归一成功（单测覆盖 Levenshtein）；重复抓取不产生重复行；价格变化正确 upsert。

## 备注

- 2.2 原为独立子项目，因与抓取强耦合（数据不出采集线）并入本方案。
- 首期只做四川（sc_yjj），站点适配器结构保证后续省份可插拔。