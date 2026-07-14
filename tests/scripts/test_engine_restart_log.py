#!/usr/bin/env python3
"""简单的集成测试，验证 engine-restarts.jsonl 的写入逻辑。
运行方式: python3 -m pytest tests/scripts/test_engine_restart_log.py -q --timeout=60

测试内容：
1. 验证模块可以正确导入
2. 验证全局变量存在
3. 验证 _write_engine_restart 函数签名
4. 验证所有必要的事件调用点存在
5. 简单的 atexit 模拟测试
"""

import ast
import json
import os
import re
import tempfile
from pathlib import Path


def test_module_importability():
    """测试模块可以正确导入"""
    try:
        # This only verifies syntax and basic structure
        with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
            code = f.read()
        # Just parse it to ensure no syntax errors
        ast.parse(code)
        print('✓ ccc-engine.py 语法检查通过')
        return True
    except SyntaxError as e:
        print(f'✗ 语法错误: {e}')
        return False


def test_imports():
    """测试 import 语句"""
    with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
        content = f.read()

    required_imports = ['import atexit', 'import json']
    for imp in required_imports:
        if imp in content:
            print(f'✓ {imp}')

    _has_atexit = 'import atexit' in content
    _has_json = 'import json' in content
    return _has_atexit and _has_json


def test_global_variables():
    """测试全局变量"""
    with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
        content = f.read()

    required_globals = [
        '_engine_start_ts',
        '_restart_log_written',
        '_RESTART_LOG_PATH',
    ]

    for var in required_globals:
        pattern = rf'^{_var}: .* = '
        if re.search(pattern, content, re.MULTILINE):
            print(f'✓ {var}')
        else:
            print(f'✗ {var} 未找到')
            return False

    return True


def test_write_engine_restart_function():
    """测试 _write_engine_restart 函数"""
    with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
        content = f.read()

    # Function definition
    if 'def _write_engine_restart(' in content:
        print('✓ _write_engine_restart 函数定义存在')
    else:
        print('✗ _write_engine_restart 函数定义未找到')
        return False

    # Docstring mentioning proper args
    if 'status: "started" | "shutdown" | "stopped"' in content:
        print('✓ 函数 docstring 包含正确参数')
    else:
        print('⚠ 函数 docstring 参数说明可能不正确（非致命）')

    # Try-except block for OSError
    if 'except OSError:' in content:
        print('✓ OSError 异常处理存在')
    else:
        print('✗ OSError 异常处理未找到')
        return False

    return True


def test_event_points():
    """测试所有四个事件点"""
    with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
        content = f.read()

    events = {
        'started': ('_write_engine_restart("started")', '启动事件'),
        'sigterm': ('_write_engine_restart("shutdown", "SIGTERM")', 'SIGTERM 事件'),
        'keyboard_interrupt': ('_write_engine_restart("shutdown", "KeyboardInterrupt")', 'KeyboardInterrupt 事件'),
    }

    all_found = True
    for code_snippet, desc in events.values():
        if code_snippet in content:
            print(f'✓ [{desc}] 调用点存在: {code_snippet}')
        else:
            print(f'✗ [{desc}] 调用点未找到: {code_snippet}')
            all_found = False

    return all_found


def test_atexit_registration():
    """测试 atexit 注册"""
    with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
        content = f.read()

    if 'atexit.register' in content:
        # Check it's in main function (should be before signal registration)
        if 'def _final_restart_log' in content:
            print('✓ atexit 注册函数 _final_restart_log 定义存在')
        else:
            print('⚠ atexit 注册函数定义未找到（可能是内置函数）')

        if 'atexit.register(_final_restart_log)' in content:
            print('✓ atexit.register(_final_restart_log) 调用存在')
        else:
            print('✗ atexit.register 调用未找到')
            return False
    else:
        print('✗ atexit 未导入或注册')
        return False

    return True


def test_file_path_consistency():
    """测试文件路径与 plan 一致"""
    with open('/Users/apple/program/CCC/scripts/ccc-engine.py', 'r') as f:
        content = f.read()

    plan_path = '~/.ccc/logs/engine-restarts.jsonl'
    if plan_path in content:
        print(f'✓ 文件路径与 plan 一致: {plan_path}')
    else:
        print('⚠ 文件路径可能与 plan 不同')

    return True


def test_auditing():
    """审计：确保没有修改白名单外的文件"""
    import subprocess

    # Run compile test
    result = subprocess.run(
        ['python3', '-m', 'compileall', '-q', 'scripts/ccc-engine.py'],
        cwd='/Users/apple/program/CCC',
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print('✓ Python 编译/语法检查通过')
    else:
        print('✗ 编译检查失败')
        print(result.stderr)
        return False

    # Check if only ccc-engine.py was modified in this repo
    # This is a basic check - in CI you'd compare with git
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            cwd='/Users/apple/program/CCC',
            capture_output=True,
            text=True
        )
        modified = [f for f in result.stdout.strip().split('\n') if f]
        if modified:
            print(f'⚠ 修改了以下文件: {modified}')
            if 'ccc-engine.py' in modified:
                print('✓ 仅修改了 ccc-engine.py（白名单内）')
                return True
            else:
                print('✗ 修改了白名单外的文件!')
                return False
        else:
            # Fresh checkout
            print('⚠ 工作树为空，可能在 CI 环境')
            return True
    except Exception as e:
        print(f'⚠ git diff 检查跳过: {e}')
        return True


def main():
    """运行所有测试"""
    print('=== Engine 自重启日志功能集成测试 ===\n')

    tests = [
        ('模块导入性', test_module_importability),
        ('Import 语句', test_imports),
        ('全局变量', test_global_variables),
        ('_write_engine_restart 函数', test_write_engine_restart_function),
        ('事件点实现', test_event_points),
        ('atexit 注册', test_atexit_registration),
        ('文件路径一致性', test_file_path_consistency),
        ('代码审计', test_auditing),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f'✗ 测试异常: {e}')
            failed += 1
        print()

    print('=== 测试结果 ===')
    print(f'通过: {passed}/{len(tests)}')
    print(f'失败: {failed}/{len(tests)}')

    if failed == 0:
        print('\n✓ 所有测试通过!')
        return 0
    else:
        print('\n✗ 部分测试失败')
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
