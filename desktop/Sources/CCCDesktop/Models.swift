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

    init(id: UUID = UUID(), role: String, content: String, isStreaming: Bool = false) {
        self.id = id
        self.role = role
        self.content = content
        self.isStreaming = isStreaming
    }
}

extension ChatMessage: Codable {
    enum CodingKeys: String, CodingKey { case role, content }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = UUID()
        role = try c.decode(String.self, forKey: .role)
        content = try c.decode(String.self, forKey: .content)
        isStreaming = false
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(role, forKey: .role)
        try c.encode(content, forKey: .content)
    }
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
    case chat, hub, ops
    var id: String { rawValue }

    var title: String {
        switch self {
        case .chat: return "对话"
        case .hub: return "Hub"
        case .ops: return "运维"
        }
    }

    var systemImage: String {
        switch self {
        case .chat: return "bubble.left.and.bubble.right.fill"
        case .hub: return "square.grid.2x2.fill"
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
