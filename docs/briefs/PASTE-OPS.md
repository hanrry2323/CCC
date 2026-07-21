# PASTE-OPS · 工厂派单板（用户只复制）

> 架构窗维护本文件。用户：**不讨论、不加需求**，按序把「粘贴包」贴进对应窗。  
> 模型路由：[`../product/cursor-model-routing.md`](../product/cursor-model-routing.md)

## 流水线状态

| 序号 | brief | 状态 | 窗 |
|------|-------|------|-----|
| F0 | 建制 | done | — |
| F1 | 断线恢复 | done `eeaf388` | — |
| F1-2 | 投递三态零谎报 | done `578e7fe` | — |
| F2-1 | soak N=5 + orphan=0 | accepted · **现在开工** | 编排 · **Auto** |
| F2-2 | （待架构写） | queued | — |

---

## 粘贴包 A · 壳窗 / 过桥窗

```
本波次 F2-1 只派编排窗。壳 / 过桥待命，无 brief 勿改代码。
```

---

## 粘贴包 B · 编排窗 · F2-1 开工（现在贴这个）

```
模型：Auto
只认 brief：docs/briefs/2026-07-21-f2-soak-orphan-zero.md
白名单：scripts/engine/ · scripts/board/roles/ · scripts/ccc-engine.py（必要时）
        scripts/smoke-ccc-demo-soak.sh · scripts/smoke-f1-backlog-failover.sh · tests/scripts/
        docs/product/hub-shell-phase-status.md（仅新增 F2-1 行）
禁止：改 Desktop、改 Hub API 字段、改 transfer/flow 契约、改无关文件。
做完：填 brief §8 → commit → 回复「F2-1 done <hash>」
提交说明建议：
test(engine): soak N=5 with orphan_delta=0 and failover regression (F2-1)
```

---

## 粘贴包 C · 架构窗自动节奏

1. 见「F2-1 done」→ 验收 → 写 F2-2 brief（双机版本对齐候选）+ 更新本板  
2. 重复直至 `four-role-fluency-charter` F2 退出条件满足，再进 F3
