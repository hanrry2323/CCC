import Foundation

/// 本机会话 SSOT：`~/Library/Application Support/CCCDesktop/`
/// Hub 仅异步镜像；杀 App / Hub 抖不丢消息与 tool_steps。
enum LocalSessionStore {
    private static let fm = FileManager.default

    static var rootURL: URL {
        let base = fm.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("CCCDesktop", isDirectory: true)
    }

    static var sessionsRoot: URL {
        rootURL.appendingPathComponent("sessions", isDirectory: true)
    }

    static var projectsCacheURL: URL {
        rootURL.appendingPathComponent("projects-cache.json")
    }

    static var pendingSyncURL: URL {
        rootURL.appendingPathComponent("pending-sync.json")
    }

    static var transferOutboxURL: URL {
        rootURL.appendingPathComponent("transfer-outbox.json")
    }

    /// 创建新会话：生成唯一 thread id
    static func createThreadId(projectId: String) -> String {
        "\(projectId)::\(UUID().uuidString.prefix(8))"
    }

    /// 从 threadId 提取 projectId
    static func projectId(fromThreadId threadId: String) -> String {
        if let idx = threadId.firstIndex(of: ":") {
            return String(threadId[..<idx])
        }
        return threadId
    }

    /// 兼容旧版单对话迁移：迁移旧 ::main 文件到新 id 体系
    static func migrateLegacyThread(projectId: String) -> String {
        let legacyId = "\(projectId)::main"
        let url = sessionURL(projectId: projectId, threadId: legacyId)
        guard fm.fileExists(atPath: url.path) else { return legacyId }
        return legacyId
    }

    // MARK: - Session record

    struct Record: Codable {
        var thread_id: String
        var project_id: String
        var title: String?
        var updated_at: String
        var messages: [ChatMessage]
        var flow: FlowThreadSnapshot?
        var needs_hub_sync: Bool?
        /// 单调修订（项目即对话）；缺省 0 兼容旧盘
        var revision: UInt64?
        /// loop-code / Claude SDK 会话 id；冷启动 resume，保证持续对话
        var claude_session_id: String?
    }

    struct ThreadIndexEntry: Codable, Hashable {
        var thread_id: String
        var title: String?
        var updated_at: String?
        var project_id: String?
    }

    struct PendingSyncItem: Codable, Hashable {
        var project_id: String
        var thread_id: String
        var attempts: Int
    }

    /// Hub 不可达时转任务 outbox（hub-api-v1 queued）
    struct TransferOutboxItem: Codable, Hashable {
        var client_request_id: String
        var project_id: String
        var thread_id: String
        var title: String
        var goal: String
        var acceptance: [String]
        var pipeline: String
        var feasibility: String
        var feasibility_reason: String?
        var executor_intent: String
        var plan_md: String
        var complexity: String
        var attempts: Int
        var saved_at: String
    }

    struct ProjectsCache: Codable {
        var projects: [DesktopProject]
        var default_project: String?
        var saved_at: String
    }

    private static func projectDir(_ projectId: String) -> URL {
        sessionsRoot.appendingPathComponent(projectId, isDirectory: true)
    }

    private static func sessionURL(projectId: String, threadId: String) -> URL {
        projectDir(projectId).appendingPathComponent("\(threadId).json")
    }

    private static func indexURL(projectId: String) -> URL {
        projectDir(projectId).appendingPathComponent("_index.json")
    }

    private static func ensureDir(_ url: URL) {
        try? fm.createDirectory(at: url, withIntermediateDirectories: true)
    }

    private static let isoFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        return f
    }()

    private static func isoNow() -> String {
        isoFormatter.string(from: Date())
    }

    // MARK: - Read / write session

    static func load(projectId: String, threadId: String) -> Record? {
        let url = sessionURL(projectId: projectId, threadId: threadId)
        guard fm.fileExists(atPath: url.path) else { return nil }
        guard let data = try? Data(contentsOf: url) else { return nil }
        do {
            return try JSONDecoder().decode(Record.self, from: data)
        } catch {
            // 损坏：备份后返回 nil，避免静默丢历史且无痕迹
            let bak = url.appendingPathExtension("corrupted")
            try? fm.removeItem(at: bak)
            try? fm.copyItem(at: url, to: bak)
            #if DEBUG
            print("[LocalSessionStore] corrupt session \(url.lastPathComponent): \(error)")
            #endif
            return nil
        }
    }

    static func save(_ record: Record) {
        ensureDir(projectDir(record.project_id))
        var rec = record
        rec.updated_at = isoNow()
        guard let data = try? JSONEncoder().encode(rec) else {
            #if DEBUG
            print("[LocalSessionStore] encode failed for \(rec.thread_id)")
            #endif
            return
        }
        try? data.write(to: sessionURL(projectId: rec.project_id, threadId: rec.thread_id), options: .atomic)
        upsertIndex(projectId: rec.project_id, threadId: rec.thread_id, title: rec.title, updatedAt: rec.updated_at)
    }

    /// 内容丰富度：条数 + 字数 + assistant 加权 + 工具步（用于禁止空 Hub 盖掉本机）
    static func messageScore(_ messages: [ChatMessage]) -> Int {
        let body = messages.reduce(0) { $0 + $1.content.count }
        let tools = messages.reduce(0) { $0 + $1.toolSteps.count }
        let assistants = messages.filter { $0.role == "assistant" }.count
        return messages.count * 1000 + body + tools * 50 + assistants * 200
    }

    static func saveMessages(
        projectId: String,
        threadId: String,
        messages: [ChatMessage],
        title: String? = nil,
        flow: FlowThreadSnapshot? = nil,
        needsHubSync: Bool = false,
        /// false：若本机已有更丰富内容则拒绝用更空的写入覆盖
        allowDowngrade: Bool = false,
        revision: UInt64? = nil,
        claudeSessionId: String? = nil
    ) {
        // 已存档会话禁止写回活动区（否则 refreshThreads / Hub 同步会「复活」）
        if isArchived(projectId: projectId, threadId: threadId) {
            return
        }
        let existing = load(projectId: projectId, threadId: threadId)
        let persistable = messages
            .filter { $0.role == "user" || $0.role == "assistant" }
            .map {
                ChatMessage(
                    id: $0.id,
                    role: $0.role,
                    content: $0.content,
                    toolSteps: $0.toolSteps,
                    filesChanged: $0.filesChanged,
                    toolsFinished: $0.toolsFinished,
                    changedFilePaths: $0.changedFilePaths,
                    kind: $0.kind,
                    summaryRounds: $0.summaryRounds,
                    transientNote: $0.transientNote,
                    edited: $0.edited,
                    replyTo: $0.replyTo
                )
            }
        let nextRev = revision ?? ((existing?.revision ?? 0) &+ 1)
        let nextClaudeId: String? = {
            if let claudeSessionId {
                let t = claudeSessionId.trimmingCharacters(in: .whitespacesAndNewlines)
                return t.isEmpty ? nil : t
            }
            return existing?.claude_session_id
        }()
        if !allowDowngrade, let existing, !existing.messages.isEmpty {
            let old = existing.messages
            if messageScore(persistable) < messageScore(old) {
                // 只更新标题/flow/resume id，保留更完整消息
                var keep = existing
                if let title, !title.isEmpty { keep.title = title }
                if let flow { keep.flow = flow }
                if needsHubSync { keep.needs_hub_sync = true }
                keep.revision = max(keep.revision ?? 0, nextRev)
                if let nextClaudeId { keep.claude_session_id = nextClaudeId }
                save(keep)
                return
            }
        }
        let rec = Record(
            thread_id: threadId,
            project_id: projectId,
            title: title ?? existing?.title,
            updated_at: isoNow(),
            messages: persistable,
            flow: flow ?? existing?.flow,
            needs_hub_sync: needsHubSync || (existing?.needs_hub_sync ?? false),
            revision: nextRev,
            claude_session_id: nextClaudeId
        )
        save(rec)
    }

    static func delete(projectId: String, threadId: String) {
        // 先改 index 再删文件，避免「文件已删但 index 仍指向」
        var idx = loadIndex(projectId: projectId)
        idx.removeAll { $0.thread_id == threadId }
        writeIndex(projectId: projectId, entries: idx)
        try? fm.removeItem(at: sessionURL(projectId: projectId, threadId: threadId))
    }

    /// 重置项目所有会话：删盘 + 清索引；调用方负责通知 sidecar drop slot
    static func reset(projectId: String) {
        let idx = loadIndex(projectId: projectId)
        for entry in idx {
            delete(projectId: projectId, threadId: entry.thread_id)
        }
    }

    static func archiveDir(projectId: String) -> URL {
        projectDir(projectId).appendingPathComponent("_archive", isDirectory: true)
    }

    /// 是否已存档（`_archive/<threadId>.json` 存在即视为墓碑，禁止再出现在侧栏）
    static func isArchived(projectId: String, threadId: String) -> Bool {
        let dst = archiveDir(projectId: projectId).appendingPathComponent("\(threadId).json")
        return fm.fileExists(atPath: dst.path)
    }

    static func archiveThread(projectId: String, threadId: String) {
        ensureDir(archiveDir(projectId: projectId))
        let src = sessionURL(projectId: projectId, threadId: threadId)
        let dst = archiveDir(projectId: projectId).appendingPathComponent("\(threadId).json")
        // 先从索引摘掉，避免「文件已迁走但索引仍在」或 move 失败导致幽灵会话
        var idx = loadIndex(projectId: projectId)
        idx.removeAll { $0.thread_id == threadId }
        writeIndex(projectId: projectId, entries: idx)
        if fm.fileExists(atPath: src.path) {
            if fm.fileExists(atPath: dst.path) {
                try? fm.removeItem(at: dst)
            }
            try? fm.moveItem(at: src, to: dst)
        } else if !fm.fileExists(atPath: dst.path) {
            // 无实体文件：写空墓碑，挡住 refreshThreads 再造同名 tid
            let tomb = Data("{}".utf8)
            try? tomb.write(to: dst, options: .atomic)
        }
        // 清掉误复活的活动副本
        if fm.fileExists(atPath: src.path), fm.fileExists(atPath: dst.path) {
            try? fm.removeItem(at: src)
        }
    }

    struct SearchResult: Identifiable, Hashable {
        var id: String { "\(threadId)-\(messageId)" }
        let threadId: String
        let messageId: String
        let role: String
        let content: String
        let title: String?
        let updatedAt: String?
    }

    static func searchMessages(projectId: String, query: String) -> [SearchResult] {
        guard !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return [] }
        let q = query.lowercased()
        let idx = loadIndex(projectId: projectId)
        var results: [SearchResult] = []
        for entry in idx {
            let url = sessionURL(projectId: projectId, threadId: entry.thread_id)
            guard let data = try? Data(contentsOf: url),
                  let record = try? JSONDecoder().decode(Record.self, from: data)
            else { continue }
            for msg in record.messages {
                guard msg.content.lowercased().contains(q) else { continue }
                let preview = msg.content.count > 120
                    ? String(msg.content.prefix(120)) + "…"
                    : msg.content
                results.append(SearchResult(
                    threadId: entry.thread_id,
                    messageId: msg.id.uuidString,
                    role: msg.role,
                    content: preview,
                    title: record.title,
                    updatedAt: record.updated_at
                ))
            }
        }
        return results.sorted { ($0.updatedAt ?? "") > ($1.updatedAt ?? "") }
    }

    static func rename(projectId: String, threadId: String, title: String) {
        guard var rec = load(projectId: projectId, threadId: threadId) else {
            upsertIndex(projectId: projectId, threadId: threadId, title: title, updatedAt: isoNow())
            return
        }
        rec.title = title
        save(rec)
    }

    // MARK: - Fork / Import / Export

    /// 分叉：复制消息到新 tid；不带 claude_session_id（新 resume）
    @discardableResult
    static func forkThread(projectId: String, sourceThreadId: String, title: String? = nil) -> String? {
        if isArchived(projectId: projectId, threadId: sourceThreadId) { return nil }
        let src = load(projectId: projectId, threadId: sourceThreadId)
        let msgs = src?.messages ?? []
        let newId = createThreadId(projectId: projectId)
        let baseTitle = title
            ?? (src?.title.map { "\($0)（副本）" } ?? "对话副本")
        saveMessages(
            projectId: projectId,
            threadId: newId,
            messages: msgs,
            title: baseTitle,
            flow: src?.flow,
            allowDowngrade: true,
            claudeSessionId: nil
        )
        // 显式清 resume
        if var rec = load(projectId: projectId, threadId: newId) {
            rec.claude_session_id = nil
            save(rec)
        }
        return newId
    }

    struct ExportV1: Codable {
        var format: String = "ccc-desktop-session-v1"
        var exported_at: String
        var project_id: String
        var thread_id: String
        var title: String?
        var messages: [ChatMessage]
        var revision: UInt64?
        /// 导出默认可剥离；导入时忽略 resume
        var claude_session_id: String?
        var include_resume: Bool?
    }

    static func exportV1(
        projectId: String,
        threadId: String,
        includeResume: Bool = false
    ) -> ExportV1? {
        guard let rec = load(projectId: projectId, threadId: threadId) else { return nil }
        return ExportV1(
            exported_at: isoNow(),
            project_id: projectId,
            thread_id: threadId,
            title: rec.title,
            messages: rec.messages,
            revision: rec.revision,
            claude_session_id: includeResume ? rec.claude_session_id : nil,
            include_resume: includeResume
        )
    }

    static func exportV1JSON(projectId: String, threadId: String, includeResume: Bool = false) -> Data? {
        guard let pack = exportV1(projectId: projectId, threadId: threadId, includeResume: includeResume)
        else { return nil }
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try? enc.encode(pack)
    }

    /// 导入为新会话；返回新 thread_id
    @discardableResult
    static func importV1(_ data: Data, projectId: String? = nil) -> String? {
        guard let pack = try? JSONDecoder().decode(ExportV1.self, from: data) else { return nil }
        let pid = projectId ?? pack.project_id
        guard !pid.isEmpty else { return nil }
        let newId = createThreadId(projectId: pid)
        let title = pack.title.map { "\($0)（导入）" } ?? "导入会话"
        saveMessages(
            projectId: pid,
            threadId: newId,
            messages: pack.messages,
            title: title,
            allowDowngrade: true,
            claudeSessionId: nil
        )
        return newId
    }

    // MARK: - Index

    static func loadIndex(projectId: String) -> [ThreadIndexEntry] {
        let url = indexURL(projectId: projectId)
        guard let data = try? Data(contentsOf: url),
              let list = try? JSONDecoder().decode([ThreadIndexEntry].self, from: data)
        else { return [] }
        return list.sorted { ($0.updated_at ?? "") > ($1.updated_at ?? "") }
    }

    private static func writeIndex(projectId: String, entries: [ThreadIndexEntry]) {
        ensureDir(projectDir(projectId))
        guard let data = try? JSONEncoder().encode(entries) else { return }
        try? data.write(to: indexURL(projectId: projectId), options: .atomic)
    }

    private static func upsertIndex(projectId: String, threadId: String, title: String?, updatedAt: String) {
        if isArchived(projectId: projectId, threadId: threadId) {
            return
        }
        var idx = loadIndex(projectId: projectId)
        if let i = idx.firstIndex(where: { $0.thread_id == threadId }) {
            idx[i].title = title ?? idx[i].title
            idx[i].updated_at = updatedAt
            idx[i].project_id = projectId
        } else {
            idx.insert(
                ThreadIndexEntry(
                    thread_id: threadId,
                    title: title,
                    updated_at: updatedAt,
                    project_id: projectId
                ),
                at: 0
            )
        }
        writeIndex(projectId: projectId, entries: idx)
    }

    static func threadsAsDesktop(projectId: String) -> [DesktopThread] {
        // 扫一遍：索引里若仍挂着已存档 tid，顺手摘掉；活动区误复活的 json 也删
        var idx = loadIndex(projectId: projectId)
        let before = idx.count
        idx.removeAll { isArchived(projectId: projectId, threadId: $0.thread_id) }
        if idx.count != before {
            writeIndex(projectId: projectId, entries: idx)
        }
        for entry in idx {
            let tid = entry.thread_id
            if isArchived(projectId: projectId, threadId: tid) {
                let live = sessionURL(projectId: projectId, threadId: tid)
                if fm.fileExists(atPath: live.path) {
                    try? fm.removeItem(at: live)
                }
            }
        }
        return idx
            .filter { !isArchived(projectId: projectId, threadId: $0.thread_id) }
            .map {
                DesktopThread(
                    thread_id: $0.thread_id,
                    title: $0.title,
                    updated_at: $0.updated_at,
                    project_id: $0.project_id ?? projectId
                )
            }
    }

    // MARK: - Projects cache

    static func saveProjects(_ projects: [DesktopProject], defaultProject: String?) {
        ensureDir(rootURL)
        let cache = ProjectsCache(
            projects: projects,
            default_project: defaultProject,
            saved_at: isoNow()
        )
        guard let data = try? JSONEncoder().encode(cache) else { return }
        try? data.write(to: projectsCacheURL, options: .atomic)
    }

    static func loadProjects() -> ProjectsCache? {
        guard let data = try? Data(contentsOf: projectsCacheURL) else { return nil }
        return try? JSONDecoder().decode(ProjectsCache.self, from: data)
    }

    // MARK: - Hub sync retry queue

    static func enqueueSync(projectId: String, threadId: String) {
        var q = loadPendingSync()
        if let i = q.firstIndex(where: { $0.project_id == projectId && $0.thread_id == threadId }) {
            q[i].attempts += 0 // keep
        } else {
            q.append(PendingSyncItem(project_id: projectId, thread_id: threadId, attempts: 0))
        }
        writePendingSync(q)
        if var rec = load(projectId: projectId, threadId: threadId) {
            rec.needs_hub_sync = true
            save(rec)
        }
    }

    static func dequeueSync(projectId: String, threadId: String) {
        var q = loadPendingSync()
        q.removeAll { $0.project_id == projectId && $0.thread_id == threadId }
        writePendingSync(q)
        if var rec = load(projectId: projectId, threadId: threadId) {
            rec.needs_hub_sync = false
            save(rec)
        }
    }

    static func loadPendingSync() -> [PendingSyncItem] {
        guard let data = try? Data(contentsOf: pendingSyncURL),
              let q = try? JSONDecoder().decode([PendingSyncItem].self, from: data)
        else { return [] }
        return q
    }

    static func bumpAttempt(projectId: String, threadId: String) -> Int {
        var q = loadPendingSync()
        if let i = q.firstIndex(where: { $0.project_id == projectId && $0.thread_id == threadId }) {
            q[i].attempts += 1
            writePendingSync(q)
            return q[i].attempts
        }
        return 0
    }

    private static func writePendingSync(_ q: [PendingSyncItem]) {
        ensureDir(rootURL)
        guard let data = try? JSONEncoder().encode(q) else { return }
        try? data.write(to: pendingSyncURL, options: .atomic)
    }

    static let maxSyncAttempts = 5
    static let maxTransferOutboxAttempts = 8

    // MARK: - Transfer outbox (Hub offline)

    static func enqueueTransfer(_ item: TransferOutboxItem) {
        var q = loadTransferOutbox()
        if let i = q.firstIndex(where: { $0.client_request_id == item.client_request_id }) {
            q[i] = item
        } else if let i = q.firstIndex(where: { $0.thread_id == item.thread_id }) {
            q[i] = item
        } else {
            q.append(item)
        }
        writeTransferOutbox(q)
    }

    static func dequeueTransfer(clientRequestId: String) {
        var q = loadTransferOutbox()
        q.removeAll { $0.client_request_id == clientRequestId }
        writeTransferOutbox(q)
    }

    static func loadTransferOutbox() -> [TransferOutboxItem] {
        guard let data = try? Data(contentsOf: transferOutboxURL),
              let q = try? JSONDecoder().decode([TransferOutboxItem].self, from: data)
        else { return [] }
        return q
    }

    static func bumpTransferAttempt(clientRequestId: String) -> Int {
        var q = loadTransferOutbox()
        if let i = q.firstIndex(where: { $0.client_request_id == clientRequestId }) {
            q[i].attempts += 1
            writeTransferOutbox(q)
            return q[i].attempts
        }
        return 0
    }

    private static func writeTransferOutbox(_ q: [TransferOutboxItem]) {
        ensureDir(rootURL)
        guard let data = try? JSONEncoder().encode(q) else { return }
        try? data.write(to: transferOutboxURL, options: .atomic)
    }

    // MARK: - Display compaction

    /// 显示压缩阈值：消息数 > 80（约 40 轮）或 token 估算 > 30k 触发
    static let compactMessageThreshold = 80
    static let compactTokenThreshold = 30_000
    /// 单次压缩保留最早的轮数被替换为摘要卡；保留最近 ~30 条不动
    static let compactKeepRecent = 30

    /// 粗估 token：4 字符 ≈ 1 token
    static func estimateTokens(_ messages: [ChatMessage]) -> Int {
        messages.reduce(0) { $0 + $1.content.count } / 4
    }

    /// 若消息超阈值，把最早 N 轮替换为一条 kind=summary 的占位卡片。
    /// 返回 (新消息, 是否压缩, 被压缩轮数)；不超阈值返回原消息。
    static func compactIfNeeded(_ messages: [ChatMessage]) -> (messages: [ChatMessage], didCompact: Bool, rounds: Int) {
        guard messages.count > compactMessageThreshold
                || estimateTokens(messages) > compactTokenThreshold
        else { return (messages, false, 0) }

        // 跳过已有 summary 卡片，找首个非 summary 的 user/assistant
        let firstReal = messages.firstIndex(where: { $0.kind == "chat" }) ?? 0
        let keepStart = max(firstReal, messages.count - compactKeepRecent)
        let toCompact = Array(messages[firstReal..<keepStart])
        guard toCompact.count >= 4 else { return (messages, false, 0) }

        // 统计被压缩轮数（user 消息数）
        let rounds = toCompact.filter { $0.role == "user" }.count
        let summary = ChatMessage(
            role: "assistant",
            content: "已压缩 \(rounds) 轮对话（保留最近 \(compactKeepRecent) 条）",
            kind: "summary",
            summaryRounds: rounds
        )
        var result: [ChatMessage] = []
        // 保留前置 summary 卡片
        result.append(contentsOf: messages[..<firstReal])
        result.append(summary)
        result.append(contentsOf: messages[keepStart...])
        return (result, true, rounds)
    }
}
