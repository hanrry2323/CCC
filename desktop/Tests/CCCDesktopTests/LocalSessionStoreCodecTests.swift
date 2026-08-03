import XCTest
@testable import CCCDesktop

/// 行为锁 · 持久化层（编解码 + 纯函数）：LocalSessionStore
/// 锁定 Record / ChatMessage 等旧盘兼容编解码与纯逻辑
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
                recentEpics: [], emptyMessage: "", fanoutHint: "hint"
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
}
