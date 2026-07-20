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
        replyTo: String? = nil
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
    }
}

enum ChatStreamEvent: Sendable {
    /// sidecar 心跳（connect / idle）；UI 显示「连接本机 Agent…」
    case ping
    case delta(String)
    /// 工具运行期间的阶段性短句（区别于主通道 delta）
    case status(String)
    case toolUse(name: String, input: [String: String])
    case toolResult(ok: Bool)
    case cost(tokens: Int?, usd: Double?)
    /// partial=true：服务端标明半截（断连/超时/异常），UI 必须标「回复中断」
    /// claudeSessionId：sidecar/loop-code 会话 id，下轮 resume 用（持续对话）
    case done(partial: Bool, claudeSessionId: String?)
}

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
}

struct FlowSnapshot: Codable {
    let ok: Bool?
    let empty: Bool?
    let message: String?
    let project_id: String?
    let epic_id: String?
    let epic: FlowEpic?
    let works: [FlowWork]?
    let headline: String?
    let user_stage: String?
}

struct TransferRequest: Encodable {
    let project_id: String
    let thread_id: String?
    let title: String
    let goal: String
    let acceptance: [String]
    let pipeline: String
    let feasibility: String
    let feasibility_reason: String?
    let executor_intent: String
    let skills_hint: [String]
    let plan_md: String
    let complexity: String
    /// Hub API v1 幂等键；重复提交返回已有 epic
    let client_request_id: String?
}

struct TransferResponse: Decodable {
    let ok: Bool?
    let epic_id: String?
    let workspace: String?
    let column: String?
    let error: String?
    let errors: [GateError]?
    let executor_intent: String?
    let engine_wake: EngineWakeInfo?
    let idempotent_replay: Bool?
}

/// 投递三态（hub-shell-roadmap / hub-api-v1）
enum TransferDeliveryPhase: String, Codable, Equatable {
    case draft
    case queued
    case delivering
    case delivered
    case accepted
    case failed

    var label: String {
        switch self {
        case .draft: return "本机草稿"
        case .queued: return "待投递"
        case .delivering: return "投递中"
        case .delivered: return "已投递"
        case .accepted: return "编排已受理"
        case .failed: return "投递失败"
        }
    }
}

struct EngineWakeInfo: Decodable, Hashable {
    let ok: Bool?
    let mode: String?
    let message: String?
}

struct GateError: Decodable, Hashable {
    let code: String?
    let message: String?

    /// 门禁错误码中文
    var localized: String {
        let c = code ?? ""
        switch c {
        case "missing_title": return "缺少标题"
        case "missing_goal": return "缺少目标"
        case "missing_acceptance": return "缺少验收"
        case "missing_pipeline": return "缺少产线"
        case "feasibility_blocked": return "可行性未通过：\(message ?? "")"
        case "project_not_dispatchable": return "当前项目不可下达"
        case "invalid_executor_intent": return "未知执行面"
        case "invalid_epic_id": return "任务 ID 非法"
        default:
            if let message, !message.isEmpty { return message }
            return c.isEmpty ? "门禁未通过" : c
        }
    }
}

struct APIErrorBody: Decodable {
    let ok: Bool?
    let error: String?
    let errors: [GateError]?
    let detail: String?
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

/// 流程图布局节点
struct FlowGraphNode: Identifiable, Hashable {
    enum Kind: Hashable { case epic, work }
    let id: String
    let kind: Kind
    let title: String
    let subtitle: String
    let statusKey: String
    let badge: String
    let detail: String?
    var x: CGFloat = 0
    var y: CGFloat = 0
}

struct FlowGraphEdge: Identifiable, Hashable {
    var id: String { "\(from)-\(to)" }
    let from: String
    let to: String
    let active: Bool
}

/// 节点详情（点击右栏节点）
struct FlowNodeDetail: Identifiable, Hashable {
    let id: String
    let kind: String
    let title: String
    let status: String
    let body: String
}

// MARK: - Phase 1.3: Token usage

extension ChatMessage {
    var tokens: Int { content.count / 4 }
}

// MARK: - Phase 1.4: Custom Quick Prompt

struct QuickPromptItem: Identifiable, Codable, Hashable {
    var id: String { title }
    var title: String
    var prompt: String
}

// MARK: - Phase 2.1: Manual Epic Form

struct ManualEpicForm: Equatable {
    var title: String = ""
    var goal: String = ""
    var acceptance: String = ""
    var pipeline: String = "dev"
    var executor: String = "opencode"
    var complexity: String = "medium"
    var priority: String = "p2"
}

// MARK: - Phase 2.2: Task Template

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

// MARK: - Phase 2.4: Task Artifacts

struct TaskArtifacts: Codable, Hashable {
    var planMd: String = ""
    var phasesJsonl: String = ""
    var reportMd: String = ""
    var reviewMd: String = ""
    var verdictMd: String = ""
}

// MARK: - Phase 2.5: Phase model

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

// MARK: - Phase 3.3: Failure Record

struct FailureRecord: Identifiable, Codable, Hashable {
    var id: String { "\(ts)-\(task_id)" }
    let ts: String
    let task_id: String
    let role: String
    let reason: String
    let exit_code: Int?
    let stderr_tail: String?
    let workspace: String?
}

// MARK: - Phase 3.4: Project Stats

struct ProjectStats: Equatable {
    var totalEpics: Int = 0
    var activeWorks: Int = 0
    var failedWorks: Int = 0
    var completedToday: Int = 0
}

// MARK: - Phase 4.1: Priority

enum TaskPriority: String, CaseIterable, Codable {
    case p0 = "p0"
    case p1 = "p1"
    case p2 = "p2"
    case p3 = "p3"

    var label: String {
        switch self {
        case .p0: return "P0 🔴"
        case .p1: return "P1 🟡"
        case .p2: return "P2 🟢"
        case .p3: return "P3 ⚪"
        }
    }

    var color: String {
        switch self {
        case .p0: return "critical"
        case .p1: return "warning"
        case .p2: return "ok"
        case .p3: return "muted"
        }
    }
}
