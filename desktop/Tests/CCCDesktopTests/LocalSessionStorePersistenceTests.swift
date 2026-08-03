import XCTest
@testable import CCCDesktop

/// 行为锁 · 持久化层（磁盘行为）：LocalSessionStore
/// 通过 testRootOverride 指向临时目录，绝不触碰真实 Application Support。
/// 覆盖 sync 队列、saveMessages 降级保护、archive 墓碑、search。
final class LocalSessionStorePersistenceTests: XCTestCase {

    private var tempDir: URL!

    override func setUpWithError() throws {
        tempDir = FileManager.default.temporaryDirectory
            .appendingPathComponent("ccc-tests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        LocalSessionStore.testRootOverride = tempDir
    }

    override func tearDownWithError() throws {
        LocalSessionStore.testRootOverride = nil
        if let tempDir {
            try? FileManager.default.removeItem(at: tempDir)
        }
    }

    // MARK: - sync 队列

    func testSyncQueueEnqueueDedupBumpDequeue() {
        LocalSessionStore.enqueueSync(projectId: "p", threadId: "p::t1")
        LocalSessionStore.enqueueSync(projectId: "p", threadId: "p::t1") // 去重
        XCTAssertEqual(LocalSessionStore.loadPendingSync().count, 1)
        XCTAssertEqual(LocalSessionStore.bumpAttempt(projectId: "p", threadId: "p::t1"), 1)
        XCTAssertEqual(LocalSessionStore.bumpAttempt(projectId: "p", threadId: "p::t1"), 2)
        LocalSessionStore.enqueueSync(projectId: "p", threadId: "p::t2")
        XCTAssertEqual(LocalSessionStore.loadPendingSync().count, 2)
        LocalSessionStore.dequeueSync(projectId: "p", threadId: "p::t1")
        XCTAssertEqual(LocalSessionStore.loadPendingSync().map(\.thread_id), ["p::t2"])
    }

    // MARK: - saveMessages / downgrade protection

    func testSaveMessagesRoundTripAndRevision() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "u"), ChatMessage(role: "assistant", content: "a")],
            title: "T"
        )
        var rec = LocalSessionStore.load(projectId: "p", threadId: "p::t1")
        XCTAssertEqual(rec?.messages.count, 2)
        XCTAssertEqual(rec?.revision, 1)
        XCTAssertEqual(rec?.title, "T")

        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "u2"), ChatMessage(role: "assistant", content: "a2"), ChatMessage(role: "assistant", content: "a3")],
            title: "T2"
        )
        rec = LocalSessionStore.load(projectId: "p", threadId: "p::t1")
        XCTAssertEqual(rec?.messages.count, 3)
        XCTAssertEqual(rec?.revision, 2)
        XCTAssertEqual(rec?.title, "T2")
    }

    func testSaveMessagesDowngradeProtection() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "rich"), ChatMessage(role: "assistant", content: "also")],
            title: "Old"
        )
        // 更空的内容写回：拒绝覆盖（保留消息），但 title/revision 更新
        LocalSessionStore.saveMessages(projectId: "p", threadId: "p::t1", messages: [], title: "New")
        let rec = LocalSessionStore.load(projectId: "p", threadId: "p::t1")
        XCTAssertEqual(rec?.messages.count, 2)
        XCTAssertEqual(rec?.title, "New")
        XCTAssertEqual(rec?.revision, 2)
    }

    func testSaveMessagesAllowDowngradeOverwrites() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "rich"), ChatMessage(role: "assistant", content: "also")],
            title: "Old"
        )
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [], title: "New", allowDowngrade: true
        )
        let rec = LocalSessionStore.load(projectId: "p", threadId: "p::t1")
        XCTAssertEqual(rec?.messages.count, 0)
        XCTAssertEqual(rec?.title, "New")
    }

    func testSaveMessagesFiltersNonChatRoles() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [
                ChatMessage(role: "user", content: "u"),
                ChatMessage(role: "system", content: "sys"),
                ChatMessage(role: "tool", content: "tool"),
            ]
        )
        let rec = LocalSessionStore.load(projectId: "p", threadId: "p::t1")
        XCTAssertEqual(rec?.messages.map(\.role), ["user"])
    }

    // MARK: - archive / prune

    func testArchiveMovesAndTombstones() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "m")], title: "T"
        )
        LocalSessionStore.archiveThread(projectId: "p", threadId: "p::t1")
        XCTAssertTrue(LocalSessionStore.isArchived(projectId: "p", threadId: "p::t1"))
        XCTAssertNil(LocalSessionStore.load(projectId: "p", threadId: "p::t1")) // 文件已迁走
        XCTAssertTrue(LocalSessionStore.threadsAsDesktop(projectId: "p").isEmpty) // 索引已摘
    }

    func testArchiveEmptyWritesTombstone() {
        // 无实体文件 → 墓碑，挡住 refreshThreads 再造同名 tid
        LocalSessionStore.archiveThread(projectId: "p", threadId: "p::ghost")
        XCTAssertTrue(LocalSessionStore.isArchived(projectId: "p", threadId: "p::ghost"))
    }

    func testSaveMessagesToArchivedIgnored() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "m")], title: "T"
        )
        LocalSessionStore.archiveThread(projectId: "p", threadId: "p::t1")
        // 已存档会话禁止写回活动区（避免「复活」）
        LocalSessionStore.saveMessages(projectId: "p", threadId: "p::t1", messages: [ChatMessage(role: "user", content: "revive")])
        XCTAssertNil(LocalSessionStore.load(projectId: "p", threadId: "p::t1"))
    }

    // MARK: - search

    func testSearchMessages() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "needle in haystack"), ChatMessage(role: "assistant", content: "other")],
            title: "T1"
        )
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t2",
            messages: [ChatMessage(role: "user", content: "nothing here")], title: "T2"
        )
        let hits = LocalSessionStore.searchMessages(projectId: "p", query: "needle")
        XCTAssertEqual(hits.count, 1)
        XCTAssertEqual(hits.first?.threadId, "p::t1")
        XCTAssertEqual(hits.first?.content, "needle in haystack")

        XCTAssertTrue(LocalSessionStore.searchMessages(projectId: "p", query: "NOPE").isEmpty)
        XCTAssertTrue(LocalSessionStore.searchMessages(projectId: "p", query: "   ").isEmpty)
    }

    func testSearchMessagesCaseInsensitive() {
        LocalSessionStore.saveMessages(
            projectId: "p", threadId: "p::t1",
            messages: [ChatMessage(role: "user", content: "Alpha Beta")], title: "T"
        )
        XCTAssertEqual(LocalSessionStore.searchMessages(projectId: "p", query: "alpha").count, 1)
    }

    // MARK: - projects / board cache

    func testProjectsCachePersists() {
        let project = DesktopProject(
            id: "p", name: "P", path: "/x/p", workspace: "ws", role: "app", engine_eligible: true
        )
        LocalSessionStore.saveProjects([project], defaultProject: "p")
        let cache = LocalSessionStore.loadProjects()
        XCTAssertEqual(cache?.projects.first?.id, "p")
        XCTAssertEqual(cache?.default_project, "p")
    }

    func testBoardCachePersists() {
        LocalSessionStore.saveBoardCache(projectId: "p", workspace: "ws", columns: [:])
        let cache = LocalSessionStore.loadBoardCache(projectId: "p")
        XCTAssertEqual(cache?.project_id, "p")
        XCTAssertEqual(cache?.workspace, "ws")
        // 空 projectId 拒绝落盘
        LocalSessionStore.saveBoardCache(projectId: "", workspace: nil, columns: [:])
        XCTAssertNil(LocalSessionStore.loadBoardCache(projectId: ""))
    }
}
