import Foundation

/// Hub / Desktop 快捷条语义（内置 + 自定义）
/// 设计：功课深度对齐 Cursor Agent；对用户仍用中文可拍板表达。
enum QuickPrompts {
    /// 共用：静默深查 + 可见答复纪律（不再用字数硬阉割智能）
    static let replyCompact =
        "【对用户回复】中文白话；先结论后理由；像 Cursor Agent 一样先核实再说话。" +
        "禁止复述工具过程、大段代码、裸 JSON（定稿块除外）。" +
        "路径仅在拍板必需时点到关键处；可用短模块名。禁止编造未读到的事实。"

    static let investigatePref =
        "【静默功课 · 必须执行】先 Read/Glob/Grep 本仓库关键文件；" +
        "需要时 Bash：`git log -5`、`git status`；交叉验证 CLAUDE.md / .ccc/profile.md / .ccc/state.md。" +
        "state 可能滞后，以 git 与现文件为准。不要 WebFetch，除非用户要外网。"

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
        replyCompact + "\n" + investigatePref +
        "\n\n# 任务：给出「下一步」——可拍板的产品/架构建议\n" +
        "继承本会话已聊目标与约束；结合仓库现状，像 Cursor 一样想清楚再答。\n\n" +
        "## 输出\n" +
        "### 判断\n" +
        "一句：现在最该推进什么（业务语言）。\n" +
        "### 下一步（最多 3 条，按优先级）\n" +
        "1. … — 为什么现在做 / 不做会怎样\n" +
        "2. …\n" +
        "3. …（可省略）\n" +
        "最佳：… — <一句场景理由>\n" +
        "### 澄清（可选）\n" +
        "最多 1 个关键问题；没有就写「无」。\n"

    static let scanRisks =
        replyCompact + "\n" + investigatePref +
        "\n\n# 任务：扫风险（发布/场景/下达可行性，不是技术名词清单）\n" +
        "对照本会话方案 + 仓库真实状态；无证据不夸大。\n\n" +
        "## 输出\n" +
        "### 风险（按严重度，最多 5 条）\n" +
        "- 用「会怎样坏 / 谁受影响 / 是否挡转任务」描述；无则「无明显风险」\n" +
        "### 建议处理顺序\n" +
        "1～3 步，业务语言。\n" +
        "### 可否定稿转任务\n" +
        "可以 / 暂缓 — <一句理由>\n"

    static let finalize =
        replyCompact + "\n" + investigatePref +
        "\n\n# 任务：定稿为可投递 CCC 的契约包（转任务前置）\n" +
        "把本会话方案收成 **一条可执行 epic**。先核实仓库是否支撑目标，再写契约。\n\n" +
        "## 步骤\n" +
        "1. 确认 title/goal/acceptance 够具体、可验收；缺关键信息则先问 1 个问题（不要硬编）。\n" +
        "2. 评估 feasibility：`ok` 或 `blocked`（blocked 必须写清原因，且不要怂恿转任务）。\n" +
        "3. `plan_md` 写成 Cursor 级短计划：背景、范围（做/不做）、步骤、验收、风险。\n" +
        "4. 白话结论后，输出**恰好一个** `ccc-transfer` fenced JSON 块（字段齐全）。\n\n" +
        "## 块外\n" +
        "2～4 句：做什么、验收长什么样、是否建议立刻转任务。\n" +
        "块内允许路径与验收命令。不要前后工程师解说。\n"

    /// 备用文案：正常路径走 Hub baseline API（AppModel.alignBaseline）
    static let alignBaseline =
        replyCompact + "\n" + investigatePref +
        "\n\n# 任务：对齐当前项目基线\n" +
        "读 CLAUDE.md、README、.ccc/profile.md、.ccc/state.md，并 `git log -5` 交叉验证。\n\n" +
        "## 输出\n" +
        "### 现状\n" +
        "- 项目定位（含版本若有）\n" +
        "- 当前阶段 / 是否可开工\n" +
        "### 风险\n" +
        "- 挡下达或发布的事；空板+闲置可写正常\n" +
        "### 建议选项\n" +
        "- 2～3 个下一步；`最佳：… — <理由>`\n" +
        "### 可下达任务\n" +
        "- 适合人确认后转任务的 1 个标题；或不适合时写「先处理：…」\n"
}
