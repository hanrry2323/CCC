# cockpit-v0302-files Review

## Verdict: **PASS**

## Size Class: **large** (215 行)

代码功能正确，错误处理完善，安全无虞。发现 4 项低严重度问题：类型标注不准、死数据采集、串行请求增延迟、未按 plan 建 API 路由。通过审查。

## Findings (4 条)

```json
{
  "verdict": "pass",
  "findings": [
    {
      "severity": "low",
      "file": "scripts/ccc-cockpit.py",
      "line": 401,
      "issue": "返回类型标注 `-> dict` 与实际不符——当 board-server 不可达时返回 `None`。类型标注应为 `-> dict | None` 或 `Optional[dict]`。",
      "suggestion": "将 `def _fetch_board_summary() -> dict:` 改为 `def _fetch_board_summary() -> dict | None:`（Python 3.10+）。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-cockpit.py",
      "line": 470,
      "issue": "`_fetch_board_summary` 获取了 `workspaces` 字典并写入返回值，但 `_render_board_section` 从未渲染它——属于死数据采集。",
      "suggestion": "移除 `workspaces` 的采集逻辑以减轻 board-server 负担，或将其渲染为看板工作区下拉/切换控件。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-cockpit.py",
      "line": 397,
      "issue": "`build_cockpit_data()` 串行执行两次 HTTP 请求（/api/board 和 /api/dashboard），每次超时 3s，页面加载最坏增加 6s 延迟。",
      "suggestion": "考虑并行化（`ThreadPoolExecutor`）或合并两次调用为一次，或将 board 数据改为页面 JS 异步加载（`fetch('/api/...')` + 渲染）以避免阻塞页面主渲染。"
    },
    {
      "severity": "low",
      "file": "scripts/ccc-cockpit.py",
      "line": 397,
      "issue": "Plan 要求新增 `GET /api/board` 独立路由，实现采用服务端聚合（_fetch_board_summary 内部直接调用 board-server），未创建 API 端点。功能等价但属架构偏离。",
      "suggestion": "按 plan 补充 `GET /api/board` 路由定义，或将 `_fetch_board_summary` 注册为路由 handler，保持 plan 一致。"
    }
  ],
  "summary": "代码功能正确，错误处理完善，安全无虞。发现 4 项低严重度问题：类型标注不准、死数据采集、串行请求增延迟、未按 plan 建 API 路由。通过审查。"
}
```
