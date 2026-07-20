import Foundation

/// 多会话状态（磁盘为 SSOT；此为 RAM/契约投影）。
struct ConversationState: Equatable {
    var projectId: String
    var threadId: String
    var messages: [ChatMessage]
    /// 右栏绑定 SSOT（随会话落盘；Hub 空列表不得冲掉）
    var boundEpicId: String?
    var flow: FlowThreadSnapshot?
    /// 单调修订；拒绝更旧写入（预留；落盘时递增）
    var revision: UInt64

    static func empty(projectId: String, threadId: String) -> ConversationState {
        ConversationState(
            projectId: projectId,
            threadId: threadId,
            messages: [],
            boundEpicId: nil,
            flow: nil,
            revision: 0
        )
    }
}

/// 会话读写门面：按 threadId 读写。
enum ConversationStore {
    /// 从本机盘加载指定 thread；无文件则空会话。
    static func load(threadId: String) -> ConversationState {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        guard let rec = LocalSessionStore.load(projectId: pid, threadId: threadId) else {
            return .empty(projectId: pid, threadId: threadId)
        }
        return ConversationState(
            projectId: pid,
            threadId: threadId,
            messages: rec.messages,
            boundEpicId: rec.flow?.epicId,
            flow: rec.flow,
            revision: rec.revision ?? 0
        )
    }

    /// 从本机盘加载指定项目的主会话（兼容旧 ::main 迁移）。
    static func load(projectId: String) -> ConversationState {
        let tid = LocalSessionStore.migrateLegacyThread(projectId: projectId)
        return load(threadId: tid)
    }

    /// 落盘；`revision` 自动 +1。`allowDowngrade` 透传 LocalSessionStore。
    static func save(
        _ state: ConversationState,
        title: String? = nil,
        needsHubSync: Bool = false,
        allowDowngrade: Bool = false
    ) {
        var flow = state.flow ?? FlowThreadSnapshot(
            epicId: state.boundEpicId,
            epic: nil,
            works: [],
            headline: "",
            recentEpics: [],
            emptyMessage: "编排空闲·等定稿下达（与对话故障无关）",
            fanoutHint: nil
        )
        if let bound = state.boundEpicId, !bound.isEmpty {
            flow.epicId = bound
        }
        let nextRev = state.revision &+ 1
        LocalSessionStore.saveMessages(
            projectId: state.projectId,
            threadId: state.threadId,
            messages: state.messages,
            title: title,
            flow: flow,
            needsHubSync: needsHubSync,
            allowDowngrade: allowDowngrade,
            revision: nextRev
        )
    }

    /// 是否视为「本机已有权威消息」（有则禁止 Hub GET 回写）
    static func hasLocalAuthority(projectId: String) -> Bool {
        let s = load(projectId: projectId)
        return LocalSessionStore.messageScore(s.messages) > 0
    }

    /// 列出项目的所有会话
    static func listThreads(projectId: String) -> [DesktopThread] {
        LocalSessionStore.threadsAsDesktop(projectId: projectId)
    }

    /// 创建新会话
    @discardableResult
    static func createThread(projectId: String, title: String = "新对话") -> String {
        let tid = LocalSessionStore.createThreadId(projectId: projectId)
        LocalSessionStore.saveMessages(
            projectId: projectId,
            threadId: tid,
            messages: [],
            title: title,
            allowDowngrade: true
        )
        return tid
    }

    /// 删除会话（存档到 _archive）
    static func archiveThread(threadId: String) {
        let pid = LocalSessionStore.projectId(fromThreadId: threadId)
        LocalSessionStore.archiveThread(projectId: pid, threadId: threadId)
    }
}
