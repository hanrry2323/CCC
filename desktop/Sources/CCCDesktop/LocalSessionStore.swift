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

    /// 单对话模型：每项目恰好一个会话，thread id = "<projectId>::main"（全局唯一）
    static func conversationThreadId(for projectId: String) -> String {
        "\(projectId)::main"
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
        revision: UInt64? = nil
    ) {
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
                    kind: $0.kind,
                    summaryRounds: $0.summaryRounds,
                    transientNote: $0.transientNote
                )
            }
        let nextRev = revision ?? ((existing?.revision ?? 0) &+ 1)
        if !allowDowngrade, let existing, !existing.messages.isEmpty {
            let old = existing.messages
            if messageScore(persistable) < messageScore(old) {
                // 只更新标题/flow，保留更完整消息
                var keep = existing
                if let title, !title.isEmpty { keep.title = title }
                if let flow { keep.flow = flow }
                if needsHubSync { keep.needs_hub_sync = true }
                keep.revision = max(keep.revision ?? 0, nextRev)
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
            revision: nextRev
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

    /// 重置项目的单一会话：删盘 + 清索引；调用方负责通知 sidecar drop slot
    static func reset(projectId: String) {
        delete(projectId: projectId, threadId: conversationThreadId(for: projectId))
    }

    static func rename(projectId: String, threadId: String, title: String) {
        guard var rec = load(projectId: projectId, threadId: threadId) else {
            upsertIndex(projectId: projectId, threadId: threadId, title: title, updatedAt: isoNow())
            return
        }
        rec.title = title
        save(rec)
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
        loadIndex(projectId: projectId).map {
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
