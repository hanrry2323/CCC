# DSH 巡检 3 红旗 + 1 蓝旗处置移交清单（2026-08-18）

> 用途：机审核对本次巡检修复的真实性与完整性。提交：`b7fdd8c3`（已推 2017，工作区无残留）。
> 处置留档：`/loop/adopt` 已写 4 条（2 adopt + 2 reject），见 2017 `DATA_DIR/observer/.adopted.jsonl`。

---

## 一、背景

DSH 巡检（`http://192.168.3.116:7788/#/dsh`，报告 `patrol-report-12.md`）检出 3 红旗 + 1 蓝旗：

| # | 级别 | 面 | 现象 |
|---|------|-----|------|
| 1 | 🔴 | L2 代码层 | `test_process_sampler_records_peak` 偶尔失败（`server/tests/test_engine_metrics.py:77`） |
| 2 | 🔴 | L1 系统层 | 子项目（cd/cla）方案文件状态非法或缺少「环境准备」声明，`validate-plans.sh` 报 35 个 FAIL |
| 3 | 🔴 | L1 系统层 | 本地 mac2017 无 `qx-map` 实仓源码（`docs/projects/_catalog/qx-map.md`） |
| 4 | 🔵 | — | 报告解析占位行（全字段 `---`） |

---

## 二、问题定性（核查后）

1. **红旗1 = 间歇性 flaky 测试，非稳定故障**：M1/2017 各自连跑 3~5 次均通过。根因：`ProcessSampler` 采样间隔被 `max(0.5, interval)` 强制最小 0.5s，而测试只 `sleep(0.7)`——采样机会仅 1~2 次，沙箱/调度慢时错过首次采样 → `peak_rss_mb` 保持 `None` → 断言失败。
2. **红旗2 = 真实数据卫生问题**（35 个 FAIL，三小类）：
   - 7 个方案状态字非法：「已确认」（ccc-038/039）、「计划中」（cla-007/008、mx-006/007/008）不在合法状态机内（合法：已确定|待排期|部分执行|待验收|已完成|作废|已覆盖）。
   - 12 个 cla 子项目方案缺卡头 `> 环境准备：` 声明（002~006、007~008、009~013）。
   - 28 个方案关联卡已全部关闭/作废，但方案状态仍滞留「部分执行」（cla 10 + hp 10 + mx 1 + xy 6）或「已完成但验收未勾选」（cla-002/003、mx-005）。
3. **红旗3 = 误报，设计如此**：`_catalog/qx-map.md` 明确「CCC 运行时**不依赖** qx-map（D2），勿把 qx-map 路径写进 Engine/web 热路径」；qx-map 为知识地图仓，只放 M1，2017 无实仓是既定设计。巡检建议处置即为「留」。
4. **蓝旗 = 解析噪音**：报告表内全字段 `---` 的占位行，无实际内容。

---

## 三、已做修改（commit b7fdd8c3，36 文件 +52/-40）

| 类 | 文件 | 动作 |
|----|------|------|
| 状态字对齐 | ccc/plans/038、039 | 「已确认」→「待排期」（按 2026-08-17 决策「已确认改待排期」） |
| 状态字对齐 | cla/plans/007、008；mx/plans/006、007、008 | 「计划中」→「待排期」 |
| 环境准备补全 | cla/plans/002~006、007~013（12 个） | 卡头新增 `> 环境准备：` 行（真实环境依赖，如 Python/Playwright/SQLite/LLM 通道） |
| 生命周期收口 | cla/plans/002~006、009~013（10 个） | 部分执行→待验收（关联卡已全关） |
| 生命周期收口 | hp/plans/009、012、015、017、022、024、025、027、028、029（10 个） | 部分执行→待验收 |
| 生命周期收口 | mx/plans/004（部分执行→待验收）、005（已完成→待验收，因验收未勾选） | 状态推进 |
| 生命周期收口 | xy/plans/002~007（6 个） | 部分执行→待验收 |
| flaky 测试加固 | server/tests/test_engine_metrics.py | 0.7s 固定等待 → 等待首次采样（3s 超时），interval 显式 0.5 |

**未动的文件**：`scripts/validate-plans.sh`（校验器本体零改动）、`server/engine/metrics.py`（实现零改动）、`docs/projects/cla/roadmap.md`（工作区遗留无关改动已还原）。

**明确未做**：验收标准勾选（`- [x]`）全部未动——勾选权归验收席/老板，本次只把状态推进到「待验收」，不代勾。

---

## 四、机审验证点（逐条带命令）

1. **校验器全绿**（2017/M1 同命令）：
   ```
   bash scripts/validate-plans.sh
   ```
   期望：`全部通过`，0 错误（修复前 35 错误 48 警告）。
2. **flaky 测试修复验证**（连跑 5 次不失败，M1/2017 双机）：
   ```
   python3 -m pytest server/tests/test_engine_metrics.py -q
   python3 -m pytest server/tests/test_engine_metrics.py::test_process_sampler_records_peak -q
   ```
   期望：全 `[100%]` 通过。
3. **状态字合规抽查**（改过的 37 个文件）：
   ```
   grep -h '状态：' docs/projects/{ccc,cla,hp,mx,xy}/plans/*.md | sort | uniq -c
   ```
   期望：只出现 已确定|待排期|部分执行|待验收|已完成|作废|已覆盖；本次改动文件无「已确认」「计划中」。
4. **环境准备声明抽查**：
   ```
   grep -l '子项目：' docs/projects/cla/plans/*.md | xargs grep -L '环境准备：'
   ```
   期望：无输出（cla 全部子项目方案均有声明）。
5. **关联卡全关但状态未推进 = 0**（改后不应再报 8.2 FAIL，即验证点 1 已覆盖；抽查 hp-009 卡头为「待验收」）。
6. **验收标准未代勾**：
   ```
   git show b7fdd8c3 --stat | grep -c "\[x\]"   # 期望 0 处勾选改动
   git diff b7fdd8c3^ b7fdd8c3 | grep -c "\[x\]" # 期望 0
   ```
   期望：提交内无任何验收勾选变更。
7. **范围不越界**：`git show --stat b7fdd8c3` 仅 36 个方案 md + 1 个测试文件；无校验器/实现/配置文件混入；无密钥。
8. **留档已写**（2017 执行）：
   ```
   tail -4 ~/.ccc/data/observer/.adopted.jsonl
   ```
   期望：4 条记录（adopt×2 + reject×2），report=patrol-report-12，reason 与本次处置一致。

---

## 五、遗留（不属本次范围，机审知悉即可）

- 28 个方案停在「待验收」——验收标准勾选由验收席按卡逐项核验后完成。
- ccc-036 功能卡缺三要素为 WARN 非 FAIL（旧方案兼容），未动。
- 蓝旗占位行根因在 DSH 报告生成端（`| --- |` 空行被当 findings 解析），本次未改报告解析逻辑（涉及 DSH 生成端，另议）。
