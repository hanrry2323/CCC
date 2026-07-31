# 下一步：最小可跑通收口（v1.1）

> 前置：本机 `16b615e` 已提交（最小可跑通 v1）。  
> 约定：每切片做完 **自动 commit**，不堆未提交大包。

## 现状缺口

| 缺口 | 现状 | 目标 |
|------|------|------|
| `ccc-engine.py` | ~972 行 | **&lt;400**（CLI + attach + 常量） |
| 金路径 | 仅单测契约 | 2017 真跑长意图 + FAIL→blocked |
| 五态调度 | 有别名，kb 仍可能挡 | verify 后非阻塞快通 done |
| 产线 | M1 ahead，未上 2017 | push → pull → Engine 热更 |

## 切片顺序

1. **push + 2017 准备** — `git push origin main`；2017 `git pull` + 重启 Engine；确认 `CCC_MIN_PIPELINE=1`
2. **胶水 &lt;400** — helper 迁出 `observability` / `health` 等；测绿即 commit
3. **热路径对齐** — `run_verify_gate`；min 路径下 kb 快通 done；loop 不跑 regress/audit/stress
4. **e2e** — demo/qb 长意图 → OpenCode commit → done；FAIL→blocked 无 L3b；tid 写入 `docs/briefs/2026-07-31-min-pipeline-golden.md`
5. **VERSION v0.66.0** — `check-version-sync.py` 绿并 commit

## 不做

删旧列名 / 重开 L3b·stress·Ops / QuantHive 并轨 / force push
