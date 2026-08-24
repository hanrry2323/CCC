# 任务卡 ccc075 · 看板 /cards 项目可见性修复——xy/mx/qb/tst 全部消失根因（DSH 执行）

> 关联：无方案（2026-08-24 老板指令直派） · 执行体：DSH · 验收：DSH · 状态：待分派 · 派发：engine · 项目：ccc · 日期：2026-08-24

## 目标

2026-08-24 实证：`GET /cards` 仅返回 cd/cla/clw/hp 四项目共 50 张，xy/mx/qb/tst/ccc 全部不可见；而进程内直接调 `load_dispatch_cards('docs/dispatch')` 返回 207 张含全部项目。老板在前端页面看不到新投递卡（含五张债务卡），直接影响「盯板」。定位根因并修复，使看板恢复全项目可见。

## 已知事实（调查起点）

- `server/board/loader.py` L180：平台前缀（ccc，category=platform）默认被扫描器跳过——**ccc 卡不上看板属设计**，不在本卡范围（如需可见性另立产品决策）。
- 异常点在 web-server 进程内：`_load_board_items()` 调同一 loader 却只得到四项目子集 → 嫌疑集中在 `_DISPATCH_DIR`/`get_index_path()` 的环境差异（launchd 环境无 DATA_DIR 时回退 `Path(__file__)/../../data`，而 web-server 以 launchd 启动时 `__file__` 所指安装路径可能非本仓）、或 `_compose_board_items` 合成层丢项、或 20s 板级缓存键未含数据集标识。
- 复现命令：`curl -s http://127.0.0.1:7788/cards | python3 -c "…按 project 计数"` 对比同机 python 直调 loader。

## 实现

白名单：server/web/server.py。

1. 定位：打印/记录 web-server 进程内 `_DISPATCH_DIR`、`get_index_path()` 解析结果与逐项目计数（临时诊断日志可留 INFO 级）。
2. 修复：使卡片加载路径解析与仓库实际位置强绑定（如以模块文件位置推导 dispatch 根，或显式配置项指向本仓 docs/dispatch），消除对启动 cwd/环境的隐性依赖；确保 xy/mx/qb/tst 全量入板。
3. 若根因在缓存键：把 dispatch 根绝对路径纳入 `_BOARD_CACHE_KEY` 组成。
4. 回归：重启 web-server 后 `/cards` 按项目计数覆盖全部 taskable 项目；既有四项目数量不减少。

## 红线（先看）

1. 白名单外零触碰；不改 loader 公共语义（ccc 平台豁免保持）。
2. 不改变 /cards 既有响应字段结构，仅扩充可见集合。
3. 禁写机审区/验收区/置已关闭。

## 红线补充说明

门禁第二条需 web-server 已载入修复后代码（本地验证时可手动重启 com.ccc.web-server 或以调试实例 :7899 验证）；wrapper 截获以第一条 pytest 为准，第二条作为部署后人工复核项。

## 步骤

1. Read 本卡全文 + server/web/server.py 卡片加载/缓存区段 + launchd plist（com.ccc.web-server）。
2. 定位并按实现节修复；单测/整文件 pytest 绿。
3. commit+push 到分支（push 前 fetch+rebase origin/main）。
4. 卡头改「已回写」并填回写区；维护区四问——勾选符落在问题行方括号内，说明行一句实情。
5. 停手等机审。

## 验收标准

1. 门禁命令真实退出码=0。
2. 修复后 /cards 项目集合 ⊇ {cd,cla,clw,hp,xy,mx,qb,tst} 且总数 ≥207-已关闭裁剪。
3. 白名单外零触碰；维护区四问非占位。

## 门禁

测试：cd /Users/fan/program/CCC-wt/ccc075 2>/dev/null || cd /Users/fan/program/CCC; python3 -m pytest server/tests/test_plans.py -q && python3 -c "import urllib.request,json;d=json.load(urllib.request.urlopen('http://127.0.0.1:7788/cards'));cards=d if isinstance(d,list) else (d.get('cards') or d.get('data') or []);ps={str(c.get('project')) for c in cards if isinstance(c,dict)};print(ps);raise SystemExit(0 if {'xy','mx','qb'} <= ps else 1)"

## 回写区

（执行体回写）

## 机审区

（验收席专用——执行体禁止写入）

## 维护区

> 完成钩子（Doc-Gate）：回写时必须逐项勾选填写，禁止留占位。

1. **方案同步**：[否]
   - 说明：[否]。平台看板可见性直派修复卡，无关联方案。
2. **教训沉淀**：[有/无]
   - 说明：（回写时据实填写；若[有]须新增 notes 文件）
3. **档案/README**：[否]
   - 说明：[否]。行为修复不改结构。
4. **线路图**：[否]
   - 说明：[否]。
