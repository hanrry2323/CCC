import Foundation

/// Hub / Desktop 快捷条语义（内置 + 自定义）
/// 设计：功课对齐 Cursor；结尾必须是明确的用户请求，避免 loop-code 合成 “No response requested.”
enum QuickPrompts {
    static let replyCompact =
        "用中文白话回复我；先结论（≤3 句）后理由。" +
        "不要复述工具过程、不要大段代码、不要裸 JSON（定稿块除外）。" +
        "不要编造未核实的事实。工具跑完后必须写出完整可见答复，" +
        "禁止只回 No response requested 或空内容。" +
        "禁止出现 transfer-outbox、Terminal、cat >、script_seed、opencode、A/B 菜单。"

    static let investigatePref =
        "你是 Desktop 对话面产品搭档（不是 Hub 聊天、不是 Engine 角色）。" +
        "业务仓事实：Hub 基线 + 一等 hub_* 工具 / 透镜 live；M1 无业务源码第二树。" +
        "问看板/在飞/文件必须先 hub_board 等工具；Hub 断则明说不可达，禁止瞎编。" +
        "板堵/残卡：你自己 hub_repair(clear_blockers)，禁止教我贴命令，禁止默认投卫生 epic。" +
        "清 abnormal 不等人审。digest 不作终局于代码细节。" +
        "仅当当前项目是 CCC 平台仓且本机有映射时，才可对本机 CCC 做 Read/git。" +
        "业务仓不可工程师模式；改码请定稿转任务。人审只在定稿/采纳；进队后全自动。" +
        "「对齐基线」是深对齐可选路径，不是定稿/转任务的硬门槛。"

    static let mustAnswer =
        "\n\n请现在开始执行，并直接把完整答复写给我。"

    static let verifyRitual =
        "\n## 现况核实（静默必修 · 勿写入回复正文当过程复述）\n" +
        "作答前必须 hub_board + hub_git（MCP ccc-hub）；" +
        "再按目标 hub_locate/hub_file 定点读 1～3 个关键相对路径。\n" +
        "先内化：ready_for_task / inflight / dirty_kind / pipeline_idle。" +
        "ready_for_task=false 或 inflight>0：先 hub_repair(clear_blockers)，" +
        "再谈产品 epic；仅业务脏/真在飞冲突时禁新产品 epic（人可显式 override）。\n" +
        "禁止把卫生/烟测/README stamp/仅勾 STATUS 当产品主业。\n" +
        "禁止向用户输出 Hub CLI / transfer-outbox / Terminal 教程。\n"

    static let builtinPrompts: [(title: String, prompt: String)] = [
        ("看仓况", nextStep),
        ("定稿", finalize),
        ("扫风险", scanRisks),
        ("对齐基线", alignBaseline),
        ("刷新看板", refreshBoard),
    ]

    private static let customKey = "ccc.customPrompts"

    static func loadCustomPrompts() -> [QuickPromptItem] {
        guard let data = UserDefaults.standard.data(forKey: customKey),
              let items = try? JSONDecoder().decode([QuickPromptItem].self, from: data)
        else { return [] }
        return items
    }

    static func saveCustomPrompts(_ items: [QuickPromptItem]) {
        guard let data = try? JSONEncoder().encode(items) else { return }
        UserDefaults.standard.set(data, forKey: customKey)
    }

    /// 旧名「下一步」：已降级为可选「看仓况」，非下达必经阶段
    static let nextStep =
        "请帮我看一下当前仓况（可选步骤，非定稿必经）。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n继承本会话已聊目标与约束，结合**核实后的**仓库现状给出**最佳方案**并默认按它推进。\n" +
        "不必先点「对齐基线」。板堵先 repair；禁止甩 A/B 菜单让我选；仅当真缺不可逆信息时最多 1 问。\n\n" +
        "请按这个结构回答：\n" +
        "### 判断\n一句：现在最该推进什么（含是否可开工 / 板是否堵；若已 repair 说明结果）。\n" +
        "### 最佳方案\n要做什么、为什么现在做、不做会怎样；默认按此执行。\n" +
        "### 备选（可选，一句）\n若有明显次优，一句带过；不要逼我拍板。" +
        mustAnswer

    static let scanRisks =
        "请帮我扫一遍风险。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n对照本会话方案与仓库真实状态；无证据不夸大。\n\n" +
        "请按这个结构回答：\n" +
        "### 风险（按严重度，最多 5 条）\n" +
        "- 会怎样坏 / 谁受影响 / 是否挡转任务；无则「无明显风险」\n" +
        "### 建议处理顺序\n1～3 步（直接定顺序，勿问我选哪条）。\n" +
        "### 可否定稿转任务\n可以 / 暂缓 — <一句理由>" +
        mustAnswer

    static let finalize =
        "请把本会话方案定稿成可转任务的契约包。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n先核实仓库能否支撑目标，再写契约。板堵先 repair；仅业务脏/真在飞冲突时 feasibility=blocked。\n" +
        "意图已够则**立即定稿**：禁止再列方案选项、禁止问「要不要入队/确认转任务」。\n" +
        "板面残卡优先 repair，勿默认卫生 epic；偶发卫生卡：executor_intent 必须 python。\n" +
        "验收条只写可执行命令或须入 commit 的交付路径；排除列表放 plan「禁止」节，勿写进 acceptance。\n" +
        "提醒：转任务二级卡仅可改标题与备注；goal/acceptance/plan_md/执行面已锁，改方案须退回重定稿。\n\n" +
        "先用 2～4 句白话说明：做什么、验收长什么样、是否建议立刻转任务" +
        "（用户可读结论；不要堆任务 id / 绝对路径）。\n" +
        "然后输出恰好一个 ```ccc-transfer``` JSON 块（title/goal/acceptance/pipeline/" +
        "feasibility/feasibility_reason/executor_intent/plan_md 齐全）。\n" +
        "feasibility 非 ok 时不要怂恿转任务；plan_md 含背景、范围、步骤、验收、风险。" +
        mustAnswer

    /// 备用文案：正常路径走 Hub baseline API（AppModel.alignBaseline）
    static let alignBaseline =
        "请帮我对齐当前项目基线（深对齐 · 可选，非硬门槛）。\n" +
        replyCompact + "\n" + investigatePref +
        verifyRitual +
        "\n若发现 abnormal/failed/幽灵轨：先 `repair … clear_blockers`，再给建议；禁止默认逼卫生 transfer。\n\n" +
        "请按这个结构回答：\n" +
        "### 现状\n- 定位（含版本）\n- 阶段 / 是否可开工（ready / inflight / dirty_kind）\n" +
        "### 风险\n挡下达或发布的事；空板闲置可写正常\n" +
        "### 已做板务（若有）\nrepair 动作与结果\n" +
        "### 建议下一步\n直接给最佳 1 条（含理由）；勿列菜单逼选\n" +
        "### 可下达任务\n适合转任务的 1 个标题，或不适合时写「先处理：…」" +
        mustAnswer

    /// 刷新看板事实：强制走 Hub live lens（sidecar 会注入 board）
    static let refreshBoard =
        "请刷新看板事实：当前权威仓在飞什么？\n" +
        replyCompact + "\n" + investigatePref +
        "\n必须以 Hub live board（as_of + inflight）为准；" +
        "覆盖本会话更早的「全 0 / 无在飞」印象。" +
        "Hub 不可达就明说，禁止瞎编。" +
        "\n\n请按这个结构回答：\n" +
        "### 在飞\n列 planned/in_progress/testing/verified 的 tid 与标题；无则写「无」\n" +
        "### 计数\n各列数字 + as_of\n" +
        "### 说明\n一句：是否与扇出/转任务一致" +
        mustAnswer
}
