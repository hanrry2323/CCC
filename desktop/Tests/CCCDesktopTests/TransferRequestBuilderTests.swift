import XCTest
@testable import CCCDesktop

/// 拆分前后行为一致证据：TransferRequestBuilder
/// 期望值 = 搬迁前 AppModel 内联表达式（createManualEpic / promoteIntentCardToBacklog / submitTransfer）
/// 断言 builder 输出与内联结果全等（outbox 用 Hashable 全字段，request 用编码字节级一致）
final class TransferRequestBuilderTests: XCTestCase {

    // MARK: - outboxItem（对照 submitTransfer 内联）

    func testOutboxItemMatchesPreSplitInline() {
        var form = TransferFormState()
        form.title = "  做登录  "
        form.goal = " 目标 "
        form.acceptance = "  A1  \n\nA2 "
        form.pipeline = " dev "
        form.executor = "opencode"
        form.skillRef = "skills/custom"
        form.complexity = "Huge"       // 非 small/medium/large → medium
        form.bumpVersion = true
        form.humanNote = " 备注 "
        form.feasibility = "ok"

        let planBody = "# Plan: X\n## 目标\n目标"
        let cid = "req-1"
        let savedAt = "2026-08-01T00:00:00Z"

        let actual = TransferRequestBuilder.outboxItem(
            projectId: "p", threadId: "p::t", form: form,
            planBody: planBody, clientRequestId: cid, savedAt: savedAt
        )

        // 搬迁前 submitTransfer 内联表达式
        let titleRaw = form.title.trimmingCharacters(in: .whitespacesAndNewlines)
        let title = String(titleRaw.prefix(80))
        let goal = form.goal.trimmingCharacters(in: .whitespacesAndNewlines)
        let pipeline = form.pipeline.trimmingCharacters(in: .whitespacesAndNewlines)
        let accLines = form.acceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let cx = form.complexity.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let complexity = ["small", "medium", "large"].contains(cx) ? cx : "medium"
        let note = form.humanNote.trimmingCharacters(in: .whitespacesAndNewlines)
        let skillRef = SkillRefResolver.skillRef(forExecutor: form.executor, fallback: form.skillRef)
        let expected = LocalSessionStore.TransferOutboxItem(
            client_request_id: cid,
            project_id: "p",
            thread_id: "p::t",
            title: title,
            goal: goal,
            acceptance: accLines,
            pipeline: pipeline,
            feasibility: form.feasibility,
            feasibility_reason: form.feasibility == "blocked" ? form.feasibilityReason : nil,
            executor_intent: form.executor,
            plan_md: planBody,
            complexity: complexity,
            bump_version: form.bumpVersion,
            human_note: note,
            attempts: 0,
            saved_at: savedAt,
            skill_ref: skillRef,
            prompt_ref: SkillRefResolver.promptRef(forSkill: skillRef)
        )

        XCTAssertEqual(actual, expected) // Hashable 全字段一致
    }

    func testOutboxItemBlockedFeasibilityCarriesReason() {
        var form = TransferFormState()
        form.feasibility = "blocked"
        form.feasibilityReason = "缺依赖"
        form.title = "t"; form.goal = "g"; form.acceptance = "a"; form.pipeline = "dev"
        let item = TransferRequestBuilder.outboxItem(
            projectId: "p", threadId: "p::t", form: form, planBody: "",
            clientRequestId: "c", savedAt: "2026-08-01T00:00:00Z"
        )
        XCTAssertEqual(item.feasibility, "blocked")
        XCTAssertEqual(item.feasibility_reason, "缺依赖")
    }

    // MARK: - gatePayload（对照 promoteIntentCardToBacklog 内联）

    func testGatePayloadMatchesPreSplitInline() {
        let draft = TransferDraft(
            title: " 超长标题" + String(repeating: "x", count: 100),
            goal: " 目标 ",
            acceptance: "A1\nA2",
            pipeline: "dev",
            feasibility: "ok",
            feasibilityReason: "清晰",
            executorIntent: "python",
            skillRef: "",
            promptRef: "",
            planMd: "方案",
            complexity: "small",
            bumpVersion: true,
            source: "ccc-transfer"
        )

        let actual = TransferRequestBuilder.gatePayload(from: draft, projectId: "p", supersedeGoals: true)

        // 搬迁前 promoteIntentCardToBacklog 内联表达式
        let title = String(draft.title.trimmingCharacters(in: .whitespacesAndNewlines).prefix(80))
        let goal = draft.goal.trimmingCharacters(in: .whitespacesAndNewlines)
        let accLines = draft.acceptanceLines
        let skillRef = SkillRefResolver.skillRef(forExecutor: draft.executorIntent, fallback: draft.skillRef)
        var expected: [String: Any] = [
            "project_id": "p",
            "title": title,
            "goal": goal.isEmpty ? title : goal,
            "acceptance": accLines,
            "pipeline": draft.pipeline,
            "feasibility": draft.feasibility,
            "feasibility_reason": draft.feasibilityReason,
            "executor_intent": draft.executorIntent,
            "skill_ref": skillRef,
            "prompt_ref": SkillRefResolver.promptRef(forSkill: skillRef),
            "complexity": draft.complexity,
            "bump_version": draft.bumpVersion,
            "plan_md": draft.planMd,
            "card_kind": "epic",
            "supersede_goals": true,
        ]

        XCTAssertEqual(
            NSDictionary(dictionary: actual),
            NSDictionary(dictionary: expected)
        )
    }

    func testGatePayloadSupersedeFlagControl() {
        let draft = TransferDraft(title: "t", goal: "g", acceptance: "a", pipeline: "dev")
        let with = TransferRequestBuilder.gatePayload(from: draft, projectId: "p", supersedeGoals: true)
        XCTAssertEqual(with["supersede_goals"] as? Bool, true)
        let without = TransferRequestBuilder.gatePayload(from: draft, projectId: "p", supersedeGoals: false)
        XCTAssertNil(without["supersede_goals"])
    }

    // MARK: - request（对照 createManualEpic 内联；编码字节级一致）

    func testRequestMatchesPreSplitInlineByteIdentical() throws {
        var form = ManualEpicForm()
        form.title = "做登录"
        form.goal = "让登录可用"
        form.acceptance = "A1\n\n A2 "
        form.pipeline = "dev"
        form.executor = "opencode"
        form.complexity = "medium"

        let cid = "req-9"
        let actual = TransferRequestBuilder.request(projectId: "p", threadId: "p::t", form: form, clientRequestId: cid)

        // 搬迁前 createManualEpic 内联表达式
        let accLines = form.acceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let skillRef = SkillRefResolver.skillRef(forExecutor: form.executor, fallback: nil)
        let expected = TransferRequest(
            project_id: "p",
            thread_id: "p::t",
            title: form.title,
            goal: form.goal,
            acceptance: accLines,
            pipeline: form.pipeline,
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: form.executor,
            skills_hint: [],
            skill_ref: skillRef,
            prompt_ref: SkillRefResolver.promptRef(forSkill: skillRef),
            plan_md: form.goal,
            complexity: form.complexity,
            client_request_id: cid
        )

        // 同类型同值 → 编码字节一致
        let actualData = try JSONEncoder().encode(actual)
        let expectedData = try JSONEncoder().encode(expected)
        XCTAssertEqual(actualData, expectedData)
    }

    // MARK: - 规范化原语

    func testNormalizedTitleTrimsAndCaps80() {
        XCTAssertEqual(TransferRequestBuilder.normalizedTitle("  短  "), "短")
        let long = String(repeating: "x", count: 100)
        XCTAssertEqual(TransferRequestBuilder.normalizedTitle(" " + long + " "), String(repeating: "x", count: 80))
        XCTAssertEqual(TransferRequestBuilder.normalizedTitle("").count, 0)
    }

    func testNormalizedComplexity() {
        XCTAssertEqual(TransferRequestBuilder.normalizedComplexity("small"), "small")
        XCTAssertEqual(TransferRequestBuilder.normalizedComplexity("MEDIUM"), "medium")
        XCTAssertEqual(TransferRequestBuilder.normalizedComplexity("  large  "), "large")
        XCTAssertEqual(TransferRequestBuilder.normalizedComplexity("huge"), "medium")
        XCTAssertEqual(TransferRequestBuilder.normalizedComplexity(""), "medium")
    }

    func testNormalizedPipelineAndGoal() {
        XCTAssertEqual(TransferRequestBuilder.normalizedPipeline(" dev "), "dev")
        XCTAssertEqual(TransferRequestBuilder.normalizedGoal(" 目标 "), "目标")
    }

    func testResolvedRefs() {
        XCTAssertEqual(
            TransferRequestBuilder.resolvedSkillRef(executor: "python", fallback: nil),
            "skills/script-seed"
        )
        XCTAssertEqual(
            TransferRequestBuilder.resolvedSkillRef(executor: "opencode", fallback: "skills/custom"),
            "skills/custom"
        )
        XCTAssertEqual(
            TransferRequestBuilder.resolvedPromptRef(skillRef: "skills/bug-fix"),
            "prompts/bug-fix-prompt"
        )
    }

    // MARK: - AcceptanceText（AcceptanceText 拆分行为锁）

    func testAcceptanceTextPlainLines() {
        XCTAssertEqual(AcceptanceText.plainLines("  A  \n\n B \n"), ["A", "B"])
        XCTAssertEqual(AcceptanceText.plainLines(""), [])
        XCTAssertEqual(AcceptanceText.plainLines("  \n\n  "), [])
        // 不去列表前缀（与 TransferDraft.acceptanceLines 一致）
        XCTAssertEqual(AcceptanceText.plainLines("- A\n* B"), ["- A", "* B"])
    }

    func testAcceptanceTextBulletStrippedJoined() {
        XCTAssertEqual(AcceptanceText.bulletStrippedJoined("- A\n* B"), "A\nB")
        XCTAssertEqual(AcceptanceText.bulletStrippedJoined("  -  A  \n## B"), "A\n## B")
        XCTAssertEqual(AcceptanceText.bulletStrippedJoined("A\n\nB"), "A\nB")
        XCTAssertEqual(AcceptanceText.bulletStrippedJoined(""), "")
    }
}
