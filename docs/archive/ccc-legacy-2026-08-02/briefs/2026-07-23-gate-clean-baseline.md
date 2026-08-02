# 干净板门禁基线 · `stress-mx-20260723-gate-clean`

- 前置：Cursor 清 `ccc-demo`/`qb` 残卡 + 剪 flow 幽灵；`efficiency_six` **无 e05**
- HEAD：`95a6ac2` · `CCC_MAX_CONCURRENT=6`
- 投递：10 epic（每仓 e01–e04+e08）· ~8min 收口 · **abnormal=0**
- 验收：2026-07-23T23:50:16+08:00 · KPI **PASS**

## 对照脏板 R5

| 指标 | R5（脏板+旧残） | gate-clean |
|------|-----------------|------------|
| epic done | 12/12（含 e05） | **10/10** |
| abnormal | 0 | **0** |
| queue indep p95 | 9.4s | **2.0s** |
| gate_wall p95 | 221s | **210.9s**（p50=104.5） |
| e2e p95 | 534s | **421s** |
| 瓶颈提示 | 杂 | **审测偏慢：gate p95=211 ≫ dev p95=12** |

## 结论（卡点）

干净板上 **gate_wall p95≈211s 仍是木桶短板**（dev p95≈12s）。  
残留任务不是主因；审测/L1（或 testing 串行预算）才是。  
本轮**只建基线，不盲改门禁**——下一刀应针对 testing 墙钟拆分（L0 短路径 vs Claude L1）与并行审测预算，而不是再加 `MAX_CONCURRENT`。

## 产物

- `~/.ccc/stress-matrix/stress-mx-20260723-gate-clean-efficiency.{json,md}`
- `~/.ccc/stress-matrix/stress-mx-20260723-gate-clean-kpi-gate.{json,md}`
