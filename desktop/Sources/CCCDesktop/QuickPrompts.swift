import Foundation

/// Hub / Desktop 快捷条语义（内置 + 自定义）
/// 设计：功课对齐 Cursor；结尾必须是明确的用户请求，避免 loop-code 合成 “No response requested.”
enum QuickPrompts {
    static let replyCompact =
        "用中文白话回复我；先结论后理由。" +
        "不要复述工具过程、不要大段代码、不要裸 JSON（定稿块除外）。" +
        "不要编造未核实的事实。工具跑完后必须写出完整可见答复，" +
        "禁止只回 No response requested 或空内容。"

    static let investigatePref =
        "你是 Desktop 对话面产品搭档（不是 Hub 聊天、不是 Engine 角色）。" +
        "业务仓事实：Hub 基线开场 + Hub 只读透镜 live（ccc-hub-lens / lens API）；M1 无业务源码第二树。" +
        "问看板/在飞/文件必须先透镜；Hub 断则明说不可达，禁止瞎编。" +
        "若本轮已注入 live board / 快照，直接据此作答；禁止对本机跑 git / Read 业务树再核实（会串台）。" +
        "仅当当前项目是 CCC 平台仓且本机有映射时，才可对本机 CCC 做 Read/git。" +
        "业务仓不可工程师模式；改码请定稿转任务。人审只在定稿/采纳；进队后全自动。不要上外网，除非我要求。"

    static let mustAnswer =
        "\n\n请现在开始执行，并直接把完整答复写给我。"

    static let builtinPrompts: [(title: String, prompt: String)] = [
        ("下一步", nextStep),
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

    static let nextStep =
        "请帮我规划「下一步」。\n" +
        replyCompact + "\n" + investigatePref +
        "\n继承本会话已聊目标与约束，结合仓库现状给出**最佳方案**并默认按它推进。\n" +
        "禁止甩 A/B 菜单让我选；仅当真缺不可逆信息时最多 1 问。\n\n" +
        "请按这个结构回答：\n" +
        "### 判断\n一句：现在最该推进什么。\n" +
        "### 最佳方案\n要做什么、为什么现在做、不做会怎样；默认按此执行。\n" +
        "### 备选（可选，一句）\n若有明显次优，一句带过；不要逼我拍板。" +
        mustAnswer

    static let scanRisks =
        "请帮我扫一遍风险。\n" +
        replyCompact + "\n" + investigatePref +
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
        "\n先核实仓库能否支撑目标，再写契约。\n" +
        "意图已够则**立即定稿**：禁止再列方案选项或问我选哪条。\n\n" +
        "先用 2～4 句白话说明：做什么、验收长什么样、是否建议立刻转任务" +
        "（用户可读结论；不要堆任务 id / 绝对路径）。\n" +
        "然后输出恰好一个 ```ccc-transfer``` JSON 块（title/goal/acceptance/pipeline/" +
        "feasibility/feasibility_reason/executor_intent/plan_md 齐全）。\n" +
        "feasibility 非 ok 时不要怂恿转任务；plan_md 含背景、范围、步骤、验收、风险。" +
        mustAnswer

    /// 备用文案：正常路径走 Hub baseline API（AppModel.alignBaseline）
    static let alignBaseline =
        "请帮我对齐当前项目基线。\n" +
        replyCompact + "\n" + investigatePref +
        "\n\n请按这个结构回答：\n" +
        "### 现状\n- 定位（含版本）\n- 阶段 / 是否可开工\n" +
        "### 风险\n挡下达或发布的事；空板闲置可写正常\n" +
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
