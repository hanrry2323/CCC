import XCTest
@testable import CCCDesktop

/// 行为锁 · 解析层：TransferDraftParser / TransferDraft 定稿协议
/// 锁定「助手正文 → TransferDraft」的契约（对齐 transfer-gate.md / transfer_gate.py）
final class TransferDraftParserTests: XCTestCase {

    private func fence(_ json: String) -> String {
        "```ccc-transfer\n\(json)\n```"
    }

    // MARK: - parse 单块

    func testParseSingleFence() throws {
        let content = fence(#"{"title":"Fix login","goal":"Make login work","acceptance":["A","B"],"pipeline":"dev"}"#)
        let d = try XCTUnwrap(TransferDraftParser.parse(from: content))
        XCTAssertEqual(d.title, "Fix login")
        XCTAssertEqual(d.goal, "Make login work")
        XCTAssertEqual(d.acceptanceLines, ["A", "B"])
        XCTAssertEqual(d.pipeline, "dev")
        XCTAssertEqual(d.source, "ccc-transfer")
        XCTAssertTrue(d.isGateReady)
    }

    func testParseNoFenceReturnsNil() {
        XCTAssertNil(TransferDraftParser.parse(from: "plain text with no fence"))
        XCTAssertNil(TransferDraftParser.parse(from: ""))
        // 非 ccc-transfer 语言的 fence 不算
        XCTAssertNil(TransferDraftParser.parse(from: "```json\n{\"title\":\"x\"}\n```"))
    }

    func testParseMultipleFencesTakesFirst() throws {
        let content = fence(#"{"title":"first","goal":"g1"}"#) + "\n\n" + fence(#"{"title":"second","goal":"g2"}"#)
        let d = try XCTUnwrap(TransferDraftParser.parse(from: content))
        XCTAssertEqual(d.title, "first")
        XCTAssertEqual(TransferDraftParser.parseAll(from: content).count, 2)
    }

    func testParseMalformedJSONInsideFenceReturnsNil() {
        let content = fence("not json at all")
        XCTAssertNil(TransferDraftParser.parse(from: content))
    }

    func testParseLanguageCaseInsensitive() throws {
        let content = "```CCC-Transfer\n{\"title\":\"t\",\"goal\":\"g\"}\n```"
        let d = try XCTUnwrap(TransferDraftParser.parse(from: content))
        XCTAssertEqual(d.title, "t")
    }

    // MARK: - parseAll 多块 / cards 展开

    func testParseAllOrderPreserved() {
        let content = fence(#"{"title":"one","goal":"g1"}"#) + "\n\n" + fence(#"{"title":"two","goal":"g2"}"#)
        let all = TransferDraftParser.parseAll(from: content)
        XCTAssertEqual(all.map(\.title), ["one", "two"])
    }

    func testParseAllCardsExpansion() {
        let json = #"{"cards":[{"title":"card1","goal":"g1"},{"title":"card2","goal":"g2"}]}"#
        let all = TransferDraftParser.parseAll(from: fence(json))
        XCTAssertEqual(all.map(\.title), ["card1", "card2"])
    }

    func testParseAllEmptyCardsIgnored() {
        let json = #"{"title":"solo","goal":"g"}"#
        let all = TransferDraftParser.parseAll(from: fence(json))
        XCTAssertEqual(all.map(\.title), ["solo"])
    }

    func testParseAllEmptyFenceAloneYieldsNothing() {
        // 空 body 的 fence 单独存在 → 无有效块
        let content = "```ccc-transfer\n\n```"
        XCTAssertTrue(TransferDraftParser.parseAll(from: content).isEmpty)
    }

    func testParseAllEmptyFenceConsumesFollowingBlocks() {
        // 现状锁定：空 body 的 fence 后接有效块时，非贪婪匹配会把后续内容吞进第一个 body，
        // 导致整段 JSON 解析失败（[]）。非理想但为当前真实行为，暂不改变（行为锁）。
        let content = "```ccc-transfer\n\n```\n\n```ccc-transfer\n{\"title\":\"t\",\"goal\":\"g\"}\n```"
        let all = TransferDraftParser.parseAll(from: content)
        XCTAssertTrue(all.isEmpty)
    }

    // MARK: - draftFromObject 字段映射

    func testFieldsTrimmedAndDefaults() throws {
        let json = #"{"title":"  spaced  ","goal":" goal ","acceptance":[" a ","b"]}"#
        let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(json)))
        XCTAssertEqual(d.title, "spaced")
        XCTAssertEqual(d.goal, "goal")
        XCTAssertEqual(d.pipeline, "dev")          // default
        XCTAssertEqual(d.feasibility, "ok")        // default
        XCTAssertEqual(d.executorIntent, "opencode") // default
        XCTAssertEqual(d.complexity, "medium")     // default
        XCTAssertEqual(d.acceptanceLines, ["a", "b"])
    }

    func testFeasibilityAndExecutorLowercased() throws {
        let json = #"{"title":"t","goal":"g","feasibility":"OK","executor_intent":"OpenCode"}"#
        let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(json)))
        XCTAssertEqual(d.feasibility, "ok")
        XCTAssertEqual(d.executorIntent, "opencode")
    }

    func testSkillRefAndPromptRefCasePreserved() throws {
        // skill_ref/prompt_ref 是库路径引用：大小写敏感，勿 lowercase
        let json = #"{"title":"t","goal":"g","skill_ref":"Skills/Write-Code","prompt_ref":"Prompts/X"}"#
        let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(json)))
        XCTAssertEqual(d.skillRef, "Skills/Write-Code")
        XCTAssertEqual(d.promptRef, "Prompts/X")
    }

    func testBumpVersionBoolAndStringForms() throws {
        let boolTrue = try XCTUnwrap(TransferDraftParser.parse(from: fence(#"{"title":"t","goal":"g","bump_version":true}"#)))
        XCTAssertTrue(boolTrue.bumpVersion)
        let boolFalse = try XCTUnwrap(TransferDraftParser.parse(from: fence(#"{"title":"t","goal":"g","bump_version":false}"#)))
        XCTAssertFalse(boolFalse.bumpVersion)

        for s in ["true", "True", "1", "yes"] {
            let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(#"{"title":"t","goal":"g","bump_version":"\#(s)"}"#)))
            XCTAssertTrue(d.bumpVersion, "string \(s) should map to true")
        }
        for s in ["false", "0", "no", ""] {
            let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(#"{"title":"t","goal":"g","bump_version":"\#(s)"}"#)))
            XCTAssertFalse(d.bumpVersion, "string \(s) should map to false")
        }
    }

    func testAcceptanceArrayTrimFilterJoin() throws {
        let json = #"{"title":"t","goal":"g","acceptance":["  A  ","B","","  C  "]}"#
        let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(json)))
        XCTAssertEqual(d.acceptance, "A\nB\nC")
        XCTAssertEqual(d.acceptanceLines, ["A", "B", "C"])
    }

    func testAcceptanceStringForm() throws {
        let json = #"{"title":"t","goal":"g","acceptance":"A\nB"}"#
        let d = try XCTUnwrap(TransferDraftParser.parse(from: fence(json)))
        XCTAssertEqual(d.acceptanceLines, ["A", "B"])
    }

    func testEmptyTitleAndGoalReturnsNil() {
        XCTAssertNil(TransferDraftParser.parse(from: fence(#"{"title":"","goal":"","acceptance":["x"]}"#)))
        XCTAssertNil(TransferDraftParser.parse(from: fence(#"{"acceptance":["x"]}"#)))
        // 只要 title 或 goal 有一个非空即可
        XCTAssertNotNil(TransferDraftParser.parse(from: fence(#"{"title":"t","goal":""}"#)))
    }

    // MARK: - isGateReady / acceptanceLines / previewLine

    func testIsGateReadyRequiresAllFields() throws {
        let ready = try XCTUnwrap(TransferDraftParser.parse(
            from: fence(#"{"title":"t","goal":"g","acceptance":["a"],"feasibility":"ok"}"#)
        ))
        XCTAssertTrue(ready.isGateReady)

        var noAcc = ready; noAcc.acceptance = ""
        XCTAssertFalse(noAcc.isGateReady)

        var blocked = ready; blocked.feasibility = "blocked"
        XCTAssertFalse(blocked.isGateReady)

        var noTitle = ready; noTitle.title = "   "
        XCTAssertFalse(noTitle.isGateReady)

        var noPipeline = ready; noPipeline.pipeline = ""
        XCTAssertFalse(noPipeline.isGateReady)
    }

    func testAcceptanceLinesTrimsAndFiltersEmpty() {
        let d = TransferDraft(acceptance: "  A  \n\n B \n")
        XCTAssertEqual(d.acceptanceLines, ["A", "B"])
    }

    func testPreviewLineTitlePreferredElseGoalPrefix60() {
        var d = TransferDraft(title: "Long title here", goal: "goal")
        XCTAssertEqual(d.previewLine, "Long title here")

        d.title = "   "
        d.goal = String(repeating: "x", count: 100)
        XCTAssertEqual(d.previewLine, String(repeating: "x", count: 60))
    }

    // MARK: - stripTransferFence / humanVisibleMarkdown / transferFenceJSON

    func testStripTransferFenceRemovesBlocks() {
        // fence 前后各留一个换行（fence 尾部 "\n```" 前的换行 + 后文换行）→ 现状保留空白行
        let content = "intro\n" + fence(#"{"title":"t","goal":"g"}"#) + "\noutro"
        let stripped = TransferDraftParser.stripTransferFence(content)
        XCTAssertEqual(stripped, "intro\n\noutro")
    }

    func testStripTransferFenceNoFenceUnchanged() {
        XCTAssertEqual(TransferDraftParser.stripTransferFence("  hello world  "), "hello world")
    }

    func testHumanVisibleMarkdownStripsFence() {
        let content = "前文\n" + fence(#"{"title":"t","goal":"g"}"#)
        XCTAssertEqual(TransferDraftParser.humanVisibleMarkdown(from: content), "前文")
    }

    func testTransferFenceJSONReturnsBody() throws {
        let content = fence(#"{"title":"t","goal":"g"}"#)
        let body = try XCTUnwrap(TransferDraftParser.transferFenceJSON(from: content))
        XCTAssertTrue(body.contains(#""title""#))
        XCTAssertTrue(body.contains(#""t""#))
    }

    func testTransferFenceJSONNilWhenAbsent() {
        XCTAssertNil(TransferDraftParser.transferFenceJSON(from: "no fence"))
    }
}
