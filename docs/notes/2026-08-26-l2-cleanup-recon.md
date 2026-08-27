# CCC 第二层清理 · 全项目摸底总报告（2026-08-26）

> 外脑指令直派 · 7路子代理并行只读侦察 · 全程零写操作 · 密钥只报存在不读内容
> 调度：DSH 会话；范围：registry 在册且 mac2017 有路径的 9 仓 + 特殊目标
> 已办结：ai-loop-router 停用转档案（commit a19aaf5c0，运行时本就无残留）

## 一、总览表

| 项目 | git卫生 | 立可回收 | 需定夺大项数 |
|---|---|---|---|
| hp | 健康 | **1.47G**（tmp_pack garbage ×2）| 5（含🔴凭据进史）|
| clwarp(clw) 封板 | 良好 | **6.9G**（Rust构建缓存+dmg拷出留档）| 3（stash×11等）|
| xianyu(xy) | 极佳 | **~212M**（ignored渲染产物+缓存）| 4（大件已进git史）|
| qb | 极佳 | 0（logs被服务fd持有）| 3（logs959M轮转/stash×45/口径）|
| clawmed-ccc(cla) | 极佳 | ~600K | 6（档案归属/活跃数据/tracked遗留）|
| medio-0(mx) | 全平台最净 | <1MB | 2（target/22G、main上游缺配）|
| ccc-demo(cd) 废除 | 与远端全同步 | 目录级（26M）| 1（.ccc 3M本地独有史档）|
| ccc-tst(tst) | 双仓自洽全净 | 0 | registry声明脱节 |
| qx-observer | archived | — | 159条未提交改动定性 |

## 二、【第二批·可直接执行】（无需定夺，预计回收 ≈8.6G）

1. hp：删 `.git/objects/pack/tmp_pack_VpcuM4`(684M)+`tmp_pack_sOIQA4`(828M)——git 自证 garbage
2. clwarp：删 `src-tauri/target/`(6.9G)+`dist/`(556K)；执行前拷出 `clwarp_0.3.0_x64.dmg`(4.2M) 至归档
3. xy：删 `video-pipeline/output/`(181M)、`.mypy_cache`/`.pytest_cache`/`.ruff_cache`/`.coverage`(~31M)、`workspace/outputs/`
4. cla：删 `.ccc/quarantines/`(300K)、两工具缓存、push-fail残片×13、flow-smoke.md
5. mx：删根级 frontend/(724K 兜底产物)、cobertura.xml、pycache、exec.log×2
6. cd：待D5批复后整目录处置

## 三、【需老板逐项定夺】（编号供批复）

- D1🔴 hp `.env.bak-2026-06-19` 已进 git 历史（4bc13fd）→ 建议无论是否重写历史都轮换对应凭据【安全】
- D2 remote-hp 生产仓（hp@hp:/data/knowledge）：12条 codex/hp009~042 死卡分支清理（可释~1.7G）+ 服务器 main 落后 GitHub 待同步【涉生产仓】
- D3 xy 大件：renders/ 168M 与 .ccc/ 473文件已 tracked（须 git rm+commit 流程）；samples/ 259M tracked MP4（瘦身需 filter-repo 破坏性重写）；.git 松散对象 227M（择机 gc --aggressive）
- D4 stash 债合计 59 条：qb×45（07-27~08-01 自动残留）、clw×11（开发期WIP）、hp×3——抽查后统一 clear
- D5 ccc-demo 整目录退役删除（26M；.ccc/ 下 3.0M 本地独有管线史档是否先备份）
- D6 qx-observer：159 条未提交改动是废弃残留还是有意封存快照
- D7 mx：target/ 22G 是否 cargo clean（代价全量重建）；main 上游未配置补 set-upstream-to
- D8 registry 批量修正：①isolation.worktree_root 声明批量失效（.ccc-wt/ 全平台不存在，涉 tst/cd/qb/mx/xy/hp/cla 七仓）②qb「可能无远端」备注过时（实际有 origin 且同步）③qx-map/qh 在 M1 机本轮不可达备注
- D9 clawmed 定夺族：最后任务(07-30)完整执行档案存删、data/llm_usage.json（今日仍写入）入库或ignore、tracked 遗留 MARKER_OBS5.txt、README自认历史骨架 run_crawler.py 删否
- D10 运行态异常确认：hp 服务 8082/8083 当前均无监听（与常驻预期不符）；qb order-gateway last exit=1（存活但曾异常退出）

## 四、跨仓共性发现

1. 分支债 = **零**：九仓全部单 main 或仅 main+origin/main，无一条垃圾本地/远端分支（CCC 第一批已清完 codex/*）
2. 未推/未拉漂移 = **零**：所有仓与各自 origin 完全对齐（唯 remote-hp 生产仓例外，见 D2）
3. worktree 残留 = **零**：.ccc-wt/ 全平台不存在（衍生 D8 登记修正）
4. 密钥落盘 = 仅 hp 一处进史（D1）；其余仓 .env 类均正常 ignore 且未读内容
5. 体量三巨头：xy.git 松散对象227M、hp .git 3.2G、mx target/ 22G

## 五、附：各仓侦察明细出处

七路子代理原始报告（含全部复现命令）已在调度会话存档；本文件为汇总层。
