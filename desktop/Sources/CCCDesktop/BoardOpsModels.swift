import Foundation

// MARK: - Board

struct BoardSnapshot: Codable {
    let columns: [String: [BoardTask]]?
    let workspace: String?
    let counts: [String: Int]?
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
    let agent_minds: OpsAgentMindsResp?
}

struct OpsAgentMindsResp: Decodable {
    let ok: Bool?
    let items: [OpsAgentMindItem]?
    let error: String?
}

struct OpsAgentMindItem: Identifiable, Decodable, Hashable {
    var id: String { project_id }
    let project_id: String
    let as_of: String?
    let board_summary: String?
    let daily: String?
    let weekly: String?
    let constraints_n: Int?
    let error: String?
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
    let relay: OpsDomainRelay?
    // v0.62.0 阶段 4:claude --bg 长 session 跟踪(Engine tick 30s 更新)
    let bg_sessions: OpsDomainBGSessions?
}

// v0.62.0 阶段 4:claude --bg 长 session 子域(后端 _ops_probe._build_bg_sessions_domain)
struct OpsDomainBGSessions: Decodable, Hashable {
    let ok: Bool?           // true=全活 / false=全死 / nil=未拉取或部分活
    let count: Int?
    let alive_count: Int?
    let sessions: [OpsDomainBGSession]?
    let note: String?

    // v0.62.0(P1-8):自定义 init(from:),类型错返 nil 而非 throw,
    // 避免整个 OpsHealthDomains 解码失败导致 OpsView 全部卡片消失。
    private enum CodingKeys: String, CodingKey {
        case ok, count, alive_count, sessions, note
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        ok = try? c.decode(Bool.self, forKey: .ok)
        count = try? c.decode(Int.self, forKey: .count)
        alive_count = try? c.decode(Int.self, forKey: .alive_count)
        sessions = try? c.decode([OpsDomainBGSession].self, forKey: .sessions)
        note = try? c.decode(String.self, forKey: .note)
    }
}

struct OpsDomainBGSession: Decodable, Hashable {
    let task_id: String?
    let role: String?
    let session_id: String?
    let pid: Int?
    let model: String?
    let started_at: Double?
    let last_heartbeat: Double?
    let age_min: Int?
    let alive: Bool?
    let idle_timeout: Bool?

    // v0.62.0(P1-8):与 OpsDomainBGSessions 同防御,类型错返 nil
    private enum CodingKeys: String, CodingKey {
        case task_id, role, session_id, pid, model,
             started_at, last_heartbeat, age_min, alive, idle_timeout
    }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        task_id = try? c.decode(String.self, forKey: .task_id)
        role = try? c.decode(String.self, forKey: .role)
        session_id = try? c.decode(String.self, forKey: .session_id)
        pid = try? c.decode(Int.self, forKey: .pid)
        model = try? c.decode(String.self, forKey: .model)
        started_at = try? c.decode(Double.self, forKey: .started_at)
        last_heartbeat = try? c.decode(Double.self, forKey: .last_heartbeat)
        age_min = try? c.decode(Int.self, forKey: .age_min)
        alive = try? c.decode(Bool.self, forKey: .alive)
        idle_timeout = try? c.decode(Bool.self, forKey: .idle_timeout)
    }
}

struct OpsDomainCluster: Decodable {
    let engine_running: Bool?
    let mode: String?
    // T40: hub_port_7777 已退役（Hub :7777 不再存在）；服务端仍可能返回此字段，Swift Decodable 自动忽略
    let ports: [OpsDomainPort]?
    let down_ports_n: Int?
    let alert_count: Int?
}

struct OpsDomainPort: Decodable {
    let port: Int?
    let ok: Bool?
}

/// `domains.agent_mcp`：MCP 探针清单；未配置≠红，断连/探测失败才红。
struct OpsDomainAgentMcp: Decodable {
    let ok: Bool?
    let mcp_probed: Bool?
    let note: String?
    let servers: [OpsDomainMcpServer]?
    let list: [String]?
    let failed: [String]?
    let configured_n: Int?
    let failed_n: Int?
    let copy_payload: String?
    let status: String?

    private enum CodingKeys: String, CodingKey {
        case ok, mcp_probed, note, servers, list, failed
        case configured_n, failed_n, copy_payload, status
        case items
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        ok = try? c.decode(Bool.self, forKey: .ok)
        mcp_probed = try? c.decode(Bool.self, forKey: .mcp_probed)
        note = try? c.decode(String.self, forKey: .note)
        servers = (try? c.decode([OpsDomainMcpServer].self, forKey: .servers))
            ?? (try? c.decode([OpsDomainMcpServer].self, forKey: .items))
        list = try? c.decode([String].self, forKey: .list)
        failed = try? c.decode([String].self, forKey: .failed)
        configured_n = try? c.decode(Int.self, forKey: .configured_n)
        failed_n = try? c.decode(Int.self, forKey: .failed_n)
        copy_payload = try? c.decode(String.self, forKey: .copy_payload)
        status = try? c.decode(String.self, forKey: .status)
    }

    /// 断连/探测失败 → 红；未探/未配置 → 不红
    var isRedFailure: Bool {
        if mcp_probed != true { return false }
        if ok == false { return true }
        if let failed, !failed.isEmpty { return true }
        if let n = failed_n, n > 0 { return true }
        if let servers, servers.contains(where: { $0.ok == false }) { return true }
        let st = (status ?? "").lowercased()
        return st == "failed" || st == "error" || st == "down"
    }

    var isUnconfigured: Bool {
        if mcp_probed != true { return true }
        if ok == nil {
            let n = configured_n ?? servers?.count ?? list?.count ?? 0
            return n == 0
        }
        let st = (status ?? "").lowercased()
        return st == "unconfigured" || st == "none" || st == "empty"
    }

    var failedCount: Int {
        if let failed, !failed.isEmpty { return failed.count }
        if let n = failed_n { return n }
        return servers?.filter { $0.ok == false }.count ?? 0
    }

    var configuredCount: Int {
        configured_n ?? servers?.count ?? list?.count ?? 0
    }
}

struct OpsDomainMcpServer: Identifiable, Decodable, Hashable {
    var id: String { name ?? detail ?? "mcp" }
    let name: String?
    let ok: Bool?
    let detail: String?
    let source: String?
    let type: String?

    private enum CodingKeys: String, CodingKey {
        case name, ok, detail, id, server, error, source, type
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = (try? c.decode(String.self, forKey: .name))
            ?? (try? c.decode(String.self, forKey: .server))
            ?? (try? c.decode(String.self, forKey: .id))
        ok = try? c.decode(Bool.self, forKey: .ok)
        detail = (try? c.decode(String.self, forKey: .detail))
            ?? (try? c.decode(String.self, forKey: .error))
        source = try? c.decode(String.self, forKey: .source)
        type = try? c.decode(String.self, forKey: .type)
    }
}

// MARK: - Ops display merge (服务端 severity + MCP)

enum OpsHealthDisplay {
    /// 服务端 alerts + domains.agent_mcp + 本地 ~/.ccc/alerts/ 巡查告警（去重）
    static func alerts(summary: OpsSummary?, localPatrol: [OpsHealthAlert] = []) -> [OpsHealthAlert] {
        var list = summary?.alerts ?? []
        if let mcp = summary?.domains?.agent_mcp, mcp.isRedFailure {
            let already = list.contains {
                let id = $0.id.lowercased()
                let src = ($0.source ?? "").lowercased()
                return id.contains("mcp")
                    || src.contains("mcp")
                    || id == "agent-mcp-down"
                    || id == "mcp-probe-failed"
            }
            if !already {
                let failedNames = mcp.failed
                    ?? (mcp.servers ?? []).filter { $0.ok == false }.compactMap(\.name)
                let detail: String = {
                    if let n = mcp.note, !n.isEmpty { return n }
                    if !failedNames.isEmpty {
                        return "失败：\(failedNames.joined(separator: ", "))"
                    }
                    if mcp.failedCount > 0 { return "\(mcp.failedCount) 个 MCP 探测失败" }
                    return "MCP 探针失败"
                }()
                let trimmed = mcp.copy_payload?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                let payload = trimmed.isEmpty ? """
                【CCC 运维红灯】请排查并修复（系统/配置问题，不是业务意图）
                标题：MCP 探针失败
                影响：对话 Agent 工具链可能不可用
                来源：agent_mcp
                详情：\(detail)
                建议：查 MCP 配置 / 服务端 domains.agent_mcp
                机器字段：{"id":"mcp-probe-failed","source":"mcp","mcp_probed":true}
                """ : trimmed
                list.append(
                    OpsHealthAlert(
                        id: "mcp-probe-failed",
                        title: "MCP 探针失败",
                        detail: detail,
                        source: "mcp",
                        severity: "red",
                        copy_payload: payload
                    )
                )
            }
        }
        // 本地 ~/.ccc/alerts/ 巡查告警（按 source+title 去重）
        for patrol in localPatrol {
            if !list.contains(where: { $0.source == patrol.source && $0.title == patrol.title }) {
                list.append(patrol)
            }
        }
        return list
    }

    static func severity(summary: OpsSummary?, localPatrol: [OpsHealthAlert] = []) -> String {
        if summary?.domains?.agent_mcp?.isRedFailure == true { return "red" }
        if !localPatrol.isEmpty { return "red" }
        // T40: 服务端 severity（Hub 旧名仅作历史注释，字段名 summary.severity 不变）
        let remote = (summary?.severity ?? "").lowercased()
        if remote == "red" { return "red" }
        if remote == "amber" || remote == "orange" { return "amber" }
        if remote == "green" { return "green" }
        if summary?.ready_to_dispatch?.ok == false { return "red" }
        if summary != nil { return "green" }
        return "amber"
    }

    static func humanLine(summary: OpsSummary?, severity: String) -> String {
        if let mcp = summary?.domains?.agent_mcp, mcp.isRedFailure {
            return "MCP 异常 · 请交给 Agent"
        }
        if let line = summary?.human_line, !line.isEmpty {
            return line
        }
        switch severity {
        case "green": return "系统健康 · 可以放心开发和下任务"
        case "red": return "请交给 Agent 处理红灯"
        default: return "有轻度提示，不挡开发"
        }
    }
}

// CCC Relay 2026-07-25:三档 tier 用量 + 健康(后端 _ops_probe._build_relay_domain)
struct OpsDomainRelay: Decodable, Hashable {
    let ok: Bool?
    let source: String?
    let host: String?
    let port: Int?
    let note: String?
    let tiers: [String: OpsDomainRelayTier]?
    let total: OpsDomainRelayTotal?
}

struct OpsDomainRelayTier: Decodable, Hashable {
    let requests_today: Int?
    let tokens_today: Int?
    let upstreams: Int?
    let healthy: Int?
}

struct OpsDomainRelayTotal: Decodable, Hashable {
    let upstreams: Int?
    let healthy: Int?
    let requests_today: Int?
    let tokens_today: Int?
}

struct OpsDomainCapacity: Decodable {
    let verdict: String?
    let note: String?
}

struct OpsControlResp: Decodable {
    let mode: String?
    let invent_hard_disabled: Bool?
    let engine_running: Bool?
    // T40: hub_port_7777 已退役；服务端仍可能返回，Swift Decodable 自动忽略
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

// MARK: - Upstream daily (GET /api/ops/upstream-daily)

struct OpsUpstreamDailyResp: Decodable {
    let ok: Bool?
    let upstreams: [OpsUpstreamDailyRow]?
    let tier_totals: [String: OpsUpstreamTierTotal]?
    let total_requests: Int?
    let total_tokens: Int?
    let total_cost: Double?
}

struct OpsUpstreamDailyRow: Identifiable, Decodable, Hashable {
    var id: String { name }
    let name: String
    let tier: String?
    let requests_today: Int?
    let tokens_today: Int?
    let success_rate: Double?
    let avg_latency_ms: Double?
    let cost_usd: Double?
}

struct OpsUpstreamTierTotal: Decodable, Hashable {
    let requests: Int?
    let tokens: Int?
}
