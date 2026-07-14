# Plan: test-cockpit-alive-check — Cockpit /api/alive 单元测试

> 撰写: ccc-product | 执行: ccc-dev (manual)

## 当前代码状态

`ccc-cockpit.py` 无单元测试。`/api/alive` 是 Cockpit 核心端点，但只在手动浏览时验证。

## 范围

- **目标**: 为 `ccc-cockpit.py` 的 `/api/alive` 端点编写 pytest 单元测试
- **只改文件**: `tests/scripts/` 下新增测试文件

## 改动

1. 新建 `tests/scripts/test_cockpit.py`
2. 测试 `GET /api/alive` 返回 200 + JSON body
3. 测试 JSON body 含 `ports` 数组（每个端口有 name/port/host/status）
4. 测试返回值格式：每个 port 有 `status` ∈ {alive, dead, unknown}

## 验收

- [new] `tests/scripts/test_cockpit.py` 文件存在
- [pass] `python3 -m pytest tests/scripts/test_cockpit.py -q` → PASS
- [字段] 测试断言 /api/alive 返回的每个 port 有 status 字段
- [不侵入] Cockpit 代码无改动（纯加测试）
