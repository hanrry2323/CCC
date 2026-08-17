# 方案 · SQLite 持久化账本底座与路径修复 (M1)
> 项目：cla · 编号：cla-plan-001 · 状态：部分执行 · 作者：OpenCode · 工具：opencode
> 创建：2026-08-17 · 更新：2026-08-17
> 关联卡：cla001
> 关联方案：无
> 里程碑：M1 · 独立底座与路径清零
> 子项目：1.1 路径纠偏与冒烟测试绿灯, 1.2 SQLite 持久化队列重构
> 环境准备：Python >= 3.10, SQLite 3
> 决策源：/Users/apple/qx-map/__archive__/decisions/ClawMed-CCC-Architecture-2026-08-17.md

## 目标

彻底清除 `clawmed-ccc` 仓内在 Mac2017 环境下的绝对路径硬编码历史债，使冒烟测试 (Pytest) 达到 100% 绿灯通过；并用 SQLite 关系数据库持久化账本全面重构纯内存队列 (`InMemoryQueue`)，打牢低配设备私有部署的持久化底座。

## 背景

紫A高空审计发现两项严重债务：
1. `tests/test_obs1_smoke.py` 和 `test_obs2_smoke.py` 硬编码了 `cwd="/Users/apple/program/clawmed-ccc"`，在 Mac2017 物理运行环境 (`/Users/fan/program/apps/clawmed-ccc`) 下直接触发 FileNotFoundError 导致 100% 崩溃。
2. 调度队列完全依赖 Python 线程锁 `InMemoryQueue`，一旦进程重启或闪退，所有 pending 的任务将会被蒸发，缺乏企业级调度可靠性。

## 环境准备

本方案运行需要以下底层软件与依赖支撑，出卡前需确保环境就绪：
- **运行时环境**：Python >= 3.10, SQLite 3
- **依赖库**：`pyyaml` (配置解析), `pytest` (测试套件运行)

## 方案内容

### 1. 绝对路径解耦与 Pytest 断言对齐
将测试套件中所有硬编码绝对路径解耦，改为动态寻找当前测试文件所在的项目根路径：
```python
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```
修改测试函数中的非标准 `return bool` 返回值为标准的 `assert`，去除 PytestReturnNotNoneWarning 警告，还原干净日志。

### 2. SQLite 持久化任务队列开发
在 `data/clawmed.db` 下新建 `jobs` 表，结构如下：
```sql
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    payload TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
重构 `src/scheduler/queue.py`。将 `InMemoryQueue` 更改为 `SQLiteQueue`，在 `enqueue` 和 `dequeue` 方法中直接利用 SQLite 的事务型 ACID 写入和乐观锁读取，断电重启后自动恢复 jobs。

---

## 转卡计划

本计划根据 ccc-plan-032 的“三要素”原则，拆解为以下 2 张高内聚、短周期功能卡：

### 1. cla001 | 绝对路径解耦与测试套件修复
*   **颗粒度**：0.5 天 (改动文件数：2 个)
*   **依赖**：无
*   **架构位置**：
    *   `tests/test_obs1_smoke.py`
    *   `tests/test_obs2_smoke.py`
*   **改动细则**：
    *   将子进程执行 CWD 从绝对路径修改为动态计算 of BASE_DIR。
    *   将 test 方法返回值删除，全量改为 `assert`。
*   **验收标准**：
    *   在 Mac2017 环境下运行 `python3 -m pytest tests/test_obs1_smoke.py tests/test_obs2_smoke.py` 100% 全绿，无 Warning 警告。

### 2. cla002 | SQLite 任务账本与持久化队列重构
*   **颗粒度**：1.0 天 (改动文件数：3 个)
*   **依赖**：--depends cla001
*   **架构位置**：
    *   `src/scheduler/queue.py`
    *   `src/scheduler/job.py`
    *   `data/clawmed.db`
*   **改动细则**：
    *   重构 `queue.py` 的 InMemoryQueue，连接本地 SQLite 初始化 `jobs` 表。
    *   重构 `enqueue` 与 `dequeue` 读写事务。
*   **验收标准**：
    *   运行 `python3 -m pytest tests/test_scheduler_jobspec.py` 通过。
    *   编写持久化测试用例：在入队 2 个任务后，手动 Kill 后端进程并重新实例化 Queue，读取队列应仍存在该 2 个任务，保证任务在闪退下不蒸发。
