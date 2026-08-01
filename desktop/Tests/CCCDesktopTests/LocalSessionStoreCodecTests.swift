import XCTest
@testable import CCCDesktop

/// 行为锁 · 持久化层（编解码 + 纯函数）：LocalSessionStore
/// 锁定 Record / ChatMessage / TransferOutboxItem 等旧盘兼容编解码与纯逻辑
final class LocalSessionStoreCodecTests: XCTestCase {

    // MARK: - ChatMessage 编解码

    private func decodeChat(_ json: String) throws -> ChatMessage {
        try JSONDecoder().decode(ChatMessage.self, from: Data(json.utf8))
    }

    func testChatMessageRoundTrip() throws {
        let step = ToolStep(name: "bash", label: "bash", icon: "terminal", status: .done, resultHint: "ok")
        let src = ChatMessage(
            id: UUID(uuidString: "B3D0F2F1-0000-0000-0000-000000000001")!,
            role: "assistant",
            content: "hello",
            toolSteps: [step],
            filesChanged: 3,
            toolsFinished: true,
            changedFilePaths: ["a.swift"],
            kind: "summary",
            summaryRounds: 5,
            transientNote: "working",
            edited: true,
            replyTo: "abc",
            displayContent: "short label"
        )
        let data = try JSONEncoder().encode(src)
        let back = try JSONDecoder().decode(ChatMessage.self, from: data)

        XCTAssertEqual(back.id, src.id)
        XCTAssertEqual(back.role, "assistant")
        XCTAssertEqual(back.content, "hello")
        XCTAssertFalse(back.isStreaming) // 编解码后恒 false（运行态字段）
        XCTAssertEqual(back.toolSteps.count, 1)
        XCTAssertEqual(back.toolSteps[0].name, "bash")
        XCTAssertEqual(back.toolSteps[0].status, .done)
        XCTAssertEqual(back.toolSteps[0].resultHint, "ok")
        XCTAssertEqual(back.filesChanged, 3)
        XCTAssertTrue(back.toolsFinished)
        XCTAssertEqual(back.changedFilePaths, ["a.swift"])
        XCTAssertEqual(back.kind, "summary")
        XCTAssertEqual(back.summaryRounds, 5)
        XCTAssertEqual(back.transientNote, "working")
        XCTAssertTrue(back.edited)
        XCTAssertEqual(back.replyTo, "abc")
        XCTAssertEqual(back.displayContent, "short label")
    }

    func testChatMessageOldDiskMinimal() throws {
        let json = #"{"id":"B3D0F2F1-0000-0000-0000-000000000000","role":"user","content":"hi"}"#
        let m = try decodeChat(json)
        XCTAssertEqual(m.id, UUID(uuidString: "B3D0F2F1-0000-0000-0000-000000000000"))
        XCTAssertEqual(m.role, "user")
        XCTAssertEqual(m.content, "hi")
        XCTAssertTrue(m.toolSteps.isEmpty)
        XCTAssertEqual(m.filesChanged, 0)
        XCTAssertFalse(m.toolsFinished)
        XCTAssertEqual(m.kind, "chat")
        XCTAssertEqual(m.summaryRounds, 0)
        XCTAssertFalse(m.edited)
        XCTAssertNil(m.replyTo)
        XCTAssertNil(m.displayContent)
    }

    func testChatMessageToolsFinishedDefaultsToToolSteps() throws {
        let json = #"{"id":"B3D0F2F1-0000-0000-0000-000000000000","role":"assistant","content":"x","tool_steps":[{"id":"B3D0F2F1-0000-0000-0000-000000000009","name":"n","label":"l","icon":"i","status":"done"}]}"#
        let m = try decodeChat(json)
        XCTAssertEqual(m.toolSteps.count, 1)
        XCTAssertTrue(m.toolsFinished)
    }

    func testChatMessageMissingIdGetsNewUUID() throws {
        let json = #"{"role":"user","content":"x"}"#
        let m = try decodeChat(json)
        XCTAssertFalse(m.id.uuidString.isEmpty)
    }

    func testChatMessageMinimalEncodeOmitsDefaults() throws {
        let m = ChatMessage(role: "user", content: "x")
        let obj = try JSONSerialization.jsonObject(
            with: JSONEncoder().encode(m)
        ) as? [String: Any]
        XCTAssertEqual(obj?["role"] as? String, "user")
        XCTAssertEqual(obj?["content"] as? String, "x")
        XCTAssertNotNil(obj?["id"])
        XCTAssertNil(obj?["tool_steps"])
        XCTAssertNil(obj?["files_changed"])
        XCTAssertNil(obj?["tools_finished"])
        XCTAssertNil(obj?["kind"])
        XCTAssertNil(obj?["summary_rounds"])
        XCTAssertNil(obj?["edited"])
        XCTAssertNil(obj?["reply_to"])
    }

    // MARK: - Record 编解码

    func testRecordRoundTrip() throws {
        var record = LocalSessionStore.Record(
            thread_id: "proj::abc",
            project_id: "proj",
            title: "T",
            updated_at: "2026-08-01T00:00:00Z",
            messages: [
                ChatMessage(role: "user", content: "u"),
                ChatMessage(role: "assistant", content: "a"),
            ],
            flow: FlowThreadSnapshot(
                epicId: "e1", epic: nil, works: [], headline: "h",
                recentEpics: [], emptyMessage: "", fanoutHint: "hint", stopLossHint: nil
            ),
            needs_hub_sync: true,
            revision: 3,
            claude_session_id: "sess1"
        )
        let data = try JSONEncoder().encode(record)
        let back = try JSONDecoder().decode(LocalSessionStore.Record.self, from: data)

        XCTAssertEqual(back.thread_id, "proj::abc")
        XCTAssertEqual(back.project_id, "proj")
        XCTAssertEqual(back.title, "T")
        XCTAssertEqual(back.messages.map(\.role), ["user", "assistant"])
        XCTAssertEqual(back.flow?.epicId, "e1")
        XCTAssertEqual(back.flow?.fanoutHint, "hint")
        XCTAssertEqual(back.needs_hub_sync, true)
        XCTAssertEqual(back.revision, 3)
        XCTAssertEqual(back.claude_session_id, "sess1")

        // 复用同一 record 变体比较
        record.updated_at = back.updated_at
        XCTAssertEqual(record.messages.count, back.messages.count)
    }

    func testRecordOldDiskOptionalDefaults() throws {
        let json = #"{"thread_id":"proj::x","project_id":"proj","updated_at":"2026-01-01T00:00:00Z","messages":[{"id":"B3D0F2F1-0000-0000-0000-000000000000","role":"user","content":"m"}]}"#
        let back = try JSONDecoder().decode(LocalSessionStore.Record.self, from: Data(json.utf8))
        XCTAssertNil(back.flow)
        XCTAssertNil(back.needs_hub_sync)
        XCTAssertNil(back.revision)
        XCTAssertNil(back.claude_session_id)
        XCTAssertEqual(back.messages.count, 1)
    }

    // MARK: - TransferOutboxItem 编解码（含旧盘兜底）

    private func outboxItemFixture() -> LocalSessionStore.TransferOutboxItem {
        LocalSessionStore.TransferOutboxItem(
            client_request_id: "c1",
            project_id: "proj",
            thread_id: "proj::t",
            title: "T",
            goal: "G",
            acceptance: ["A"],
            pipeline: "dev",
            feasibility: "ok",
            feasibility_reason: nil,
            executor_intent: "opencode",
            plan_md: "plan",
            complexity: "medium",
            bump_version: true,
            human_note: "note",
            attempts: 2,
            saved_at: "2026-08-01T00:00:00Z",
            skill_ref: "skills/x",
            prompt_ref: "prompts/x"
        )
    }

    func testTransferOutboxItemRoundTrip() throws {
        let item = outboxItemFixture()
        let data = try JSONEncoder().encode(item)
        let back = try JSONDecoder().decode(LocalSessionStore.TransferOutboxItem.self, from: data)
        XCTAssertEqual(back, item) // Hashable 全字段
    }

    func testTransferOutboxItemOldDiskFallbackDefaults() throws {
        // 旧盘项（stage5 硬切换前 queued）：无 skill_ref/prompt_ref/complexity/bump_version/human_note
        let json = #"{"client_request_id":"c1","project_id":"proj","thread_id":"proj::t","title":"T","goal":"G","acceptance":["A"],"pipeline":"dev","feasibility":"ok","feasibility_reason":null,"executor_intent":"opencode","plan_md":"plan","attempts":0,"saved_at":"2026-01-01T00:00:00Z"}"#
        let back = try JSONDecoder().decode(LocalSessionStore.TransferOutboxItem.self, from: Data(json.utf8))
        XCTAssertEqual(back.skill_ref, SkillRefResolver.defaultSkillRef) // 兜底 write-code
        XCTAssertEqual(back.prompt_ref, SkillRefResolver.defaultPromptRef)
        XCTAssertEqual(back.complexity, "medium")
        XCTAssertFalse(back.bump_version)
        XCTAssertEqual(back.human_note, "")
    }

    func testTransferOutboxItemOldDiskExplicitValuesKept() throws {
        let json = #"{"client_request_id":"c1","project_id":"proj","thread_id":"proj::t","title":"T","goal":"G","acceptance":["A"],"pipeline":"dev","feasibility":"ok","feasibility_reason":null,"executor_intent":"opencode","skill_ref":"skills/custom","prompt_ref":"prompts/custom","plan_md":"plan","complexity":"small","bump_version":true,"human_note":"keep","attempts":0,"saved_at":"2026-01-01T00:00:00Z"}"#
        let back = try JSONDecoder().decode(LocalSessionStore.TransferOutboxItem.self, from: Data(json.utf8))
        XCTAssertEqual(back.skill_ref, "skills/custom")
        XCTAssertEqual(back.prompt_ref, "prompts/custom")
        XCTAssertEqual(back.complexity, "small")
        XCTAssertTrue(back.bump_version)
        XCTAssertEqual(back.human_note, "keep")
    }

    func testTransferOutboxItemRequiredFieldMissingThrows() {
        let json = #"{"project_id":"proj","title":"T","goal":"G","acceptance":[],"pipeline":"dev","feasibility":"ok","executor_intent":"opencode","plan_md":"","attempts":0,"saved_at":"x"}"#
        XCTAssertThrowsError(try JSONDecoder().decode(LocalSessionStore.TransferOutboxItem.self, from: Data(json.utf8)))
    }

    // MARK: - TransferReceipt

    func testReceiptIsRejected() {
        var r = LocalSessionStore.TransferReceipt(
            client_request_id: "c", epic_id: "e", project_id: "p", thread_id: "p::t",
            delivered_at: "d", status: nil, reason: nil, fix_hint: nil, card_title: nil
        )
        XCTAssertFalse(r.isRejected) // 缺省 delivered
        r.status = "rejected"
        XCTAssertTrue(r.isRejected)
        r.status = "REJECTED"
        XCTAssertTrue(r.isRejected) // 大小写不敏感
        r.status = "delivered"
        XCTAssertFalse(r.isRejected)
    }

    func testTransferReceiptRoundTrip() throws {
        let src = LocalSessionStore.TransferReceipt(
            client_request_id: "c1", epic_id: "e1", project_id: "p", thread_id: "p::t",
            delivered_at: "d", status: "rejected", reason: "gate", fix_hint: "fix", card_title: "T"
        )
        let data = try JSONEncoder().encode(src)
        let back = try JSONDecoder().decode(LocalSessionStore.TransferReceipt.self, from: data)
        XCTAssertEqual(back, src)
        XCTAssertTrue(back.isRejected)
    }

    // MARK: - ExportV1 / ProjectsCache / BoardCacheFile

    func testExportV1RoundTrip() throws {
        let src = LocalSessionStore.ExportV1(
            exported_at: "2026-08-01T00:00:00Z", project_id: "p", thread_id: "p::t",
            title: "T", messages: [ChatMessage(role: "user", content: "m")],
            revision: 2, claude_session_id: "s", include_resume: true
        )
        let data = try JSONEncoder().encode(src)
        let back = try JSONDecoder().decode(LocalSessionStore.ExportV1.self, from: data)
        XCTAssertEqual(back.format, "ccc-desktop-session-v1")
        XCTAssertEqual(back.project_id, "p")
        XCTAssertEqual(back.thread_id, "p::t")
        XCTAssertEqual(back.title, "T")
        XCTAssertEqual(back.messages.map(\.role), ["user"])
        XCTAssertEqual(back.revision, 2)
        XCTAssertEqual(back.claude_session_id, "s")
        XCTAssertEqual(back.include_resume, true)
    }

    func testProjectsCacheRoundTrip() throws {
        let project = DesktopProject(
            id: "p", name: "P", path: "/x/p", workspace: "ws", role: "app", engine_eligible: true
        )
        let src = LocalSessionStore.ProjectsCache(
            projects: [project], default_project: "p", saved_at: "2026-08-01T00:00:00Z"
        )
        let data = try JSONEncoder().encode(src)
        let back = try JSONDecoder().decode(LocalSessionStore.ProjectsCache.self, from: data)
        XCTAssertEqual(back.projects.first?.id, "p")
        XCTAssertEqual(back.projects.first?.workspace, "ws")
        XCTAssertEqual(back.default_project, "p")
    }

    func testBoardCacheFileRoundTrip() throws {
        let src = LocalSessionStore.BoardCacheFile(
            project_id: "p", workspace: "ws", columns: [:], saved_at: "2026-08-01T00:00:00Z"
        )
        let data = try JSONEncoder().encode(src)
        let back = try JSONDecoder().decode(LocalSessionStore.BoardCacheFile.self, from: data)
        XCTAssertEqual(back.project_id, "p")
        XCTAssertEqual(back.workspace, "ws")
        XCTAssertTrue(back.columns.isEmpty)
    }

    // MARK: - 纯函数

    func testProjectIdFromThreadId() {
        XCTAssertEqual(LocalSessionStore.projectId(fromThreadId: "proj::abc"), "proj")
        XCTAssertEqual(LocalSessionStore.projectId(fromThreadId: "a:b:c"), "a")
        XCTAssertEqual(LocalSessionStore.projectId(fromThreadId: "no-sep"), "no-sep")
        XCTAssertEqual(LocalSessionStore.projectId(fromThreadId: ""), "")
    }

    func testCreateThreadIdFormat() {
        let tid = LocalSessionStore.createThreadId(projectId: "proj")
        XCTAssertTrue(tid.hasPrefix("proj::"))
        let suffix = String(tid.dropFirst("proj::".count))
        XCTAssertEqual(suffix.count, 8)
        XCTAssertTrue(suffix.allSatisfy { $0.isLetter || $0.isNumber })
    }

    func testMessageScoreWeighted() {
        let msgs = [
            ChatMessage(role: "user", content: "abc"),
            ChatMessage(role: "assistant", content: "abcdef"),
            ChatMessage(role: "assistant", content: "x", toolSteps: [ToolStep(name: "t", label: "t", icon: "i")]),
        ]
        // count*1000(3000) + body(3+6+1=10) + tools*50(50) + assistants*200(400) = 3460
        XCTAssertEqual(LocalSessionStore.messageScore(msgs), 3460)
    }

    func testEstimateTokens() {
        let msgs = [
            ChatMessage(role: "user", content: "abc"),
            ChatMessage(role: "assistant", content: "abcdef"),
            ChatMessage(role: "assistant", content: "x"),
        ]
        XCTAssertEqual(LocalSessionStore.estimateTokens(msgs), (3 + 6 + 1) / 4)
    }

    // MARK: - compactIfNeeded

    private func makeMessages(_ count: Int, contentLength: Int = 10, userFirst: Bool = true) -> [ChatMessage] {
        (0..<count).map { i in
            let role = (i.isMultiple(of: 2) == userFirst) ? "user" : "assistant"
            return ChatMessage(role: role, content: String(repeating: "x", count: contentLength))
        }
    }

    func testCompactBelowThresholdUnchanged() {
        let msgs = makeMessages(10)
        let (out, didCompact, rounds) = LocalSessionStore.compactIfNeeded(msgs)
        XCTAssertFalse(didCompact)
        XCTAssertEqual(rounds, 0)
        XCTAssertEqual(out.count, 10)
    }

    func testCompactMessageCountThreshold() {
        let msgs = makeMessages(81)
        let (out, didCompact, rounds) = LocalSessionStore.compactIfNeeded(msgs)
        XCTAssertTrue(didCompact)
        // 81 条：keepRecent=30 → 压缩 0..<51；rounds = 其中 user 数 = 26
        XCTAssertEqual(rounds, 26)
        XCTAssertEqual(out.count, 1 + (81 - 51))
        XCTAssertEqual(out.first?.kind, "summary")
        XCTAssertEqual(out.first?.summaryRounds, 26)
        XCTAssertTrue(out.first?.content.contains("26 轮") ?? false)
    }

    func testCompactTokenThreshold() {
        // 40 条 × 3200 字符 → 128k chars → estimate 32000 > 30000；条数 ≤80 走 token 阈值
        let msgs = makeMessages(40, contentLength: 3200)
        let (out, didCompact, rounds) = LocalSessionStore.compactIfNeeded(msgs)
        XCTAssertTrue(didCompact)
        // keepStart = 40-30 = 10 → 压缩 0..<10；user 在偶数位 → 5
        XCTAssertEqual(rounds, 5)
        XCTAssertEqual(out.count, 1 + (40 - 10))
        XCTAssertEqual(out.first?.kind, "summary")
    }

    func testCompactKeepsExistingSummaryCards() {
        var msgs = makeMessages(81)
        // 前置 summary 卡
        msgs.insert(ChatMessage(role: "assistant", content: "已压缩", kind: "summary", summaryRounds: 3), at: 0)
        let (out, didCompact, _) = LocalSessionStore.compactIfNeeded(msgs)
        XCTAssertTrue(didCompact)
        XCTAssertEqual(out.first?.kind, "summary") // 原 summary 保留在首
    }

    // MARK: - isExhaustRepairHint

    func testIsExhaustRepairHint() {
        XCTAssertTrue(LocalSessionStore.isExhaustRepairHint("hang_detected in slot"))
        XCTAssertTrue(LocalSessionStore.isExhaustRepairHint("retry budget exceeded"))
        XCTAssertTrue(LocalSessionStore.isExhaustRepairHint("short_path_fail reported"))
        XCTAssertTrue(LocalSessionStore.isExhaustRepairHint("fail_loop_exhausted"))
        XCTAssertTrue(LocalSessionStore.isExhaustRepairHint("验收耗尽"))
        XCTAssertFalse(LocalSessionStore.isExhaustRepairHint("all good"))
        XCTAssertFalse(LocalSessionStore.isExhaustRepairHint(""))
    }
}
