import Foundation

// MARK: - Board

struct BoardSnapshot: Decodable {
    let columns: [String: [BoardTask]]?
    let workspace: String?
    let counts: [String: Int]?
}

struct BoardTask: Identifiable, Decodable, Hashable {
    let id: String
    let title: String?
    let card_kind: String?
    let parent_id: String?
    let status: String?
    let note: String?
    let executor: String?
    let split_status: String?

    var displayTitle: String { title ?? id }

    var isEpic: Bool {
        if let k = card_kind { return k == "epic" }
        return parent_id == nil || parent_id?.isEmpty == true
    }
}

// MARK: - Ops

struct OpsOverview: Decodable {
    let machines: [OpsMachine]?
    let alert_count: Int?
    let down_ports: [OpsDownPort]?
    let generated_at: String?
}

struct OpsMachine: Identifiable, Decodable, Hashable {
    var id: String { "\(name)-\(ip)" }
    let name: String
    let ip: String
    let role: String?
    let reachable: Bool?
    let alive_ports: Int?
    let port_count: Int?
}

struct OpsDownPort: Identifiable, Decodable, Hashable {
    var id: String { "\(host)-\(port)-\(name)" }
    let port: Int
    let name: String
    let host: String
}

struct OpsRisksResp: Decodable {
    let count: Int?
    let high: Int?
    let risks: [OpsRisk]?
}

struct OpsRisk: Identifiable, Hashable {
    let id: String
    let title: String
    let detail: String
    let severity: String
}

extension OpsRisk: Decodable {
    enum CodingKeys: String, CodingKey {
        case title, detail, severity, message, level, name, id
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let t = (try? c.decode(String.self, forKey: .title))
            ?? (try? c.decode(String.self, forKey: .name))
            ?? "风险"
        let d = (try? c.decode(String.self, forKey: .detail))
            ?? (try? c.decode(String.self, forKey: .message))
            ?? ""
        let s = (try? c.decode(String.self, forKey: .severity))
            ?? (try? c.decode(String.self, forKey: .level))
            ?? "info"
        let rid = (try? c.decode(String.self, forKey: .id)) ?? "\(t)-\(d.prefix(24))"
        id = rid
        title = t
        detail = d
        severity = s
    }
}

struct ProjectBaselineResp: Decodable {
    let prompt: String?
}
