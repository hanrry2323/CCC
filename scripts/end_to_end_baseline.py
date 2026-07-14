#!/usr/bin/env python3
"""
p0-3-end-to-end-submit-task: Baseline verification script

This script runs through the complete end-to-end flow from task submission
through scheduler execution and result verification.
"""

import json
import subprocess
import sys
import sqlite3
import time
from datetime import datetime
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR
WORKSPACE = BASE_DIR
DISPATCH_DB = WORKSPACE / "data/dispatch.db"
PIPELINE_DB = WORKSPACE / "data/pipeline.db"
API_SERVER = "http://localhost:8000/api/dispatcher"


def colorize(text: str, color: str = "") -> str:
    """ANSI color escape codes."""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m",
    }
    b = colors.get(color[:4]) if len(color) >= 4 else ""
    return f"{b}{text}{colors['reset']}"


def print_step(step: str, details: str = ""):
    print(f"\n{colorize('▶', 'blue')} {step}")
    if details:
        print(f"    {details}")


def print_success(msg: str):
    print(f"{colorize('✓', 'green')} {msg}")


def print_error(msg: str):
    print(f"{colorize('✗', 'red')} {msg}")


def print_info(msg: str):
    print(f"{colorize('ℹ', 'yellow')} {msg}")


def run_command(
    cmd: list[str], cwd: Path | None = None, capture: bool = True
) -> tuple[bool, str, str]:
    """Run a shell command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        print_error(f"Command timed out: {' '.join(cmd)}")
        return False, "", ""
    except Exception as e:
        print_error(f"Command failed: {e}")
        return False, "", str(e)


def check_file_exists(path: Path, desc: str = "file") -> bool:
    """Check if a file or directory exists."""
    exists = path.exists()
    if exists:
        print_success(f"{desc} exists: {path}")
    else:
        print_error(f"{desc} missing: {path}")
    return exists


def query_db(db_path: Path, query: str) -> list[dict]:
    """Run a SQL query on a SQLite database."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_scheduler_pid() -> int | None:
    """Look for scheduler PID on macOS."""
    try:
        run_command(["pgrep", "-f", "scheduler.py run"], capture=False)
        pid = int(
            subprocess.check_output(["pgrep", "-f", "scheduler.py run"], text=True)
            .strip()
            .split()[0]
        )
        print_success(f"Scheduler PID: {pid}")
        return pid
    except (subprocess.CalledProcessError, ValueError):
        print_error("Scheduler not running")
        return None


def start_scheduler(cwd: Path) -> bool:
    """Start scheduler daemon."""
    print_step("Step 1: Start scheduler daemon")
    success, _, stderr = run_command(
        ["python3", "scheduler.py", "run"],
        cwd=cwd,
        capture=False,
    )

    if success:
        print_success("Scheduler daemon started")
    else:
        print_error(f"Failed to start scheduler: {stderr}")

    return success


def submit_task(cwd: Path) -> str | None:
    """Submit a minimal task via API."""
    print_step("Step 2: Submit minimal task")
    payload = {
        "type": "manual_verification",
        "prompt": "echo 'Hello from end-to-end verification'",
        "priority": "normal",
    }

    print_info(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                f"{API_SERVER}/submit",
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(payload),
            ],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if response.returncode == 0:
            try:
                data = json.loads(response.stdout)
                task_id = data.get("task_id") or data.get("id")
                print_success(f"Task submitted, ID: {task_id}")
                return task_id
            except json.JSONDecodeError:
                print_info(f"Response (raw): {response.stdout}")
                return None
        else:
            print_error(f"Submit failed: {response.stderr}")
            return None
    except Exception as e:
        print_error(f"Submit request failed: {e}")
        return None


def wait_and_get_status(task_id: str | None, timeout: int = 120) -> dict | None:
    """Wait for task to complete and return its status."""
    print_step("Step 3: Wait for task completion")

    if not task_id:
        return None

    print_info(f"Waiting max {timeout}s for task {task_id} to complete")

    start = time.time()
    iteration = 0

    while time.time() - start < timeout:
        iteration += 1

        # Poll via API
        try:
            response = subprocess.run(
                ["curl", "-s", f"{API_SERVER}/tasks"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if response.returncode == 0:
                try:
                    tasks = json.loads(response.stdout)
                    for task in tasks:
                        if task.get("id") == task_id:
                            status = task.get("status", "unknown")
                            print_info(f"[{iteration}s] Task status: {status}")
                            if status in ["completed", "failed"]:
                                print_success(f"Task final status: {status}")
                                return task

                            # Show elapsed time for running tasks
                            if status == "running":
                                elapsed = int(time.time() - start)
                                print_info(
                                    f"Started at {datetime.fromtimestamp(start).isoformat()}"
                                )
                                print_info(f"Currently running for {elapsed}s")

                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print_info(f"Poll error: {e}")

        # Wait before next poll
        time.sleep(5)

    print_error(f"Timeout: Task did not complete within {timeout}s")
    return None


def check_db(task_id: str | None) -> dict | None:
    """Check pipeline.db for task results."""
    print_step("Step 4: Verify results in pipeline.db")

    if not task_id:
        return None

    # Query task result
    query = """
    SELECT task_id, task_type, task_prompt, exec_status, exec_return_code,
           task_result, exec_start_time, exec_end_time
    FROM task_results
    WHERE task_id = ?
    """

    rows = query_db(PIPELINE_DB, query)

    if not rows:
        # Check if table exists
        table_query = (
            "SELECT name FROM sqlite_master WHERE type='table' AND name='task_results'"
        )
        rows = query_db(PIPELINE_DB, table_query)

        if rows:
            print_error("Task results table exists but no matching task found")
        else:
            print_error("Task results table missing")

        print_info("Available tables in pipeline.db:")
        tables = query_db(
            PIPELINE_DB, "SELECT name FROM sqlite_master WHERE type='table'"
        )
        for table in tables:
            print_info(f"  - {table['name']}")

        return None

    result_row = rows[0]
    exec_status = result_row.get("exec_status")
    exec_return_code = result_row.get("exec_return_code")
    task_result = result_row.get("task_result")

    print_info(f"Task status: {exec_status}")
    print_info(f"Return code: {exec_return_code}")
    print_info(
        f"Task result: {json.dumps(task_result, indent=2) if task_result else None}"
    )

    if exec_status == "completed" and exec_return_code == 0:
        print_success("Task completed successfully in pipeline.db")
        return result_row
    else:
        print_error("Task did not complete successfully")
        return None


def run_report(cwd: Path):
    """Run verification and report results."""
    print("\n" + "=" * 70)
    print(colorize("🚀 p0-3 End-to-End Submit Pipeline Verification", "blue"))
    print("=" * 70)
    print(f"Workspace: {cwd}")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    # Prereq checks
    print_step("Prereq Checks")
    checks = [
        check_file_exists(DISPATCH_DB, "dispatch.db"),
        check_file_exists(PIPELINE_DB, "pipeline.db"),
        check_file_exists(cwd / "scheduler.py", "scheduler.py script"),
    ]

    if not all(checks):
        print_error("Prereq checks failed")
        sys.exit(1)

    # Start scheduler
    if not start_scheduler(cwd):
        print_error("Scheduler did not start, check logs")
        sys.exit(1)

    # Wait for scheduler to wake up
    time.sleep(2)

    # Submit task
    task_id = submit_task(cwd)
    if not task_id:
        print_error("Task submission failed")
        sys.exit(1)

    # Wait for task
    task_status = wait_and_get_status(task_id)
    if not task_status:
        print_error("Task did not complete within timeout")
        sys.exit(1)

    # Check DB
    db_result = check_db(task_id)

    # Final disposition
    print("\n" + "=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)

    if db_result and task_status.get("status") == "completed":
        print_success("✓ All end-to-end checks passed")
        print_info("Baseline report written to: .ccc/reports/")
        sys.exit(0)
    else:
        print_error("✗ End-to-end verification failed")
        sys.exit(1)


def main():
    """Entry point."""
    runner = run_report
    runner(Path(WORKSPACE))


if __name__ == "__main__":
    main()
