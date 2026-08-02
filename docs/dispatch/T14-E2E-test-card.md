# 测试任务卡 T14-E2E · E2E 全链路流程测试（临时卡）

> 关联：T14 · 执行体：Trae（mock 执行体）· 状态：待分派 · 日期：2026-08-02
> 目的：验证「任务卡 → Engine 派发 → 执行体执行 → 回写 → 看板更新」全链路

## 任务

在 `server/README.md` 末尾添加一行状态注释：

```
# E2E test marker — do not remove
```

## 范围

- `server/README.md`：追加一行注释

## 验收

```bash
grep -q "E2E test marker" server/README.md && echo "PASS" || echo "FAIL"
```

## 红线

1. 不改其他文件
2. 不碰运行面
3. 完成后自检通过才提交