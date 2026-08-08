#!/usr/bin/env python3
"""存量 sidecar 卡状态一键收敛同步脚本。

扫描 docs/dispatch 所有的磁盘卡：
若卡在磁盘上状态为「已关闭 / 打回 / 待分派」，但 sidecar runtime 中仍有活跃流程态，
则调用 `clear_card_state` 写入失效记录，实现 runtime 彻底合拢。
"""

import sys
from pathlib import Path

# Insert project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.board.models import base_state
from server.board.loader import load_index_file
from server.web.server import _executor_log_dir
from server.engine.runtime_state import read_card_state, clear_card_state

def main():
    log_dir = _executor_log_dir()
    if not log_dir:
        print("[ERROR] 无法确定 EXECUTOR_LOG_DIR 执行日志目录，请检查配置。")
        sys.exit(1)

    print(f"执行日志目录: {log_dir}")
    runtime = read_card_state(log_dir)

    # 扫描磁盘上所有的卡片
    dispatch_dir = Path(__file__).resolve().parents[1] / "docs/dispatch"
    try:
        index_entries = load_index_file(dispatch_dir)
    except Exception as e:
        print(f"[ERROR] 载入磁盘卡片索引失败: {e}")
        sys.exit(1)

    cleared_count = 0
    for entry in index_entries.values():
        card_id = entry.get("id")
        if not card_id:
            continue

        # 磁盘卡片的当前状态
        raw_state = entry.get("state", "")
        disk_base = base_state(raw_state)

        # 若卡在磁盘上属于「已关闭」、「打回」或「待分派」
        if disk_base in ("已关闭", "打回", "待分派"):
            # 检查 sidecar runtime 里是否存在活跃的流程态
            rt = runtime.get(card_id)
            # 注意：如果 rt["state"] 是 None，说明已经失效了，不需要再清除
            if rt and rt.get("state") is not None:
                print(f"发现撕裂卡: id={card_id} 磁盘状态={disk_base} sidecar状态={rt['state']} -> 正在同步清除 sidecar 状态")
                clear_card_state(log_dir, card_id)
                cleared_count += 1

    print(f"收敛同步完成。共清理了 {cleared_count} 张残留卡的 sidecar 状态。")

if __name__ == "__main__":
    main()
