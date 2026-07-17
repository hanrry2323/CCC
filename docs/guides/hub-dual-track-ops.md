# Hub 双轨操作卡（复制即用）

> 简称：**cla** = clawmed-ccc  
> 你只负责点 Hub；验证由协作方后台看看板。

登录：`http://127.0.0.1:7777` · 账密 `ccc` / `ccc`  
当前控制面：`enabled`（下达后 Engine 可能立刻消费）

> **看板语义（v0.42.2+）**：Hub「下达」落 **待办大卡（epic）**，常驻左侧待办列；Claude product 扇出 **work 小卡**进 planned 及之后流转。大卡不会进 in_progress。完成后可在待办列头点「清理已完成」（仅 `ui_hidden`，数据仍在）。

---

## 任务 1 · A1（xianyu 质量门）

### 你点这些

1. 打开 Hub → 对话  
2. 侧栏项目选 **xianyu**（或标题栏项目选 xianyu）  
3. 点标题栏 **＋ 下达任务**（或工具条「下达任务」）  
4. 下面三块**整段复制**进对应框 → 提交  

### 【复制 · 标题】

```
A1 xianyu 视频质量门：跑通近期优化并出验收清单
```

### 【复制 · 描述】

```
目标：验证 xianyu 近期视频质量相关优化是否可用，产出书面验收清单；本卡不过线则不进入「产出 CCC 介绍片」。

验收（全部满足才算完）：
1) 指定一条样例输入，连续跑 2 次出片进程不崩溃
2) 写出差距表：画质/音画同步/乱码/其它 — 每项标注 已修|未修|不适用
3) 至少产出 1 条时长≥30s、人眼可看的样片，路径写进 report
4) report 写到本仓 .ccc/reports/ 下，文件名含本 task id

范围：只改/只跑与「视频质量验证」直接相关的脚本与配置；不做介绍片、不大重构。
复杂度：medium
```

### 【复制 · 其它字段】

- 项目 / workspace：**xianyu**  
- 复杂度：**medium**  

---

## 任务 2 · cla B1（迁入最小爬虫）

> B0 已完成（仓已在）。本卡是第一笔业务迁入。

### 你点这些

1. Hub → 对话  
2. 项目选 **clawmed-ccc**（列表里可能显示全名；任务标题用 `cla:`）  
3. **＋ 下达任务**  
4. 复制下面三块 → 提交  

### 【复制 · 标题】

```
cla:B1 从旧 qx 迁入最小爬虫并跑通 1 条
```

### 【复制 · 描述】

```
目标：在 clawmed-ccc（简称 cla）中，从归档零件库 ~/program/projects/qx 迁入「最小可跑」爬虫相关代码，跑通 1 条（优先 demo 或四川价之一）。

约束：
- 不要复制旧 qx/clawmed 的 .ccc/plans|phases|reports|board 任务垃圾
- 旧仓 _archive/ 仅参考，不当事情来源
- 编排入口保持 CCC Hub；不要恢复 PM2 唯一调度叙事

验收：
1) clawmed-ccc 内有迁入代码路径（写进 report）
2) 一条可重复命令或本仓脚本能跑通选定爬虫/demo（exit 0 或约定成功码）
3) README 或 docs 用 ≤10 行写明「怎么跑」
4) report 含本 task id

复杂度：medium
零件库：~/program/projects/qx （归档后零件仍在 crawlers/ 等目录）
```

### 【复制 · 其它字段】

- 项目 / workspace：**clawmed-ccc**  
- 复杂度：**medium**  

### B1 假发布说明（2026-07-17）

看板 **已发布** ≠ 真交付。B1 `cla-b1--qx--1-vded`：`src/` 空、reviewer FALLBACK。  
回炉卡 **`cla-b1-1-migrate`**（`cla:B1.1`）已由协作方 seed 并拉起；Hub 上看 **in_progress** 即可，无需再点一次 B1。

硬验收（B1.1）：`src/` 有 `.py` + smoke pytest 绿 + README demo 命令。

---

---

## 任务 3 · 流程诊断 OBS1（打 H1 commit 门）

> 不求业务迁入；只验证「有文件改动 → 必须出现含 task_id 的新 commit」。  
> 项目：**clawmed-ccc** · 复杂度：**medium**

### 【复制 · 标题】

```
cla:OBS1 流程探针：tests 冒烟 + 强制 git commit
```

### 【复制 · 描述】

```
目标：验证 CCC 过门前是否产生「含本 task id」的新 git commit（打 H1）。

必须做：
1) 新建 tests/test_obs1_smoke.py（注意是仓库根 tests/，不是 scripts/tests/），内容：def test_ok(): assert True
2) 新建 docs/OBS1.md，一行说明本卡目的
3) 用 git 提交上述文件，commit message 必须含本 task id（如 cla-obs1-…）
4) report 写明：git rev-parse HEAD、git log -1 --oneline、git ls-files tests/test_obs1_smoke.py

硬验收（缺一不可）：
- tests/test_obs1_smoke.py 已被 git 跟踪
- HEAD 相对任务开始时变化，且 log -1 含 task id
- python3 -m pytest tests/test_obs1_smoke.py -q 通过

禁止：只改 .ccc/ 或只写 VERSION/CHANGELOG 就过门；禁止空 commit。
复杂度：medium
```

---

## 任务 4 · 流程诊断 OBS2（打 H2/H3 reviewer+pytest）

> 接在 OBS1 后。验证 Engine 是否真跑 `tests/`，以及 reviewer 是否仍 FALLBACK 假 PASS。  
> 项目：**clawmed-ccc** · 复杂度：**medium**

### 【复制 · 标题】

```
cla:OBS2 流程探针：改断言触发 tests 门禁
```

### 【复制 · 描述】

```
目标：在 OBS1 基础上改 tests，逼 Engine pytest 门禁跑起来；观察 reviewer 是否 LLM 真审（打 H2/H3）。

必须做：
1) 修改 tests/test_obs1_smoke.py（或新建 tests/test_obs2_smoke.py）：增加 test_obs2 断言 1+1==2
2) 更新 docs/OBS1.md 追加一节「OBS2」
3) git commit，message 含本 task id
4) report 写明 pytest 命令与输出摘要；若有 verdict，摘录 Verdict 行

硬验收：
- git 跟踪到本次改动
- pytest tests/ -q 全绿
- Hub/看板进入 testing 后，协作方核对 engine 日志是否出现 pytest 而非「无 tests/ 跳过」

复杂度：medium
```

---

## 下达后你回我一句

任选：

```
A1 已下达
```

或

```
cla B1 已下达
```

或诊断：

```
OBS1 已下达
```

```
OBS1 + OBS2 都已下达
```

我收到后去看板核对列、plan/phases、是否被 Engine 拉起；OBS 跑完再总结流程修复，不提前大改 CCC。
