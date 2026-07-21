# PASTE-OPS · 工厂派单板（用户只复制）

> 架构窗维护本文件。用户：**不讨论、不加需求**，按序把「粘贴包」贴进对应窗。  
> 模型路由：[`../product/cursor-model-routing.md`](../product/cursor-model-routing.md)

## 流水线状态

| 序号 | brief | 状态 | 窗 |
|------|-------|------|-----|
| F0 | 建制 | done | — |
| F1 | 断线恢复 | done `eeaf388` | — |
| F1-2 | 投递三态零谎报 | done `578e7fe` | — |
| F2-1 | soak N=5 + orphan=0 | done `9af1fb4` | — |
| F2-2 | 双机版本对齐核对 | accepted · **现在开工** | 编排 · **Auto** |
| F3-1 | （待架构写） | queued | — |

---

## 粘贴包 A · 壳窗 / 过桥窗

```
本波次 F2-2 只派编排窗。壳 / 过桥待命，无 brief 勿改代码。
```

---

## 粘贴包 B · 编排窗 · F2-2 开工（现在贴这个）

```
模型：Auto
只认 brief：docs/briefs/2026-07-21-f2-dual-host-version-check.md
白名单：scripts/ccc-dual-host-check.sh（新）
        scripts/chat_server/routers/desktop.py（若加 version 端点）
        scripts/chat_server/app.py（注册路由）
        tests/scripts/test_dual_host_check.py（新）
        docs/deploy/dual-host-version-check.md（新）
        docs/product/hub-api-v1.md（若加端点，先改）
禁止：改 Desktop、改 Engine 主循环、改 transfer/flow 契约、改无关文件。
做完：填 brief §8 → commit → 回复「F2-2 done <hash>」
提交说明建议：
feat(deploy): one-shot dual-host version alignment check (F2-2)
```

---

## 粘贴包 C · 架构窗自动节奏

1. 见「F2-2 done」→ 验收 → 写 F3-1 brief（业务仓闭环）+ 更新本板  
2. F2 退出条件：soak N=5 + orphan=0（F2-1 ✓）+ 双机可核对（F2-2）→ 进 F3
