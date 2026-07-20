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
        "请先建立项目心智再答：依次 Read（按存在）CLAUDE.md、AGENTS.md、.ccc/profile.md、" +
        ".ccc/state.md、README.md；再 bash：git log -5、git status；需要时 Grep/Glob。" +
        "路径以本仓「双机路径」表为准（M1=apps/ 对话副本，2017=apps/ 编排 SSOT）。" +
        "不要上外网，除非我要求。"

    static let mustAnswer =
        "\n\n请现在开始执行，并直接把完整答复写给我。"

    static let builtinPrompts: [(title: String, prompt: String)] = [
        ("下一步", nextStep),
        ("定稿", finalize),
        ("扫风险", scanRisks),
        ("对齐基线", alignBaseline),
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
        "\n继承本会话已聊目标与约束，结合仓库现状给出可拍板建议。\n\n" +
        "请按这个结构回答：\n" +
        "### 判断\n一句：现在最该推进什么。\n" +
        "### 下一步（最多 3 条，按优先级）\n" +
        "1. … — 为什么现在做 / 不做会怎样\n" +
        "2. …\n" +
        "3. …（可省略）\n" +
        "最佳：… — <一句理由>\n" +
        "### 澄清\n最多 1 个问题；没有就写「无」。" +
        mustAnswer

    static let scanRisks =
        "请帮我扫一遍风险。\n" +
        replyCompact + "\n" + investigatePref +
        "\n对照本会话方案与仓库真实状态；无证据不夸大。\n\n" +
        "请按这个结构回答：\n" +
        "### 风险（按严重度，最多 5 条）\n" +
        "- 会怎样坏 / 谁受影响 / 是否挡转任务；无则「无明显风险」\n" +
        "### 建议处理顺序\n1～3 步。\n" +
        "### 可否定稿转任务\n可以 / 暂缓 — <一句理由>" +
        mustAnswer

    static let finalize =
        "请把本会话方案定稿成可转任务的契约包。\n" +
        replyCompact + "\n" + investigatePref +
        "\n先核实仓库能否支撑目标，再写契约。\n\n" +
        "先用 2～4 句白话说明：做什么、验收长什么样、是否建议立刻转任务。\n" +
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
        "### 建议选项\n2～3 个下一步；最佳：… — <理由>\n" +
        "### 可下达任务\n适合转任务的 1 个标题，或不适合时写「先处理：…」" +
        mustAnswer
}
