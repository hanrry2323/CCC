# debt-dead-scripts 执行报告

## 信息
- Phase: debt-dead-scripts-p1
- Timeout: 300s
- 退出码: 1
- 时长: -

## stdout
```

```

## stderr
```
Traceback (most recent call last):
  File "/Users/apple/program/CCC/scripts/opencode-exec.py", line 206, in <module>
    sys.exit(asyncio.run(main()))
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/asyncio/runners.py", line 44, in run
    return loop.run_until_complete(main)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/asyncio/base_events.py", line 642, in run_until_complete
    return future.result()
  File "/Users/apple/program/CCC/scripts/opencode-exec.py", line 199, in main
    result = await run_opencode(args.phase, prompt_text, args.timeout, args.cwd)
  File "/Users/apple/program/CCC/scripts/opencode-exec.py", line 107, in run_opencode
    proc = await asyncio.create_subprocess_exec(
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/asyncio/subprocess.py", line 236, in create_subprocess_exec
    trans
```
