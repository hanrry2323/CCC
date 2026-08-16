# 卡3 · DSH 只读取证席首单（合规红线扫描）

- **状态**：✅ 首单完成（待老板人工核实）
- **批次**：Phase 2 · ccc-plan-029 卡3
- **环境**：测试实例（headless code 模式，只读）
- **日期**：2026-08-16

## 结论

**DSH 只读取证/审计席首单跑通**，产出完整合规红线审计报告（见 `26-k3-audit-first-run.md`）。DSH 作为只读取证执行体的能力得到实证：Code Run 真执行、取证带证据、零残留、弱模型不作开发——与 ccc-plan-029 卡3 的预期一致。

## 首单结果摘要（DSH 审计结论，待人工核实）

**3 处实锤（高置信）**：
1. `docs/relay/KEY-POOL.md` + `docs/executors/{overview,loop-code}.md` 仍把 4100/4102 写「现行」无「史」标（红线2）
2. `docs/runbooks/pre-test-dual-host-sync.md:20` 现行文档含 `git add -A`（红线5）
3. 2017 机审交叉配对在引擎硬编码（main.py:2827-2831），但 dev-channel/machine-audit-flow/executors.json 三处残留「自验收」旧口径（红线1）

**待老板裁决**：AGENTS.md「唯一出口 6100/6102」 vs 08-14/08-16 直连决策（口径漂移，红线2-3/7-2）

**其他**：registry SSOT 机制成立、卡命名 188 张零违规、两仓无密钥明文；`__dev__/` 落点表外目录（中）；决策档截断密钥前缀建议掩码（中）

## 审计过程的旁证

- 审计中 bash 工具反复报 `missing required property "description"`（**57% 漏参模式在真实任务中重现**）——DSH 用 read/glob/grep 替代 bash 绕行，且对无法核实的项（git 历史）诚实标「未核实」。
- 覆盖度自评完整（读了/没读/推断），符合卡3 审计契约。

## 后续（老板动作）

- [ ] 老板人工核实首单命中/误报
- [ ] 裁决 2-3 直连口径（改红线 or 回退）
- [ ] 处置 3 处实锤（标史/重写）
