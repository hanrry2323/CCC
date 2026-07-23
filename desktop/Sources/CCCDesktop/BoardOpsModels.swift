import Foundation

// MARK: - Board

struct BoardSnapshot: Codable {
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

struct BoardTask: Identifiable, Codable, Hashable {
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
    let resources_history: OpsResourcesHistoryResp?
    let logistics: OpsLogisticsResp?
    let control: OpsControlResp?
    let ready_to_dispatch: OpsReadyToDispatch?
    let recent_failures: [OpsFailureRow]?
    let abnormal_cards: [OpsAbnormalCard]?
    /// 总灯 green|amber|red（运维面 2026-07-24）
    let severity: String?
    let human_line: String?
    let alerts: [OpsHealthAlert]?
    let amber_notes: [String]?
    let domains: OpsHealthDomains?
}

struct OpsHealthAlert: Identifiable, Hashable, Decodable {
    let id: String
    let title: String
    let detail: String?
    let source: String?
    let severity: String?
    let copy_payload: String?
}

struct OpsHealthDomains: Decodable {
    let cluster: OpsDomainCluster?
    let agent_mcp: OpsDomainAgentMcp?
    let capacity: OpsDomainCapacity?
}

struct OpsDomainCluster: Decodable {
    let engine_running: Bool?
    let mode: String?
    let hub_port_7777: Bool?
    let ports: [OpsDomainPort]?
    let down_ports_n: Int?
    let alert_count: Int?
}

struct OpsDomainPort: Decodable {
    let port: Int?
    let ok: Bool?
}

struct OpsDomainAgentMcp: Decodable {
    let ok: Bool?
    let mcp_probed: Bool?
    let note: String?
}

struct OpsDomainCapacity: Decodable {
    let verdict: String?
    let note: String?
}

struct OpsControlResp: Decodable {
    let mode: String?
    let invent_hard_disabled: Bool?
    let engine_running: Bool?
    let hub_port_7777: Bool?
    let generated_at: String?
}

struct OpsReadyToDispatch: Decodable {
    let ok: Bool?
    let reason: String?
    let blockers: [String]?
    let invent_hard_disabled: Bool?
    let mode: String?
    let engine_running: Bool?
    let resource_verdict: String?
    let fleet_abnormal: Int?
}

struct OpsResourcesHistoryResp: Decodable {
    let summary: OpsResourcesHistorySummary?
    let sparklines: OpsResourcesSparklines?
}
struct OpsResourcesHistorySummary: Decodable {
    let verdict: String?
    let note: String?
    let reason: String?
    let load_p95: Double?
    let mem_p95: Double?
}
struct OpsResourcesSparklines: Decodable {
    let load_ratio: String?
    let mem_pct: String?
}

struct OpsFailureRow: Identifiable, Decodable, Hashable {
    var id: String { "\(workspace ?? "")-\(task_id ?? "")-\(ts ?? "")" }
    let workspace: String?
    let task_id: String?
    let reason: String?
    let role: String?
    let ts: String?
    let from_col: String?
    let to_col: String?
}

struct OpsAbnormalCard: Identifiable, Decodable, Hashable {
    var id: String { "\(workspace)-\(task_id ?? title ?? "")" }
    let workspace: String
    let task_id: String?
    let title: String?
    let note: String?
    let card_kind: String?
    let parent_id: String?
    let status: String?
}

struct OpsLogisticsResp: Decodable {
    let ammo_workspaces: [OpsAmmoWorkspace]?
    let daily_today: [OpsLogisticsDaily]?
    let docs_today: [OpsLogisticsDaily]?
    let spawn_hint_today: Int?
    let ops_auto_backlog: Int?
    let plist: OpsLogisticsPlist?
    let headline: String?
    let needs_attention: Bool?
    let note: String?
    let generated_at: String?
}
struct OpsAmmoWorkspace: Decodable, Hashable {
    let workspace: String?
    let path: String?
}
struct OpsLogisticsDaily: Identifiable, Decodable, Hashable {
    var id: String { "\(workspace)-\(path ?? mtime ?? "")" }
    let workspace: String
    let path: String?
    let decision: String?
    let mtime: String?
    let watermark: String?
}
struct OpsLogisticsPlist: Decodable {
    let agents: [OpsLogisticsAgent]?
    let any_loaded: Bool?
    let any_apply_ammo: Bool?
}
struct OpsLogisticsAgent: Identifiable, Decodable, Hashable {
    var id: String { label }
    let label: String
    let loaded: Bool?
    let plist: String?
    let apply_ammo: Bool?
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
    var id: String { "\(workspace ?? "")-\(file ?? "")" }
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
