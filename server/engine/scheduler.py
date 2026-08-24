"""通用定时任务框架 — 间隔调度、只读巡检、变更类走卡。

用法：
    $PYTHON_BIN -m server.engine.scheduler --config <config.env>        # 持续模式
    $PYTHON_BIN -m server.engine.scheduler --config <config.env> --once  # 单次执行后退出

支持两种任务类型：
1. 只读巡检（readonly）：采集状态信息，写入文件，不产生业务动作
2. 变更类（change）：生成任务卡到 dispatch 目录，走正常任务卡流程

定时默认只读：巡检只采集不动作；变更类走任务卡保留确认。
失败时记日志，不中断、不产生脏数据。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from server.config.loader import ConfigError, load_config

logger = logging.getLogger("ccc.engine.scheduler")

DEFAULT_INTERVAL_SECONDS = 60

# 单任务硬性执行超时（秒）：超时自动放弃，不阻塞后续任务（P0 调度器裸奔加固）。
DEFAULT_TASK_TIMEOUT_SECONDS = 60
# 巡检任务并发上限（线程隔离）：单任务挂死/超时不影响其它巡检。
TASK_MAX_WORKERS = 4

# 持久线程池：跨轮复用，不再每轮新建/销毁，避免挂死线程随轮次累积造成资源泄漏。
# 挂死任务只占用 1 个 worker，其余 worker 继续服务后续任务 → 不阻塞整轮。
_TASK_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=TASK_MAX_WORKERS)


# ── 任务类型 ──

TASK_TYPE_READONLY = "readonly"
TASK_TYPE_CHANGE = "change"


@dataclass
class ScheduledTask:
    """单个定时任务描述。

    Attributes:
        name: 任务名（日志 / 标识用）。
        task_type: TASK_TYPE_READONLY 或 TASK_TYPE_CHANGE。
        run: 可调用对象，接收 config dict，返回 (ok: bool, summary: dict)。
    """

    name: str
    task_type: str
    run: Callable[[dict[str, Any]], tuple[bool, dict[str, Any]]]


# ── 注册表 ──


@dataclass
class TaskRegistry:
    """定时任务注册表。"""

    tasks: list[ScheduledTask] = field(default_factory=list)

    def register(self, task: ScheduledTask) -> None:
        self.tasks.append(task)

    def list_readonly(self) -> list[ScheduledTask]:
        return [t for t in self.tasks if t.task_type == TASK_TYPE_READONLY]

    def list_change(self) -> list[ScheduledTask]:
        return [t for t in self.tasks if t.task_type == TASK_TYPE_CHANGE]


# ── 执行 ──


def _task_timeout_seconds(cfg: dict[str, Any]) -> int:
    """单个巡检/变更任务硬性超时（秒）。可经 SCHEDULER_TASK_TIMEOUT 覆盖。"""
    try:
        return max(1, int(cfg.get("SCHEDULER_TASK_TIMEOUT") or DEFAULT_TASK_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TASK_TIMEOUT_SECONDS


def _guarded_task_result(
    task: ScheduledTask,
    cfg: dict[str, Any],
    timeout: int,
    executor: concurrent.futures.ThreadPoolExecutor,
) -> dict[str, Any]:
    """在线程中执行单个任务并保护后续调度：

    - 每个任务跑独立线程（线程隔离，单个挂死不拖垮全局）。
    - 硬性超时 ``timeout`` 秒：超时自动放弃（cancel 不可中断已运行线程，仅等超时放弃结果）。
    - ``task.run`` 抛出异常 / 超时均捕获：打 error 日志，返回 ok=False，不中断整轮。

    返回结构：name / type / ok / summary / crashed（True=异常或超时，说明为基础设施失败）。
    """
    base: dict[str, Any] = {"name": task.name, "type": task.task_type, "ok": False}
    future = executor.submit(task.run, cfg)
    try:
        ok, summary = future.result(timeout=timeout)
        base["ok"] = bool(ok)
        base["summary"] = summary if summary is not None else {}
    except concurrent.futures.TimeoutError:
        # 超时：线程仍在跑（无法中断 daemon 线程），主动放弃该任务结果，不阻塞后续。
        base["crashed"] = True
        base["summary"] = {"timeout": True, "reason": f"exceeded {timeout}s hard timeout"}
        logger.error("巡检任务 %s 超时放弃（>%ds）: %s", task.name, timeout, task.name)
    except Exception as exc:
        base["crashed"] = True
        base["summary"] = {
            "crashed": True,
            "reason": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[:2000],
        }
        logger.error("巡检任务 %s 异常（已隔离，不中断本轮）: %s\n%s", task.name, exc, traceback.format_exc()[:1000])
    return base


def run_tasks(
    registry: TaskRegistry,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """执行所有注册任务，返回结果列表。

    只读巡检总是执行；变更类仅在 SCHEDULER_DISPATCH_DIR 非空时执行。
    每个任务线程隔离并带硬性超时（见 _guarded_task_result），异常/超时不影响其它任务。
    """
    results: list[dict[str, Any]] = []
    dispatch_dir = cfg.get("SCHEDULER_DISPATCH_DIR", "")
    timeout = _task_timeout_seconds(cfg)

    readonly_tasks = registry.list_readonly()

    # 只读巡检线程隔离执行（持久池 _TASK_POOL：挂死任务仅占 1 worker，不阻塞整轮）
    if not dispatch_dir:
        skipped: list[dict[str, Any]] = []
        for task in registry.list_change():
            logger.info("变更任务 %s 跳过（SCHEDULER_DISPATCH_DIR 未配置）", task.name)
            skipped.append(
                {
                    "name": task.name,
                    "type": task.task_type,
                    "ok": True,
                    "summary": {"skipped": True, "reason": "dispatch_dir not configured"},
                }
            )
        readonly = [_guarded_task_result(t, cfg, timeout, _TASK_POOL) for t in readonly_tasks]
        results = readonly + skipped
    else:
        readonly = [_guarded_task_result(t, cfg, timeout, _TASK_POOL) for t in readonly_tasks]
        change = [_guarded_task_result(t, cfg, timeout, _TASK_POOL) for t in registry.list_change()]
        results = readonly + change

    for r in results:
        if r.get("crashed"):
            logger.error("任务 %s 异常（已隔离）: %s", r["name"], r.get("summary"))
        elif r["ok"]:
            logger.info("任务 %s 完成: %s", r["name"], r.get("summary"))
        else:
            logger.warning("任务 %s 失败: %s", r["name"], r.get("summary"))

    return results


# ── CLI ──


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ccc-engine-scheduler",
        description="CCC Engine 定时任务框架：间隔调度、只读巡检、变更类走卡",
    )
    parser.add_argument("--config", required=True, help="config.env 路径（必填）")
    parser.add_argument("--once", action="store_true", help="单次执行后退出")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="覆盖轮询间隔秒数（默认使用 config 中的 SCHEDULER_INTERVAL）",
    )
    return parser.parse_args(argv)


def run_once(
    registry: TaskRegistry,
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """单次执行所有注册任务。"""
    return run_tasks(registry, cfg)


def run_loop(
    registry: TaskRegistry,
    cfg: dict[str, Any],
    interval: int,
) -> None:
    """持续模式：每 interval 秒执行一轮。"""
    logger.info("定时任务框架启动（轮询间隔 %ds）", interval)
    while True:
        results = run_tasks(registry, cfg)
        logger.info("本轮任务完成: %s", json.dumps(results, ensure_ascii=False))
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return 2

    interval = args.interval if args.interval > 0 else int(cfg.get("SCHEDULER_INTERVAL", DEFAULT_INTERVAL_SECONDS))

    # 注册默认任务（可被外部扩展覆盖）
    registry = _default_registry()

    if args.once:
        results = run_once(registry, cfg)
        print(json.dumps(results, ensure_ascii=False))
        return 0

    run_loop(registry, cfg, interval)
    return 0  # 持续模式不返回（Ctrl-C 终止）


# ── 默认注册表 ──


def _default_registry() -> TaskRegistry:
    """返回默认注册表（含集群采集巡检任务）。"""
    registry = TaskRegistry()

    # 延迟导入避免循环依赖
    from server.engine.cluster import collect_cluster_status
    from server.engine.observer import run_observation_metrics, run_observer

    def _trigger_scheduled_ops_wrapper(cfg):
        from server.engine.observer import trigger_scheduled_ops

        return trigger_scheduled_ops(cfg)

    registry.register(
        ScheduledTask(
            name="cluster-collect",
            task_type=TASK_TYPE_READONLY,
            run=collect_cluster_status,
        )
    )

    registry.register(
        ScheduledTask(
            name="loop-observer",
            task_type=TASK_TYPE_READONLY,
            run=run_observer,
        )
    )

    registry.register(
        ScheduledTask(
            name="observation-metrics",
            task_type=TASK_TYPE_READONLY,
            run=run_observation_metrics,
        )
    )

    registry.register(
        ScheduledTask(
            name="scheduled-ops-trigger",
            task_type=TASK_TYPE_READONLY,
            run=_trigger_scheduled_ops_wrapper,
        )
    )

    def _merge_dsh_trigger(cfg):
        """螺旋上升 P2-1（B2）：新 merge commit → SSH 触发 DSH 全局跑通复核。

        兜底捕获所有 push main 路径（含非 approve-merge 的直接 push），
        与 approve-merge 钩子（B1）+ 6h cron 并存。记录上次已触发 merge sha
        于 DATA_DIR/observer/.merge-dsh-last.json，避免重复触发。
        """
        import json as _json
        import os
        import subprocess as _sp

        data_dir = cfg.get("DATA_DIR", "data")
        state_file = os.path.join(data_dir, "observer", ".merge-dsh-last.json")
        try:
            res = _sp.run(
                ["git", "log", "origin/main", "--merges", "-n", "1", "--format=%H"],
                capture_output=True, text=True, timeout=5,
            )
            if res.returncode != 0:
                return (True, {"skipped": "git log 失败"})
            merge_sha = res.stdout.strip()
        except Exception as e:  # noqa: BLE001
            return (True, {"skipped": f"merge 检测异常: {e}"})

        if not merge_sha:
            return (True, {"skipped": "无 merge commit"})

        # 读上次已触发 sha
        last_sha = ""
        try:
            if os.path.isfile(state_file):
                with open(state_file, encoding="utf-8") as f:
                    last_sha = (_json.load(f) or {}).get("merge_sha", "")
        except Exception:
            last_sha = ""

        if merge_sha == last_sha:
            return (True, {"skipped": "无新 merge"})

        # 新 merge → SSH 触发 DSH（fire-and-forget）
        try:
            deploy_home = os.environ.get("M2_DEPLOY_HOME", "/Users/fan")
            _sp.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                 "fan@192.168.3.116",
                 f"cd {deploy_home} && nohup /bin/bash {deploy_home}/.dsh/run_patrol.sh >> {deploy_home}/.dsh/patrol_merge.log 2>&1 &"],
                capture_output=True, text=True, timeout=15,
            )
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                _json.dump({"merge_sha": merge_sha}, f)
            return (True, {"triggered": True, "merge_sha": merge_sha})
        except Exception as e:  # noqa: BLE001
            return (True, {"error": f"SSH 触发失败: {e}"})

    registry.register(
        ScheduledTask(
            name="merge-dsh-trigger",
            task_type=TASK_TYPE_READONLY,
            run=_merge_dsh_trigger,
        )
    )

    def _log_janitor(cfg):
        """F4 日志轮转（2026-08-24 直修，受老板临时授权）：exec 会话日志 >30 天 gzip 归档。

        只处理 exec/ 下已结束会话的 ``*.log``（派发侧每会话独立落盘、写完即闭），
        归档后删原文件。launchd 持有 fd 的 ``*.stderr.log`` 不在此轮转（截断会产生
        稀疏洞），如需轮转应走 newsyslog 配置。
        """
        import gzip as _gzip
        import os as _os
        import time as _time
        from pathlib import Path as _P

        log_dir = _P(cfg.get("LOG_DIR") or (_P.home() / ".ccc" / "logs"))
        exec_dir = log_dir / "exec"
        cutoff = _time.time() - 30 * 86400
        archived = 0
        errors = 0
        try:
            if exec_dir.is_dir():
                for f in sorted(exec_dir.iterdir()):
                    try:
                        name = f.name
                        if not name.endswith(".log") or name.endswith(".audit.log"):
                            continue  # 机审证据日志保留原文，不归档
                        st = f.stat()
                        if st.st_mtime > cutoff:
                            continue
                        with open(f, "rb") as src, _gzip.open(str(f) + ".gz", "wb", compresslevel=6) as g:
                            while True:
                                chunk = src.read(1 << 20)
                                if not chunk:
                                    break
                                g.write(chunk)
                        f.unlink()
                        archived += 1
                    except OSError:
                        errors += 1
                        continue
                # 同名 .gz 超 90 天直接删除（归档二阶生命周期）
                gz_cutoff = _time.time() - 90 * 86400
                for g in exec_dir.glob("*.log.gz"):
                    try:
                        if g.stat().st_mtime < gz_cutoff:
                            g.unlink()
                    except OSError:
                        errors += 1
            return (True, {"archived": archived, "errors": errors, "cutoff_days": 30})
        except Exception as e:  # noqa: BLE001
            return (False, {"error": str(e)})

    registry.register(
        ScheduledTask(
            name="log-janitor",
            task_type=TASK_TYPE_READONLY,
            run=_log_janitor,
        )
    )

    return registry


if __name__ == "__main__":
    sys.exit(main())
