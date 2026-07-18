# Plan: fix-engine-log-printf — 修复 engine_log printf 风格调用

> 撰写：20-min patrol | 执行：直接（1 phase）
> 复杂度：small

## 当前代码状态

`ccc-engine.py:72` `engine_log(msg: str)` 只接受 1 个字符串参数。
但 `ccc-engine.py:775-778` 和 `782-785` 以 printf 风格传递 3 个参数：
```python
engine_log("[stats] %s — %s", ws.name, ins.get("label", ""))
```
导致 `TypeError: engine_log() takes 1 positional argument but 3 were given`，
被 stats 段的 except 捕获为 "aggregate error"。

## 修复

修改 `engine_log` 函数为支持 `*args`：

```python
def engine_log(msg: str, *args: str) -> None:
    if args:
        msg = msg % args
    _log.info("%s", msg)
```

## 验收

- [ ] `python3 -c "import ast; ast.parse(open('scripts/ccc-engine.py').read())"` 通过
- [ ] 引擎不再报 `engine_log() takes 1 positional argument but 3 were given`
