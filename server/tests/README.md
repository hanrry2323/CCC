# tests/ — 测试

> 冒烟 + 单元 · 运行：`python3 -m pytest server/tests/ -q`

## 约定

- 新增模块/函数必须带测试；重构不降绿。
- **测试夹具允许字面端口/路径/工具名**（测试数据，非生产硬编码；硬编码扫描排除 `tests/`）。
- loader 四用例：正常加载 / 缺项报错 / 空值报错 / 可选键默认值。
- executors schema 断言**锁定契约 §7 五角色**（角色集合、分类合法性、绑定非空）。

## 覆盖现状

| 文件 | 覆盖 |
|------|------|
| `test_skeleton.py` | 目录结构、config 加载、executors schema |

## 施工入口

- T2/T3：新增 `test_engine_*.py` / `test_board_*.py` / `test_web_*.py`。
