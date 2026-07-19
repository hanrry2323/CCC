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

    // MARK: - Session record

    struct Record: Codable {
        var thread_id: String
        var project_id: String
        var title: String?
        var updated_at: String
        var messages: [ChatMessage]
        var flow: FlowThreadSnapshot?
        var needs_hub_sync: Bool?
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

    private static func isoNow() -> String {
        ISO8601DateFormatter().string(from: Date())
    }

    // MARK: - Read / write session

    static func load(projectId: String, threadId: String) -> Record? {
        let url = sessionURL(projectId: projectId, threadId: threadId)
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Record.self, from: data)
    }

    static func save(_ record: Record) {
        ensureDir(projectDir(record.project_id))
        var rec = record
        rec.updated_at = isoNow()
        guard let data = try? JSONEncoder().encode(rec) else { return }
        try? data.write(to: sessionURL(projectId: rec.project_id, threadId: rec.thread_id), options: .atomic)
        upsertIndex(projectId: rec.project_id, threadId: rec.thread_id, title: rec.title, updatedAt: rec.updated_at)
    }

    static func saveMessages(
        projectId: String,
        threadId: String,
        messages: [ChatMessage],
        title: String? = nil,
        flow: FlowThreadSnapshot? = nil,
        needsHubSync: Bool = false
    ) {
        let existing = load(projectId: projectId, threadId: threadId)
        let persistable = messages
            .filter { $0.role == "user" || $0.role == "assistant" }
            .map {
                ChatMessage(
                    role: $0.role,
                    content: $0.content,
                    toolSteps: $0.toolSteps,
                    filesChanged: $0.filesChanged,
                    toolsFinished: $0.toolsFinished
                )
            }
        let rec = Record(
            thread_id: threadId,
            project_id: projectId,
            title: title ?? existing?.title,
            updated_at: isoNow(),
            messages: persistable,
            flow: flow ?? existing?.flow,
            needs_hub_sync: needsHubSync || (existing?.needs_hub_sync ?? false)
        )
        save(rec)
    }

    static func delete(projectId: String, threadId: String) {
        try? fm.removeItem(at: sessionURL(projectId: projectId, threadId: threadId))
        var idx = loadIndex(projectId: projectId)
        idx.removeAll { $0.thread_id == threadId }
        writeIndex(projectId: projectId, entries: idx)
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
}
