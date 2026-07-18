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
    let title: String?
    let updated_at: String?
    let project_id: String?
}

struct ChatMessage: Identifiable, Hashable {
    let id: UUID
    let role: String
    let content: String

    init(id: UUID = UUID(), role: String, content: String) {
        self.id = id
        self.role = role
        self.content = content
    }
}

extension ChatMessage: Codable {
    enum CodingKeys: String, CodingKey { case role, content }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = UUID()
        role = try c.decode(String.self, forKey: .role)
        content = try c.decode(String.self, forKey: .content)
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

    enum CodingKeys: String, CodingKey {
        case workId = "id"
        case title, status, executor
        case dependsOn = "depends_on"
    }

    var isActive: Bool {
        ["in_progress", "testing", "planned"].contains(status)
    }

    var isTerminalDone: Bool {
        ["released", "verified"].contains(status)
    }

    var isFailed: Bool { status == "abnormal" }
}

struct FlowEpic: Codable, Hashable {
    let id: String?
    let title: String?
    let split_status: String?
    let column: String?
}

struct FlowSnapshot: Codable {
    let ok: Bool?
    let empty: Bool?
    let message: String?
    let project_id: String?
    let epic_id: String?
    let epic: FlowEpic?
    let works: [FlowWork]?
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
}

struct GateError: Decodable, Hashable {
    let code: String?
    let message: String?
}

struct APIErrorBody: Decodable {
    let ok: Bool?
    let error: String?
    let errors: [GateError]?
    let detail: String?
}

enum SidebarDestination: String, CaseIterable, Identifiable {
    case chat
    case hub
    case ops

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
