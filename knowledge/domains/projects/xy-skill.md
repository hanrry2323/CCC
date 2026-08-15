# xy (xianyu) 开发技能指南

> 项目：xianyu — 独立业务仓（视频生产管线）
> 仓库：/Users/fan/program/apps/xianyu（Mac2017）

## 常用命令

- 运行测试：`pytest` 全量
- 单模块测试：`pytest tests/<module>/ -v`
- 代码检查：`ruff check`

## 开发守则

1. 改动前先跑 `pytest` 确认基线全绿
2. 视频管线改动需确保端到端可运行
3. 配置文件变更需同步更新文档
4. 禁止硬编码路径（使用配置或环境变量）
5. 文档改动需确保与代码一致（`grep` 验证无过期引用）