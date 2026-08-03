import Foundation

/// Desktop 快捷条语义（内置 + 自定义）
/// v0.65：UI 只保留「对齐基线」「扫风险」；意图链由 Agent 理解后自动投出（勿靠人点转意图卡）。
enum QuickPrompts {
    static let replyCompact =
        "用中文白话回复我；先结论（≤3 句）后理由。" +
        "不要复述工具过程、不要大段代码、不要裸 JSON（意图卡契约块除外）。" +
        "不要编造未核实的事实。工具跑完后必须写出完整可见答复，" +
        "禁止只回 No response requested 或空内容。" +
        "禁止出现 Terminal、cat >、script_seed、opencode、A/B 菜单。"

    static let investigatePref =
        "你是 Desktop **高级智能开发伙伴 · 架构师**（分析→架构→理解意图→**自动投意图链**→读测纠偏→连续优化；可查 HP/社区；板务仅挡事时；不是 Engine 本身）。" +
        "主交付 = 有序阶段路线图 + 失败自动纠正；禁止默认缩成单功能闲聊。" +
        "业务仓事实：服务端基线 + 一等 hub_* 工具 / 透镜 live；M1 无业务源码第二树。" +
        "问看板/在飞/文件必须先 hub_board 等工具；服务端断则明说不可达，禁止瞎编。" +
        "板堵/残卡/失败：本会话 hub_repair + 读 failure_pack；耗尽则**自动**优化意图卡并投链；禁止甩锅「打开编排运维」；禁止教贴命令；禁止卫生 epic；禁止 invent。" +
        "本机 Read/Write/git 仅限 CCC 平台仓；业务改码经意图卡→Engine。" +
        "意图收敛后**自动**出 ccc-transfer（系统 gate 绿→进代办）；**禁止**等人点「转意图卡」按钮。" +
        "「对齐基线」= 分析并排系列计划的可选深扫，不是投链硬门槛。"

    static let mustAnswer =
        "\n\n请现在开始执行，并直接把完整答复写给我。"

    static let verifyRitual =
        "\n## 现况核实（静默必修 · 勿写入回复正文当过程复述）\n" +
        "作答前必须 hub_board + hub_git（MCP ccc-hub）；" +
        "再按目标 hub_locate/hub_file 定点读 1～3 个关键相对路径。\n" +
        "先内化：ready_for_task / inflight / dirty_kind / pipeline_idle。" +
        "ready_for_task=false 或 inflight>0（非纯业务脏）：hub_repair(clear_blockers)，" +
        "再谈产品意图；仅业务脏/真在飞冲突时禁新产品（人可显式 override）。\n" +
        "禁止把卫生/烟测/README stamp/仅勾 STATUS 当产品主业。\n" +
        "禁止向用户输出 MCP CLI / Terminal 教程。\n"

    /// 内部保留：自动投链 / 用户口述「开发/下达」时注入用（无 UI 按钮）
    static let nextStep =
        "请帮我看一下当前仓况（可选，非主路径）。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n继承本会话已聊目标与约束，结合**核实后的**仓库现状给出**最佳方案**并默认按它推进。\n" +
        "板堵先 repair；禁止甩 A/B 菜单；意图已收敛则直接出 ccc-transfer 自动投链。\n\n" +
        "请按这个结构回答：\n" +
        "### 判断\n一句：现在最该推进什么。\n" +
        "### 最佳方案\n要做什么、为什么现在做；默认按此执行。\n" +
        "### 备选（可选，一句）\n若有明显次优，一句带过。" +
        mustAnswer

    static let scanRisks =
        "请帮我扫一遍风险。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n对照本会话方案与仓库真实状态；无证据不夸大。\n\n" +
        "请按这个结构回答：\n" +
        "### 风险（按严重度，最多 5 条）\n" +
        "- 会怎样坏 / 谁受影响 / 是否挡意图链；无则「无明显风险」\n" +
        "### 建议处理顺序\n1～3 步（直接定顺序，勿问我选哪条）。\n" +
        "### 可否投意图链\n可以 / 暂缓 — <一句理由>" +
        mustAnswer

    /// 内部：Agent 自动投链文案（无「转意图卡」按钮；用户说开发/下达时等同）
    static let finalize =
        "把本会话已排妥的**系列开发计划**一次性落成整条意图卡链并推动进代办（系统自动路径，勿等人点按钮）。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n严格按 `references/intent-card-sop.md` + `references/intent-chain-dev-sop.md`。\n" +
        "**收敛门**：整条路线未齐（阶段/怎样算完）→ 只回白话缺什么并拒投。\n" +
        "已收敛：**禁止**再问要不要入队；**禁止**只落当前首刀、丢掉后续阶段。\n" +
        "**多卡硬规则**：系列计划 ≥2 步 → 必须多个 ```ccc-transfer``` " +
        "或一块 JSON `cards:[...]`（每卡 1 阶段意图 · 1 phase · 1～2 强探针）；" +
        "真·单意图才允许单块。系统逐卡 gate→进代办→wake Engine。\n" +
        "硬完成：可见答复里必须有可过门契约块；禁只写 L1 交差。\n" +
        "板堵先 repair；偶发卫生卡 executor_intent=python。\n\n" +
        "### 每卡硬预算\n" +
        "- scope≤5 文件同顶层；acceptance 1～2 条本卡强探针（pytest/DRY_RUN/assert）\n" +
        "- ❌ test -f、散文、unit+paper 混装、把下一意图塞本卡、敏感路径(.env/密钥)\n" +
        "- plan_md 必有 ## 验收；title≤80；默认 medium\n\n" +
        "白话 2～4 句：整条计划拆成几张、每张怎样算完。\n" +
        "然后输出全部契约块（技术字段只进块内）。起草前读 digest 教训 + next_product_goal。\n" +
        mustAnswer

    /// 备用文案：正常路径走服务端 baseline API（AppModel.alignBaseline）
    static let alignBaseline =
        "请对齐项目基线。你是高级智能开发伙伴·架构师：分析项目并交付**系列开发计划**（3～7 步到收口），不是讨论一个功能。\n" +
        replyCompact + "\n" +
        "直接四段白话；禁止工具旁白；本轮禁止 ccc-transfer；禁止缩成单点补丁。\n" +
        "细则 references/align-baseline-sop.md。\n\n" +
        "### 项目与进度\n定位 + 走到哪 + 能否开系列计划\n" +
        "### 该留意什么\n只挡整条路线/发布；无则「当前没有挡事的异常」\n" +
        "### 开发计划（系列）\n3～7 步有序阶段；标明当前首刀与依赖；每步产品结果\n" +
        "### 若要落成意图卡链\n1/N… 白话标题 ≤20 字（人确认路线后你自动投链，勿等人点按钮）" +
        mustAnswer

    /// 内部保留：无 UI 按钮；Agent 可自行 hub_board 刷新
    static let refreshBoard =
        "请刷新看板事实：当前权威仓在飞什么？\n" +
        replyCompact + "\n" + investigatePref +
        "\n必须以服务端 live board（as_of + inflight）为准；" +
        "覆盖本会话更早的「全 0 / 无在飞」印象。" +
        "服务端不可达就明说，禁止瞎编。" +
        "\n\n请按这个结构回答：\n" +
        "### 在飞\n列 planned/in_progress/testing/verified 的 tid 与标题；无则写「无」\n" +
        "### 计数\n各列数字 + as_of\n" +
        "### 说明\n一句：是否与意图卡/代办一致" +
        mustAnswer
}
