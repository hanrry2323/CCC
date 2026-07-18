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
}

struct DesktopThread: Identifiable, Codable, Hashable {
    var id: String { thread_id }
    let thread_id: String
    let title: String?
    let updated_at: String?
    let project_id: String?
}

struct ChatMessage: Identifiable, Codable, Hashable {
    var id: String { "\(role)-\(content.prefix(40))-\(content.count)" }
    let role: String
    let content: String
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
}

struct FlowSnapshot: Codable {
    let ok: Bool?
    let empty: Bool?
    let message: String?
    let project_id: String?
    let epic_id: String?
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
