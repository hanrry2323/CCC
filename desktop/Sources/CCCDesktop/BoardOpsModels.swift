import Foundation

// MARK: - Board

struct BoardSnapshot: Decodable {
    let columns: [String: [BoardTask]]?
    let workspace: String?
    let counts: [String: Int]?
}

struct BoardSummariesResp: Decodable {
    let summaries: [String: BoardSnapshot]
}

struct BoardTaskDetail: Identifiable, Decodable, Hashable {
    let id: String
    let title: String?
    let card_kind: String?
    let parent_id: String?
    let status: String?
    let note: String?
    let executor: String?
    let split_status: String?
    let acceptance: String?
    let phases: [BoardTaskPhase]?
    let events: [BoardTaskEvent]?

    var displayTitle: String { title ?? id }
    var isEpic: Bool {
        if let k = card_kind { return k == "epic" }
        return parent_id == nil || parent_id?.isEmpty == true
    }
}

struct BoardTaskPhase: Identifiable, Decodable, Hashable {
    var id: String { name }
    let name: String
    let status: String?
    let commit: String?
}

struct BoardTaskEvent: Identifiable, Decodable, Hashable {
    var id: String { "\(ts ?? "")-\(role ?? "")" }
    let ts: String?
    let role: String?
    let message: String?
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

// MARK: - Ops Summary (aggregated /api/ops/summary)

struct OpsSummary: Decodable {
    let overview: OpsOverview?
    let risks: OpsRisksResp?
    let workspaces: OpsWorkspacesResp?
    let daily: OpsDailyResp?
    let quality: OpsQualityResp?
    let docs: OpsDocsDebtResp?
    let kb: OpsKbHealthResp?
    let deploy: OpsDeployResp?
    let ports: OpsPortsResp?
    let auto: OpsAutoResp?
    let resources: OpsResourcesResp?
}

struct OpsWorkspacesResp: Decodable {
    let workspaces: [OpsWorkspaceSummary]?
}
struct OpsWorkspaceSummary: Identifiable, Decodable, Hashable {
    var id: String { workspace }
    let workspace: String
    let backlog: Int?
    let planned: Int?
    let in_progress: Int?
    let testing: Int?
    let verified: Int?
    let released: Int?
    let abnormal: Int?
    let epic_count: Int?
    let last_event: String?
}

struct OpsDailyResp: Decodable {
    let reports: [OpsDailyReport]?
    let latest: OpsDailyReport?
    let latest_body: String?
    let generated_at: String?
}
struct OpsDailyReport: Identifiable, Decodable, Hashable {
    var id: String { "\(workspace)-\(name)" }
    let workspace: String
    let name: String
    let path: String?
    let mtime: String?
    let size: Int?
}

struct OpsQualityResp: Decodable {
    let workspaces: [OpsQualityDigest]?
    let generated_at: String?
}
struct OpsQualityDigest: Identifiable, Decodable, Hashable {
    var id: String { workspace }
    let workspace: String
    let commits_24h: Int?
    let commit_sample: [String]?
    let released_total: Int?
    let hint: String?
}

struct OpsDocsDebtResp: Decodable {
    let items: [OpsDocsDebtItem]?
    let count: Int?
    let generated_at: String?
}
struct OpsDocsDebtItem: Identifiable, Decodable, Hashable {
    var id: String { "\(workspace)-\(file ?? "")" }
    let workspace: String?
    let file: String?
    let issue: String?
}

struct OpsKbHealthResp: Decodable {
    let ok: Bool?
    let note: String?
}
struct OpsDeployResp: Decodable {
    let targets: [String]?
}
struct OpsPortsResp: Decodable {
    let ports: [OpsDownPort]?
}
struct OpsAutoResp: Decodable {
    let tasks: [OpsAutoTask]?
}
struct OpsAutoTask: Identifiable, Decodable, Hashable {
    var id: String { "\(workspace ?? "")-\(title ?? "")" }
    let workspace: String?
    let title: String?
    let description: String?
    let tags: [String]?
}
struct OpsResourcesResp: Decodable {
    let cpu: Double?
    let mem_pct: Double?
    let disk_pct: Double?
}
