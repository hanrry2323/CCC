import Foundation

/// 项目即对话：按 `projectId` 的会话状态（磁盘为 SSOT；此为 RAM/契约投影）。
struct ConversationState: Equatable {
    var projectId: String
    /// 恒为 `{projectId}::main`
    var conversationId: String
    var messages: [ChatMessage]
    /// 右栏绑定 SSOT（随会话落盘；Hub 空列表不得冲掉）
    var boundEpicId: String?
    var flow: FlowThreadSnapshot?
    /// 单调修订；拒绝更旧写入（预留；落盘时递增）
    var revision: UInt64

    static func empty(projectId: String) -> ConversationState {
        let cid = LocalSessionStore.conversationThreadId(for: projectId)
        return ConversationState(
            projectId: projectId,
            conversationId: cid,
            messages: [],
            boundEpicId: nil,
            flow: nil,
            revision: 0
        )
    }
}

/// 会话读写门面：身份收敛 + 落盘闭包用的 (projectId, conversationId)。
enum ConversationStore {
    static func conversationId(for projectId: String) -> String {
        LocalSessionStore.conversationThreadId(for: projectId)
    }

    /// 从本机盘加载；无文件则空会话。
    static func load(projectId: String) -> ConversationState {
        let cid = conversationId(for: projectId)
        guard let rec = LocalSessionStore.load(projectId: projectId, threadId: cid) else {
            return .empty(projectId: projectId)
        }
        return ConversationState(
            projectId: projectId,
            conversationId: cid,
            messages: rec.messages,
            boundEpicId: rec.flow?.epicId,
            flow: rec.flow,
            revision: rec.revision ?? 0
        )
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
            threadId: state.conversationId,
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
}
