# DEV-PACKET: 016-golden-path-regression-seal

> **状态：Cursor 自跑完成**（R4 · Relay Flash 封印后）  
> 主题：平台侧可重复回归 + 生产交付封印文档。不用 Claude。

---

## 目标

1. Hub 探活契约可重复（`ccc-hub-probe.sh` + 单测锁口径）。  
2. prepare / transfer_gate 相关既有测绿。  
3. production-readiness / PRODUCTION-DELIVERY-ROUNDS 勾「平台生产交付完成」。  
4. 双机 `main` aligned。

---

## 白名单

- `tests/scripts/test_hub_probe_contract.py`（新建）
- `docs/dev-packets/README.md` / `PRODUCTION-DELIVERY-ROUNDS.md`
- `docs/briefs/2026-07-27-ccc-production-readiness.md`
- `docs/briefs/2026-07-28-relay-flash-seal.md`（交叉一句）
- 本文件

---

## 验收

```bash
bash scripts/ccc-hub-probe.sh   # 隧道或 LAN
PYTHONPATH=scripts pytest tests/scripts/test_hub_probe_contract.py tests/scripts/test_role_tool.py -q --tb=short
```

---

## §8（Cursor 自填）

见合入 commit + readiness「平台生产交付」节。
