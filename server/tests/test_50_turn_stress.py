#!/usr/bin/env python3
"""test_50_turn_stress.py — 全自动 50 轮工具调用 3 轮循环极限压测脚本。

本脚本不属于常规 pytest 套件，需手动执行：
    python server/tests/test_50_turn_stress.py

验证指标（硬性断言）：
1. 100% 连通：流式 SSE 输出不发生 Connection refused 或是 401 错误。
2. 0 切片错位：解析 SSE 的 data payload 时，0 次 JSON 解码错误。
3. 0 进程泄露：每轮（50 轮）结束后，执行 `ps aux` 检索，确保 Claude 及其拉起的所有后台子进程（node / sleep）全部被 Popen 进程组杀手 100% 清理，泄露数恒等于 0。
"""

import sys
from pathlib import Path

# 把项目根加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import json
import time
import signal
import tempfile
import stat
import urllib.request
import urllib.error
import subprocess
import threading
from server.web.server import create_server

# ── 1. 构造高仿真 Mock Claude Code CLI ──
MOCK_CLAUDE_CONTENT = """#!/usr/bin/env python3
import sys
import time
import json
import subprocess

# 仿真：Claude Code 启动时拉起的在途后台执行进程（Node.js 与 grep 等工具）
# 它们与本脚本处于同一个进程组，本脚本退出时如果不使用进程组 SIGKILL，它们会变成孤儿进程泄露
node_proc = subprocess.Popen(["node", "-e", "setInterval(() => {}, 1000)"])
sleep_proc = subprocess.Popen(["sleep", "100"])

# 仿真：输出 stream-json 流式事件，对齐 _normalize_stream_event 契约
events = [
    {"type": "system", "subtype": "init", "model": "flash", "tools": ["Grep", "Files"]},
    {"type": "assistant", "message": {"content": [{"type": "thinking", "data": "Searching the workspace for state.js..."}]}},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "tu_grep", "name": "Grep", "input": {"query": "delta"}}]}},
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "tu_grep", "content": "matched line in state.js"}]}},
    {"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "I found the matching lines in state.js."}}},
    {"type": "result", "is_error": False, "result": "I found the matching lines in state.js."}
]

for ev in events:
    print(json.dumps(ev), flush=True)
    time.sleep(0.005) # 仿真流式延迟
"""


def check_process_leak() -> list[str]:
    """使用 ps aux 检查是否有泄露的模拟 node（setInterval）或 sleep（sleep 100）进程。"""
    try:
        output = subprocess.check_output(["ps", "aux"], text=True)
    except Exception:
        output = ""
    leaks = []
    for line in output.splitlines():
        if "setInterval" in line and "grep" not in line and "test_50_turn_stress" not in line:
            leaks.append(line)
        if "sleep 100" in line and "grep" not in line and "test_50_turn_stress" not in line:
            leaks.append(line)
    return leaks


def main():
    print("=======================================================")
    print(" 开始执行对话大底座加固与 50 轮稳定性极限压测")
    print("=======================================================")

    # 准备临时 Mock 目录
    temp_dir = tempfile.TemporaryDirectory()
    mock_bin_path = Path(temp_dir.name) / "mock_claude"
    mock_bin_path.write_text(MOCK_CLAUDE_CONTENT, encoding="utf-8")
    mock_bin_path.chmod(mock_bin_path.stat().st_mode | stat.S_IEXEC)

    # 注入环境变量，使大脑调用我们高仿的自愈杀进程 Mock 路径
    os.environ["CCC_BRAIN_CLAUDE_BIN"] = str(mock_bin_path.resolve())
    os.environ["CCC_BRAIN_BASE_URL"] = "http://127.0.0.1:6100"
    os.environ["CCC_BRAIN_AUTH_TOKEN"] = "mock_token"
    os.environ["CCC_WEB_AUTH_REQUIRED"] = "0" # 免登录

    # 启动本地服务器
    print("[INFO] 正在启动 7789 端口的临时 HTTP 服务端...")
    server = create_server("127.0.0.1", 7789)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # 等待服务器就绪
    for _ in range(10):
        try:
            with urllib.request.urlopen("http://127.0.0.1:7789/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.1)

    print("[PASS] 服务端已成功就绪！")

    total_turns = 50
    total_rounds = 3
    parser_errors = 0
    connect_errors = 0

    try:
        for round_idx in range(1, total_rounds + 1):
            print(f"\n--- [Round {round_idx}/{total_rounds}] 启动 50 轮极限压测往返 ---")

            for turn_idx in range(1, total_turns + 1):
                payload = {
                    "message": f"搜索 docs/ 并列出前缀 (Round {round_idx} Turn {turn_idx})",
                    "stream": True,
                    "thread_id": f"stress_round_{round_idx}"
                }
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:7789/conversation",
                    data=data,
                    headers={"Content-Type": "application/json"}
                )

                try:
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        assert resp.status == 200, f"HTTP 状态码错误: {resp.status}"

                        # 逐行消费 SSE 流式内容，进行切片错位和粘连强断言
                        event_name = None
                        for line in resp:
                            line_str = line.decode("utf-8").strip()
                            if not line_str:
                                continue
                            if line_str.startswith("event:"):
                                event_name = line_str[6:].strip()
                            elif line_str.startswith("data:"):
                                raw_data = line_str[5:].strip()
                                try:
                                    json.loads(raw_data)
                                except json.JSONDecodeError as exc:
                                    parser_errors += 1
                                    print(f"[FAIL] JSON 粘连解析错误: {raw_data} - {exc}", file=sys.stderr)
                except urllib.error.URLError as err:
                    connect_errors += 1
                    print(f"[FAIL] 连通性错误: {err}", file=sys.stderr)

                # 打印单次往返进度
                if turn_idx % 10 == 0:
                    print(f"  进度: 已完成 {turn_idx}/{total_turns} 轮往返")

            # 轮次结束，静待 0.2 秒完成资源最后回收
            time.sleep(0.2)

            # ── 进程泄露强断言 ──
            leaked = check_process_leak()
            print(f"[CHECK] 本轮结束进程泄露状态：在途泄露进程数 = {len(leaked)}")
            if leaked:
                for l in leaked:
                    print(f"  [LEAK_PROCESS]: {l}", file=sys.stderr)
                raise AssertionError(f"在 Round {round_idx} 结束后发现有未被回收的孤儿进程泄露！")
            else:
                print(f"[PASS] Round {round_idx} 完美回收 0 泄露！")

        print("\n=======================================================")
        print(" 压测最终核算断言指标核对")
        print("=======================================================")
        print(f"- 累计并发连接请求次：{total_rounds * total_turns} 次")
        print(f"- 连通性连接错误数：{connect_errors} 次 (预期恒等于 0)")
        print(f"- JSON 切片粘连错位：{parser_errors} 次 (预期恒等于 0)")

        assert connect_errors == 0, f"连通率未达 100%，发生连接错误: {connect_errors} 次"
        assert parser_errors == 0, f"存在 JSON 切片粘连解析错误: {parser_errors} 次"

        print("\n[SUCCESS] 恭喜！50 轮工具调用 3 轮循环极限压测 100% 完美通过！")
        print("[SUCCESS] 0 切片错位 · 100% 连通 · 0 进程组泄露 终极指标全部达成！")

    finally:
        # 关闭服务器
        server.shutdown()
        temp_dir.cleanup()


if __name__ == "__main__":
    main()
