import Foundation

struct DesktopProject: Identifiable, Codable, Hashable {
    let id: String
    let name: String
    let path: String
    let workspace: String?
    let role: String?
    let engine_eligible: Bool?

    var isDispatchable: Bool {
        (engine_eligible ?? true) && (role ?? "app") != "orch"
    }

    var isOrch: Bool {
        (role ?? "") == "orch" || !(engine_eligible ?? true)
    }
}

struct DesktopThread: Identifiable, Codable, Hashable {
    var id: String { thread_id }
    let thread_id: String
    var title: String?
    let updated_at: String?
    let project_id: String?
}

struct ChatMessage: Identifiable, Hashable {
    let id: UUID
    var role: String
    var content: String
    var isStreaming: Bool
    var toolSteps: [ToolStep]
    var filesChanged: Int
    var toolsFinished: Bool
    /// 本轮写入路径（工程师模式 Review；导出可选）
    var changedFilePaths: [String]
    /// "chat" | "summary"（已压缩 N 轮的占位卡片）
    var kind: String
    /// summary 卡片：被压缩的轮数
    var summaryRounds: Int
    /// 工具运行期间的阶段性短句（status 事件；下一条 delta 前显示）
    var transientNote: String?
    /// 消息是否已编辑（Phase 1.5）
    var edited: Bool
    /// 消息引用（Phase 1.7）
    var replyTo: String?
    /// UI 展示文案（快捷条短标签）；nil 则显示 content。发给 Agent 仍用 content。
    var displayContent: String?

    init(
        id: UUID = UUID(),
        role: String,
        content: String,
        isStreaming: Bool = false,
        toolSteps: [ToolStep] = [],
        filesChanged: Int = 0,
        toolsFinished: Bool = false,
        changedFilePaths: [String] = [],
        kind: String = "chat",
        summaryRounds: Int = 0,
        transientNote: String? = nil,
        edited: Bool = false,
        replyTo: String? = nil,
        displayContent: String? = nil
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.isStreaming = isStreaming
        self.toolSteps = toolSteps
        self.filesChanged = filesChanged
        self.toolsFinished = toolsFinished
        self.changedFilePaths = changedFilePaths
        self.kind = kind
        self.summaryRounds = summaryRounds
        self.transientNote = transientNote
        self.edited = edited
        self.replyTo = replyTo
        self.displayContent = displayContent
    }

    /// 气泡/列表展示用
    var visibleContent: String {
        let d = displayContent?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return d.isEmpty ? content : d
    }
}

extension ChatMessage: Codable {
    enum CodingKeys: String, CodingKey {
        case id
        case role, content
        case tool_steps
        case files_changed
        case tools_finished
        case changed_file_paths
        case kind
        case summary_rounds
        case transient_note
        case edited
        case reply_to
        case display_content
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        if let raw = try c.decodeIfPresent(String.self, forKey: .id),
           let uuid = UUID(uuidString: raw) {
            id = uuid
        } else {
            id = UUID()
        }
        role = try c.decode(String.self, forKey: .role)
        content = try c.decodeIfPresent(String.self, forKey: .content) ?? ""
        isStreaming = false
        toolSteps = try c.decodeIfPresent([ToolStep].self, forKey: .tool_steps) ?? []
        filesChanged = try c.decodeIfPresent(Int.self, forKey: .files_changed) ?? 0
        toolsFinished = try c.decodeIfPresent(Bool.self, forKey: .tools_finished)
            ?? !toolSteps.isEmpty
        changedFilePaths = try c.decodeIfPresent([String].self, forKey: .changed_file_paths) ?? []
        kind = try c.decodeIfPresent(String.self, forKey: .kind) ?? "chat"
        summaryRounds = try c.decodeIfPresent(Int.self, forKey: .summary_rounds) ?? 0
        transientNote = try c.decodeIfPresent(String.self, forKey: .transient_note)
        edited = try c.decodeIfPresent(Bool.self, forKey: .edited) ?? false
        replyTo = try c.decodeIfPresent(String.self, forKey: .reply_to)
        displayContent = try c.decodeIfPresent(String.self, forKey: .display_content)
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id.uuidString, forKey: .id)
        try c.encode(role, forKey: .role)
        try c.encode(content, forKey: .content)
        if !toolSteps.isEmpty {
            try c.encode(toolSteps, forKey: .tool_steps)
        }
        if filesChanged > 0 {
            try c.encode(filesChanged, forKey: .files_changed)
        }
        if toolsFinished || !toolSteps.isEmpty {
            try c.encode(toolsFinished, forKey: .tools_finished)
        }
        if !changedFilePaths.isEmpty {
            try c.encode(changedFilePaths, forKey: .changed_file_paths)
        }
        if kind != "chat" {
            try c.encode(kind, forKey: .kind)
            try c.encode(summaryRounds, forKey: .summary_rounds)
        }
        if let note = transientNote, !note.isEmpty {
            try c.encode(note, forKey: .transient_note)
        }
        if edited {
            try c.encode(true, forKey: .edited)
        }
        if let replyTo {
            try c.encode(replyTo, forKey: .reply_to)
        }
        if let displayContent, !displayContent.isEmpty {
            try c.encode(displayContent, forKey: .display_content)
        }
    }
}

enum ChatStreamEvent: Sendable {
    /// 心跳（connect / idle）
    case ping(turnId: String?)
    case delta(String, turnId: String?)
    /// 工具运行期间的阶段性短句（区别于主通道 delta）
    case status(String, turnId: String?)
    case toolUse(name: String, input: [String: String], turnId: String?)
    case toolResult(ok: Bool, turnId: String?)
    case cost(tokens: Int?, usd: Double?, turnId: String?)
    /// partial=true：服务端标明半截（断连/超时/异常），UI 必须标「回复中断」
    /// claudeSessionId：服务端会话 id，下轮 resume 用（持续对话）
    case done(partial: Bool, claudeSessionId: String?, turnId: String?, metrics: ChatTurnMetrics?)
}

struct ChatTurnMetrics: Sendable {
    let durationMs: Int?
    let eventCounts: [String: Int]
}

enum SidebarDestination: String, CaseIterable, Identifiable {
    case chat, board, ops
    var id: String { rawValue }

    var title: String {
        switch self {
        case .chat: return "对话"
        case .board: return "看板"
        case .ops: return "运维"
        }
    }

    var systemImage: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right.fill"
        case .board: return "square.grid.2x2.fill"
        case .ops: return "wrench.and.screwdriver.fill"
        }
    }
}

// MARK: - Phase 1.3: Token usage

extension ChatMessage {
    var tokens: Int { content.count / 4 }
}

// MARK: - Flow persistence types (kept for FlowThreadSnapshot compatibility)

struct FlowWork: Identifiable, Codable, Hashable {
    var id: String { workId }
    let workId: String
    let title: String
    let status: String
    let executor: String
    let dependsOn: [String]
    let userStatus: String?
    let executorLabel: String?
    let dependsOnTitles: [String]?
    let note: String?
    let failureNote: String?

    enum CodingKeys: String, CodingKey {
        case workId = "id"
        case title, status, executor, note
        case dependsOn = "depends_on"
        case userStatus = "user_status"
        case executorLabel = "executor_label"
        case dependsOnTitles = "depends_on_titles"
        case failureNote = "failure_note"
    }

    var displayStatus: String { userStatus ?? Self.mapStatus(status) }
    var displayExecutor: String { executorLabel ?? Self.mapExecutor(executor) }

    var isActive: Bool { ["in_progress", "testing"].contains(status) }
    var isFailed: Bool { status == "abnormal" }
    var isDone: Bool { ["released", "verified"].contains(status) }

    static func mapStatus(_ s: String) -> String {
        switch s {
        case "planned": return "排队"
        case "in_progress": return "执行中"
        case "testing": return "验收中"
        case "verified", "released": return "已完成"
        case "abnormal": return "异常"
        default: return s
        }
    }

    static func mapExecutor(_ e: String) -> String {
        switch e.lowercased() {
        case "opencode": return "写码"
        case "python": return "脚本"
        case "ollama": return "本地模型"
        case "cli": return "命令行"
        default: return e
        }
    }
}

struct FlowEpic: Codable, Hashable {
    let id: String?
    let title: String?
    let split_status: String?
    let column: String?
    let goal_summary: String?
    let pipeline: String?
    let user_stage: String?
    let headline: String?
    let description: String?
}

struct FlowEpicRef: Identifiable, Codable, Hashable {
    var id: String { epic_id }
    let epic_id: String
    let title: String?
    let updated_at: String?
    let thread_id: String?
    var user_stage: String?
}

// MARK: - Flow persistence model

struct FlowThreadSnapshot: Codable, Hashable {
    var epicId: String?
    var epic: FlowEpic?
    var works: [FlowWork]
    var headline: String
    var recentEpics: [FlowEpicRef]
    var emptyMessage: String
    var fanoutHint: String?

    init(
        epicId: String? = nil,
        epic: FlowEpic? = nil,
        works: [FlowWork] = [],
        headline: String = "",
        recentEpics: [FlowEpicRef] = [],
        emptyMessage: String = "编排空闲·等定稿下达（与对话故障无关）",
        fanoutHint: String? = nil
    ) {
        self.epicId = epicId
        self.epic = epic
        self.works = works
        self.headline = headline
        self.recentEpics = recentEpics
        self.emptyMessage = emptyMessage
        self.fanoutHint = fanoutHint
    }
}

// MARK: - Composer Attachment

struct ComposerAttachment: Identifiable, Hashable, Equatable {
    let id: UUID
    var path: String
    var isImage: Bool

    init(id: UUID = UUID(), path: String, isImage: Bool = false) {
        self.id = id
        self.path = path
        let lower = path.lowercased()
        self.isImage = isImage
            || lower.hasSuffix(".png")
            || lower.hasSuffix(".jpg")
            || lower.hasSuffix(".jpeg")
            || lower.hasSuffix(".gif")
            || lower.hasSuffix(".webp")
    }
}

// MARK: - Inbox Proposal

struct InboxProposalsResp: Decodable {
    let ok: Bool?
    let proposals: [InboxProposal]?
}

struct InboxProposal: Identifiable, Decodable, Hashable {
    let id: String
    let project_id: String?
    let title: String?
    let status: String?
    let complexity: String?
    let path: String?
}

// MARK: - Custom Quick Prompt

struct QuickPromptItem: Identifiable, Codable, Hashable {
    var id: String { title }
    var title: String
    var prompt: String
}

// MARK: - Manual Epic Form

struct ManualEpicForm: Equatable {
    var title: String = ""
    var goal: String = ""
    var acceptance: String = ""
    var pipeline: String = "dev"
    var executor: String = "opencode"
    var complexity: String = "medium"
    var priority: String = "p2"
}

// MARK: - Task Template

struct TaskTemplate: Identifiable, Codable, Hashable {
    var id: String { title + pipeline }
    var title: String
    var goal: String
    var acceptance: String
    var pipeline: String
    var executor: String
    var complexity: String
    var priority: String
    var tags: [String]
}

// MARK: - Phase model

struct Phase: Identifiable, Codable, Hashable {
    var id: String { name }
    let name: String
    let status: String
    let executor: String
    let dependsOn: [String]

    enum CodingKeys: String, CodingKey {
        case name, status, executor
        case dependsOn = "depends_on"
    }
}

// MARK: - Project Stats

struct ProjectStats: Equatable {
    var totalEpics: Int = 0
    var activeWorks: Int = 0
    var failedWorks: Int = 0
    var completedToday: Int = 0
}

