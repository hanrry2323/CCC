import SwiftUI
import AppKit

/// 域 chip 四态：绿 / 橙(降级) / 红 / 灰(未知/未拉取)
enum DomainChipTone { case green, amber, red, gray }

/// 原生运维：一眼红绿灯
struct OpsView: View {
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var window: WindowChatState
    @State private var showAdoptSheet = false
    @State private var adoptTitle = ""
    @State private var adoptDesc = ""
    @State private var adoptWorkspace = ""
    @State private var showFleet = false
    @State private var showReports = false
    @State private var showActions = false
    @State private var showFailures = false
    @State private var showChannelDetail = false
    @State private var showUpstreamDaily = false
    @State private var showAgentMinds = false

    private var preferredAmmoWorkspace: String {
        if let p = model.selectedProject, p.isDispatchable {
            return p.workspace ?? p.id
        }
        if let p = model.projects.first(where: \.isDispatchable) {
            return p.workspace ?? p.id
        }
        return ""
    }

    private var canAdoptAmmo: Bool {
        let ws = adoptWorkspace.trimmingCharacters(in: .whitespacesAndNewlines)
        return !ws.isEmpty && ws.uppercased() != "CCC"
    }

    private let machineColumns = [
        GridItem(.adaptive(minimum: 220, maximum: 320), spacing: 12),
    ]

    var body: some View {
        VStack(spacing: 0) {
            header
            if let err = model.opsError {
                Label(err, systemImage: "exclamationmark.triangle.fill")
                    .font(CCCTheme.callout)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 8)
            }
            if let adoptErr = model.opsAdoptError {
                Text(adoptErr)
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 6)
            }
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 22) {
                    // P0 四域 above-the-fold：①总灯 ②集群 ③Agent/MCP/Relay ④仅红
                    healthLampSection
                    clusterSummarySection
                    agentMcpRelaySection
                    redAlertsSection

                    DisclosureGroup("失败与提案", isExpanded: $showFailures) {
                        VStack(alignment: .leading, spacing: 22) {
                            failuresSection
                            inboxProposalsSection
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))

                    DisclosureGroup("通道与长任务", isExpanded: $showChannelDetail) {
                        VStack(alignment: .leading, spacing: 16) {
                            relayDetailSection
                            bgSessionsDetailSection
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))

                    DisclosureGroup("后勤与舰队", isExpanded: $showFleet) {
                        VStack(alignment: .leading, spacing: 22) {
                            logisticsSection
                            overviewSection
                            resourcesSection
                            workspacesSection
                            downPortsSection
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))
                    DisclosureGroup("报告与债", isExpanded: $showReports) {
                        VStack(alignment: .leading, spacing: 22) {
                            dailyReviewSection
                            qualitySection
                            docsDebtSection
                            risksSection
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))
                    DisclosureGroup("模型通道", isExpanded: $showUpstreamDaily) {
                        upstreamDailySection
                    }
                    .font(.system(size: 15, weight: .semibold))
                    DisclosureGroup("项目心智", isExpanded: $showAgentMinds) {
                        agentMindsSection
                    }
                    .font(.system(size: 15, weight: .semibold))
                    DisclosureGroup("例外动作", isExpanded: $showActions) {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("日审默认 dry-run；采纳须业务仓（禁 CCC）。日常不必点。")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.faint)
                            Button {
                                Task { await model.runDailyReview(workspace: "") }
                            } label: {
                                Label("跑日审（dry-run）", systemImage: "play.fill")
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                            .disabled(model.opsAdoptBusy)
                        }
                        .padding(.top, 8)
                    }
                    .font(.system(size: 15, weight: .semibold))
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 28)
            }
        }
        .background(CCCTheme.chatBg)
        .task {
            if adoptWorkspace.isEmpty {
                adoptWorkspace = preferredAmmoWorkspace
            }
            await model.refreshOps()
        }
        .sheet(isPresented: $showAdoptSheet) {
            adoptSheet
                .onAppear {
                    if adoptWorkspace.isEmpty || adoptWorkspace.uppercased() == "CCC" {
                        adoptWorkspace = preferredAmmoWorkspace
                    }
                }
        }
    }

    private var header: some View {
        HStack {
            Label("运维", systemImage: "heart.text.square.fill")
                .font(.system(size: 18, weight: .semibold))
            let redN = displayAlerts.count
            if redN > 0 {
                Text("\(redN)")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(CCCTheme.nodeFail))
            }
            Spacer()
            if let hint = model.opsCopiedHint {
                Text(hint)
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.secondary)
            }
            if model.opsAdoptBusy || model.opsBusy {
                ProgressView().controlSize(.small)
            }
            Menu {
                Button("采纳建议…", systemImage: "plus.circle") {
                    adoptWorkspace = preferredAmmoWorkspace
                    showAdoptSheet = true
                }
                .disabled(preferredAmmoWorkspace.isEmpty)
                Button("刷新", systemImage: "arrow.clockwise") {
                    Task { await model.refreshOps() }
                }
            } label: {
                Image(systemName: "ellipsis.circle")
                    .font(.system(size: 16))
                    .foregroundStyle(CCCTheme.secondary)
            }
            .menuStyle(.borderlessButton)
            Button("回对话") {
                window.destination = .chat
                model.selectDestination(.chat, projectId: window.projectId)
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .padding(.bottom, 10)
    }

    // MARK: - Health lamp (homepage)

    /// Hub severity + 本机 Agent + MCP 合并后的总灯（与侧栏角标共用 OpsHealthDisplay）
    private var displaySeverity: String {
        OpsHealthDisplay.severity(
            summary: model.opsSummary,
            agentOk: model.opsAgentOk,
            localPatrol: model.localPatrolAlerts
        )
    }

    private var displayHumanLine: String {
        OpsHealthDisplay.humanLine(
            summary: model.opsSummary,
            agentOk: model.opsAgentOk,
            severity: displaySeverity
        )
    }

    private var displayAlerts: [OpsHealthAlert] {
        OpsHealthDisplay.alerts(summary: model.opsSummary, agentOk: model.opsAgentOk, localPatrol: model.localPatrolAlerts)
    }

    private var healthLampSection: some View {
        let sev = displaySeverity
        let color: Color = {
            switch sev {
            case "green": return CCCTheme.nodeDone
            case "red": return CCCTheme.nodeFail
            default: return Color.orange
            }
        }()
        let title: String = {
            switch sev {
            case "green": return "可以开发"
            case "red": return "请交给 Agent"
            default: return "可忽略"
            }
        }()
        let icon: String = {
            switch sev {
            case "green": return "checkmark.circle.fill"
            case "red": return "exclamationmark.octagon.fill"
            default: return "exclamationmark.circle.fill"
            }
        }()
        return VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .center, spacing: 16) {
                Image(systemName: icon)
                    .font(.system(size: 44))
                    .foregroundStyle(color)
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(color)
                    Text(displayHumanLine)
                        .font(.system(size: 15))
                        .foregroundStyle(CCCTheme.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            if sev == "amber", let notes = model.opsSummary?.amber_notes, !notes.isEmpty {
                Text(notes.prefix(3).joined(separator: " · "))
                    .font(CCCTheme.caption)
                    .foregroundStyle(Color.orange.opacity(0.9))
            }
            if sev == "green" {
                Text("看一眼绿灯就可以去定稿下任务。不必在这里修东西。")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(color.opacity(0.12))
        )
    }

    private var redAlertsSection: some View {
        let alerts = displayAlerts
        return Group {
            if !alerts.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    sectionTitle("红灯 · 交给对话 Agent", systemImage: "doc.on.clipboard")
                    Text("红灯是系统问题。点按钮打开当前项目对话处理。你不用当维修工。")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                    ForEach(alerts) { alert in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "light.beacon.max.fill")
                                .foregroundStyle(CCCTheme.nodeFail)
                                .padding(.top, 2)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(alert.title)
                                    .font(.system(size: 14, weight: .semibold))
                                if let d = alert.detail, !d.isEmpty {
                                    Text(d)
                                        .font(CCCTheme.caption)
                                        .foregroundStyle(CCCTheme.secondary)
                                        .lineLimit(3)
                                }
                            }
                            Spacer(minLength: 8)
                            HStack(spacing: 6) {
                                Button("仅复制") {
                                    _ = copyOpsAlertToPasteboard(alert)
                                    model.opsCopiedHint = "已复制"
                                    DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                        if model.opsCopiedHint == "已复制" {
                                            model.opsCopiedHint = nil
                                        }
                                    }
                                }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                                Button("交给 Agent") {
                                    Task { await handoffOpsAlert(alert) }
                                }
                                .buttonStyle(.borderedProminent)
                                .tint(CCCTheme.nodeFail)
                                .controlSize(.small)
                            }
                        }
                        .padding(12)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(CCCTheme.nodeFail.opacity(0.08))
                        )
                    }
                }
            }
        }
    }

    /// 组装告警文本并写入系统剪贴板，返回文本本身
    private func copyOpsAlertToPasteboard(_ alert: OpsHealthAlert) -> String {
        let text = (alert.copy_payload?.trimmingCharacters(in: .whitespacesAndNewlines)).flatMap { $0.isEmpty ? nil : $0 }
            ?? """
            【CCC 运维红灯】\(alert.title)
            \(alert.detail ?? "")
            来源：\(alert.source ?? "ops")
            """
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
        return text
    }

    private func handoffOpsAlert(_ alert: OpsHealthAlert) async {
        let text = copyOpsAlertToPasteboard(alert)
        await model.handoffToOpsAgent(
            payload: text,
            sourceProjectId: window.projectId ?? model.selectedProjectId
        )
        window.destination = .chat
        model.selectDestination(.chat, projectId: window.projectId ?? model.selectedProjectId ?? "ccc")
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            if model.opsCopiedHint == "已交对话 Agent" {
                model.opsCopiedHint = nil
            }
        }
    }

    private var clusterSummarySection: some View {
        let cluster = model.opsSummary?.domains?.cluster
        let downN = cluster?.down_ports_n ?? model.opsOverview?.down_ports?.count ?? 0
        let engOk = cluster?.engine_running == true
        let mode = cluster?.mode ?? "—"
        let hubOk = cluster?.hub_port_7777 != false
        let tunnelOk = model.serverURLString.contains(":17777")
        return VStack(alignment: .leading, spacing: 10) {
            sectionTitle("集群与服务", systemImage: "server.rack")
            HStack(spacing: 10) {
                domainChip(
                    title: "Engine",
                    tone: engOk ? (mode == "enabled" ? .green : .amber) : .red,
                    subtitle: engOk ? "运行 · \(mode)" : "停 · \(mode)"
                )
                domainChip(
                    title: "Hub",
                    ok: hubOk,
                    subtitle: hubOk ? "编排 :7777" : "7777 异常"
                )
                domainChip(
                    title: "宕口",
                    ok: downN == 0,
                    subtitle: downN == 0 ? "全部正常" : "\(downN) 个异常"
                )
            }
            // 隧道状态行 — 与 chip 同级
            HStack(spacing: 6) {
                Image(systemName: "point.topleft.down.curvedto.point.bottomright.up")
                    .foregroundStyle(tunnelOk ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                    .font(.system(size: 14))
                Text("com.ccc.hub-tunnel")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(CCCTheme.ink)
                Text(tunnelOk ? "127.0.0.1:17777" : "未连")
                    .font(CCCTheme.caption)
                    .foregroundStyle(tunnelOk ? CCCTheme.nodeDone : CCCTheme.secondary)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill((tunnelOk ? CCCTheme.nodeDone : CCCTheme.nodeFail).opacity(0.1))
            )
            if let ports = cluster?.ports, !ports.isEmpty {
                Text(
                    "端口 "
                        + ports.map { p in
                            let n = p.port.map(String.init) ?? "?"
                            let mark = p.ok == true ? "✓" : (p.ok == false ? "✗" : "?")
                            return ":\(n)\(mark)"
                        }.joined(separator: "  ")
                )
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
            }
        }
    }

    private var agentMcpRelaySection: some View {
        let mcp = model.opsSummary?.domains?.agent_mcp
        let relay = model.opsSummary?.domains?.relay
        let agentOk = model.opsAgentOk
        let cap = model.opsSummary?.domains?.capacity
        return VStack(alignment: .leading, spacing: 10) {
            sectionTitle("Agent · MCP · Relay", systemImage: "cpu")
            HStack(spacing: 10) {
                domainChip(
                    title: "Agent",
                    tone: agentOk == true ? .green : (agentOk == false ? .red : .gray),
                    subtitle: {
                        if agentOk == true {
                            let rt = model.opsAgentRuntime ?? "sidecar"
                            let m = model.opsAgentModel ?? ""
                            return m.isEmpty ? rt : "\(rt) · \(m)"
                        }
                        if agentOk == false { return "本机未就绪" }
                        return "探测中"
                    }()
                )
                domainChip(
                    title: "MCP",
                    tone: mcpChipTone(mcp),
                    subtitle: mcpSubtitle(mcp)
                )
                domainChip(
                    title: "Relay",
                    tone: relay?.ok == true ? .green : (relay?.ok == false ? .amber : .gray),
                    subtitle: relaySubtitle(relay)
                )
                domainChip(
                    title: "容量",
                    tone: {
                        let v = cap?.verdict ?? ""
                        if v == "saturated" { return .red }
                        if v.isEmpty || v == "headroom" { return .green }
                        return .gray
                    }(),
                    subtitle: cap?.verdict ?? "—"
                )
            }
            if let mcp, mcp.isRedFailure, let note = mcp.note, !note.isEmpty {
                Text(note)
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
            } else if let mcp, mcp.isUnconfigured {
                Text(mcp.note ?? "MCP 未配置（灰/橙，不挡开发）")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            } else if let servers = mcp?.servers, !servers.isEmpty {
                Text(
                    "MCP "
                        + servers.prefix(6).map { s in
                            let n = s.name ?? "?"
                            let mark = s.ok == true ? "✓" : (s.ok == false ? "✗" : "?")
                            return "\(n)\(mark)"
                        }.joined(separator: "  ")
                )
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
            }
            if let relay = relay, relay.ok == false {
                Text("Relay fail-open 直连（\(relay.source ?? "relay_down")）· 不挡开发")
                    .font(CCCTheme.caption)
                    .foregroundStyle(.orange)
            }
        }
    }

    private func mcpChipTone(_ mcp: OpsDomainAgentMcp?) -> DomainChipTone {
        guard let mcp else { return .gray }  // 未返回 → 灰
        if mcp.isRedFailure { return .red }
        if mcp.isUnconfigured { return .gray } // 未配置 → 灰（非红）
        if mcp.ok != false { return .green }
        return .gray
    }

    private func mcpSubtitle(_ mcp: OpsDomainAgentMcp?) -> String {
        guard let mcp else { return "待 Hub 探针" }
        if mcp.isRedFailure {
            let n = mcp.failedCount
            return n > 0 ? "失败 \(n)" : "探测失败"
        }
        if mcp.isUnconfigured {
            return mcp.mcp_probed == true ? "未配置" : "未探针"
        }
        if mcp.ok == true {
            let n = mcp.configuredCount
            return n > 0 ? "正常 · \(n)" : "正常"
        }
        return mcp.note ?? "—"
    }

    private var relayDetailSection: some View {
        let relay = model.opsSummary?.domains?.relay
        return Group {
            if let relay = relay, relay.ok == true, let tiers = relay.tiers, !tiers.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Relay 三档").font(.system(size: 12, weight: .semibold))
                    let order = ["flash", "Pro", "code"]
                    ForEach(order, id: \.self) { k in
                        if let d = tiers[k] {
                            HStack(spacing: 6) {
                                Text(k).font(CCCTheme.caption.monospaced())
                                Spacer()
                                let up = d.upstreams ?? 0
                                let h = d.healthy ?? 0
                                let ok = up > 0 ? "\(h)/\(up)" : "—"
                                Text("上游 \(ok)")
                                    .font(CCCTheme.caption.monospaced())
                                    .foregroundStyle(h < up ? CCCTheme.nodeFail : CCCTheme.faint)
                                let reqs = d.requests_today ?? 0
                                Text("今日 \(reqs)")
                                    .font(CCCTheme.caption.monospaced())
                                    .foregroundStyle(CCCTheme.faint)
                            }
                        }
                    }
                }
            } else if let relay = relay, relay.ok == false {
                Text("⚠️ relay 不可达 — 客户端已切 fail-open 直连(\(relay.source ?? "relay_down"))")
                    .font(CCCTheme.caption)
                    .foregroundStyle(.orange)
            } else {
                emptyHint("暂无 Relay 分档明细")
            }
        }
    }

    private var bgSessionsDetailSection: some View {
        Group {
            if let bg = model.opsSummary?.domains?.bg_sessions,
               let sList = bg.sessions, !sList.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("长 session (claude --bg)").font(.system(size: 12, weight: .semibold))
                        Spacer()
                        let c = bg.count ?? 0
                        let a = bg.alive_count ?? 0
                        Text("\(a)/\(c) alive")
                            .font(CCCTheme.caption.monospaced())
                            .foregroundStyle(a == c ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                    }
                    ForEach(sList, id: \.session_id) { s in
                        let sid = (s.session_id ?? "?").prefix(8)
                        let role = s.role ?? "?"
                        let task = s.task_id ?? "?"
                        let aliveMark = s.alive == true ? "●" : "○"
                        let idle = s.idle_timeout == true ? "(idle)" : ""
                        HStack(spacing: 6) {
                            Text(aliveMark)
                                .foregroundStyle(s.alive == true ? CCCTheme.nodeDone : CCCTheme.faint)
                            Text(role).font(CCCTheme.caption.monospaced())
                            Text("\(task) · \(sid) \(idle)")
                                .font(CCCTheme.caption.monospaced())
                                .foregroundStyle(CCCTheme.faint)
                            Spacer()
                            let age = s.age_min ?? 0
                            Text("\(age)m")
                                .font(CCCTheme.caption.monospaced())
                                .foregroundStyle(CCCTheme.faint)
                        }
                    }
                }
            } else if let bg = model.opsSummary?.domains?.bg_sessions, bg.count == 0 {
                Text("长 session 0 个 — Engine 无 background 任务")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.faint)
            } else {
                emptyHint("暂无长 session 数据")
            }
        }
    }

    private var upstreamDailySection: some View {
        let rows = model.opsUpstreamDaily
        return Group {
            if rows.isEmpty {
                emptyHint("暂无用量数据")
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(rows) { row in
                        HStack(spacing: 8) {
                            Text(row.name)
                                .font(.system(size: 13, design: .monospaced))
                                .foregroundStyle(CCCTheme.ink)
                            Spacer(minLength: 4)
                            if let r = row.requests_today {
                                Text("\(r) 次")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.secondary)
                            }
                            if let rate = row.success_rate {
                                Text(String(format: "%.0f%%", rate * 100))
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(rate >= 0.95 ? CCCTheme.nodeDone : CCCTheme.nodeWarn)
                            } else if row.requests_today != nil {
                                Text("—")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.faint)
                            }
                            if let cost = row.cost_usd, cost > 0 {
                                Text(String(format: "$%.4f", cost))
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.faint)
                            }
                        }
                        Divider()
                    }
                }
            }
        }
    }

    private var agentMindsSection: some View {
        let resp = model.opsSummary?.agent_minds
        let items = resp?.items ?? []
        return Group {
            if let err = resp?.error, !err.isEmpty {
                Text("心智读取失败：\(err)")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
            } else if items.isEmpty {
                emptyHint("暂无心智摘要")
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(items) { item in
                        if let err = item.error, !err.isEmpty {
                            Text("\(item.project_id)：\(err)")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.nodeFail)
                        } else {
                            VStack(alignment: .leading, spacing: 3) {
                                HStack(spacing: 6) {
                                    Text(item.project_id)
                                        .font(.system(size: 13, weight: .medium, design: .monospaced))
                                        .foregroundStyle(CCCTheme.ink)
                                    if let n = item.constraints_n, n > 0 {
                                        Text("\(n) 约束")
                                            .font(.system(size: 10, weight: .semibold))
                                            .foregroundStyle(CCCTheme.faint)
                                            .padding(.horizontal, 5)
                                            .padding(.vertical, 1)
                                            .background(Capsule().fill(CCCTheme.faint.opacity(0.15)))
                                    }
                                }
                                if let s = item.board_summary ?? item.daily ?? item.weekly, !s.isEmpty {
                                    Text(s)
                                        .font(CCCTheme.caption)
                                        .foregroundStyle(CCCTheme.secondary)
                                        .lineLimit(3)
                                }
                                if let asOf = item.as_of, !asOf.isEmpty {
                                    Text(asOf)
                                        .font(.system(size: 10))
                                        .foregroundStyle(CCCTheme.faint)
                                }
                            }
                        }
                        Divider()
                    }
                }
            }
        }
    }

    // CCC Relay 2026-07-25:relay chip 副标题
    private func relaySubtitle(_ relay: OpsDomainRelay?) -> String {
        guard let relay = relay else { return "未拉取" }
        if relay.ok == true {
            let host = relay.host ?? "127.0.0.1"
            let port = relay.port ?? 4000
            return "\(host):\(port) · 三档"
        }
        if relay.ok == false { return "fail-open 直连" }
        return "探测中"
    }

    private func domainChip(title: String, tone: DomainChipTone, subtitle: String) -> some View {
        let color: Color = {
            switch tone {
            case .green: return CCCTheme.nodeDone
            case .amber: return CCCTheme.nodeWarn
            case .red:   return CCCTheme.nodeFail
            case .gray:  return CCCTheme.faint
            }
        }()
        return VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(CCCTheme.faint)
            Text(subtitle)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(color)
                .lineLimit(2)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(color.opacity(0.1))
        )
    }

    /// 保留二进制 ok 包装（green / red），方便不用 amber/gray 的调用处
    private func domainChip(title: String, ok: Bool, subtitle: String) -> some View {
        domainChip(title: title, tone: ok ? .green : .red, subtitle: subtitle)
    }

    // MARK: - Failures / abnormal (reopen)

    private var failuresSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("失败与异常", systemImage: "arrow.uturn.backward.circle")
            Text("归档仍须人确认；此处仅 reopen → planned。")
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
            let cards = model.opsSummary?.abnormal_cards ?? []
            if cards.isEmpty {
                emptyHint("无 abnormal 卡")
            } else {
                ForEach(cards.prefix(12)) { card in
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(card.title ?? card.task_id ?? "—")
                                .font(.system(size: 13, weight: .semibold))
                            Text("\(card.workspace) · \((card.note?.isEmpty == false) ? (card.note ?? "") : "abnormal")")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(2)
                        }
                        Spacer(minLength: 8)
                        Button("重开") {
                            Task {
                                await model.reopenOpsTask(
                                    taskId: card.task_id ?? card.id,
                                    workspace: card.workspace
                                )
                            }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.mini)
                        .disabled(model.opsBusy || model.opsAdoptBusy)
                        Button("看板") {
                            model.openBoardFromOps(workspace: card.workspace)
                            window.destination = .board
                        }
                        .buttonStyle(.borderless)
                        .controlSize(.mini)
                    }
                    .padding(10)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.nodeFail.opacity(0.06))
                    )
                }
            }
            let fails = model.opsSummary?.recent_failures ?? []
            if !fails.isEmpty {
                Text("最近失败账本")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(CCCTheme.secondary)
                    .padding(.top, 4)
                ForEach(fails.prefix(8)) { fr in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(fr.workspace ?? "?") · \(fr.task_id ?? "?") · \(fr.role ?? "")")
                            .font(.system(size: 11, design: .monospaced))
                        Text(fr.reason ?? "—")
                            .font(CCCTheme.caption)
                            .foregroundStyle(CCCTheme.secondary)
                            .lineLimit(2)
                    }
                    .padding(.vertical, 2)
                }
            }
        }
    }

    // MARK: - Logistics heartbeat (read-only)

    private var logisticsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("后勤供弹", systemImage: "shippingbox.fill")
            if let log = model.opsSummary?.logistics {
                VStack(alignment: .leading, spacing: 8) {
                    if let headline = log.headline {
                        Text(headline)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(log.needs_attention == true ? Color.orange : CCCTheme.ink)
                    }
                    HStack {
                        Label("\(log.ammo_workspaces?.count ?? 0) 弹药仓", systemImage: "tray.full")
                        Spacer()
                        if let n = log.ops_auto_backlog {
                            Text("ops-auto \(n)")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                    if let ammo = log.ammo_workspaces, !ammo.isEmpty {
                        Text(ammo.compactMap(\.workspace).joined(separator: " · "))
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(CCCTheme.faint)
                            .lineLimit(2)
                    }
                    Text("CCC orch 不在供弹名单")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                    if let agents = log.plist?.agents, !agents.isEmpty {
                        ForEach(agents) { a in
                            HStack {
                                Image(systemName: (a.loaded == true) ? "checkmark.circle.fill" : "circle")
                                    .foregroundStyle((a.loaded == true) ? CCCTheme.nodeDone : CCCTheme.faint)
                                Text(a.label)
                                    .font(.system(size: 12, design: .monospaced))
                                Spacer()
                                Text(a.apply_ammo == true ? "apply" : "dry")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.secondary)
                            }
                        }
                    }
                    if let daily = log.daily_today, !daily.isEmpty {
                        ForEach(daily) { d in
                            Text("\(d.workspace) · \(d.decision ?? "—")")
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    } else {
                        emptyHint("今日尚无日审报告")
                    }
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(CCCTheme.surface)
                )
            } else {
                emptyHint("后勤心跳未返回（刷新或升级 Hub）")
            }
        }
    }

    // MARK: - Inbox proposals (Hub-Shell P2)

    private var inboxProposalsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("待采纳提案", systemImage: "tray.and.arrow.down")
            if model.inboxProposals.isEmpty {
                emptyHint("inbox/ 无 pending 提案")
            } else {
                ForEach(model.inboxProposals) { p in
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.title ?? p.id)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(CCCTheme.ink)
                            Text("\(p.project_id ?? "—") · \(p.complexity ?? "small")")
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                        }
                        Spacer()
                        Button("采纳") {
                            Task { await model.adoptInboxProposal(p.id) }
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                        .disabled(model.inboxAdoptBusy)
                    }
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 8).fill(CCCTheme.surface.opacity(0.9)))
                }
            }
        }
    }

    // MARK: - Overview machines

    private var overviewSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("集群", systemImage: "desktopcomputer")
            if let machines = model.opsOverview?.machines, !machines.isEmpty {
                LazyVGrid(columns: machineColumns, spacing: 12) {
                    ForEach(machines) { m in
                        machineCard(m)
                    }
                }
            } else {
                emptyHint("暂无机器数据")
            }
        }
    }

    private func machineCard(_ m: OpsMachine) -> some View {
        let up = m.reachable ?? false
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: up ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .font(.system(size: 18))
                    .foregroundStyle(up ? CCCTheme.nodeDone : CCCTheme.nodeFail)
                VStack(alignment: .leading, spacing: 2) {
                    Text(m.name)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(CCCTheme.ink)
                    Text(m.role ?? "—")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
                Spacer(minLength: 0)
            }
            Divider()
            LabeledContent("地址") {
                Text(m.ip)
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundStyle(CCCTheme.secondary)
            }
            .font(CCCTheme.callout)
            if let alive = m.alive_ports, let total = m.port_count {
                LabeledContent("端口") {
                    Text("\(alive)/\(total)")
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundStyle(alive == total ? CCCTheme.nodeDone : CCCTheme.accent)
                }
                .font(CCCTheme.callout)
                ProgressView(value: total > 0 ? Double(alive) / Double(total) : 0)
                    .tint(alive == total ? CCCTheme.nodeDone : CCCTheme.accent)
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(.regularMaterial)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(CCCTheme.border, lineWidth: 1)
        )
    }

    // MARK: - Resources gauges

    private var resourcesSection: some View {
        Group {
            if let res = model.opsSummary?.resources {
                VStack(alignment: .leading, spacing: 12) {
                    sectionTitle("资源", systemImage: "chart.bar.fill")
                    if let hist = model.opsSummary?.resources_history?.summary {
                        let verdict = hist.verdict ?? "—"
                        HStack {
                            Text("并行容量：\(verdict)")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(verdict == "saturated" ? CCCTheme.nodeFail : CCCTheme.nodeDone)
                            if let spark = model.opsSummary?.resources_history?.sparklines?.load_ratio {
                                Text(spark)
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundStyle(CCCTheme.faint)
                            }
                        }
                        if let note = hist.note ?? hist.reason, !note.isEmpty {
                            Text(note)
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                        }
                    }
                    HStack(spacing: 16) {
                        if let cpu = res.cpu {
                            resourceGauge(
                                title: "CPU",
                                value: cpu,
                                symbol: "cpu",
                                unit: String(format: "%.0f%%", cpu * 100)
                            )
                        }
                        if let mem = res.mem_pct {
                            resourceGauge(
                                title: "内存",
                                value: mem / 100.0,
                                symbol: "memorychip",
                                unit: String(format: "%.0f%%", mem)
                            )
                        }
                        if let disk = res.disk_pct {
                            resourceGauge(
                                title: "磁盘",
                                value: disk / 100.0,
                                symbol: "externaldrive.fill",
                                unit: String(format: "%.0f%%", disk)
                            )
                        }
                    }
                }
            }
        }
    }

    private func resourceGauge(title: String, value: Double, symbol: String, unit: String) -> some View {
        let clamped = min(max(value, 0), 1)
        return VStack(spacing: 8) {
            Gauge(value: clamped) {
                Image(systemName: symbol)
            } currentValueLabel: {
                Text(unit)
                    .font(.system(size: 13, weight: .semibold, design: .rounded))
            }
            .gaugeStyle(.accessoryCircularCapacity)
            .tint(clamped > 0.85 ? CCCTheme.nodeFail : (clamped > 0.65 ? CCCTheme.accent : CCCTheme.nodeDone))
            Text(title)
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(.regularMaterial)
        )
    }

    // MARK: - Risks

    private var risksSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionTitle("风险", systemImage: "exclamationmark.shield.fill")
                if let high = model.opsRisksHigh, high > 0 {
                    Text("高 \(high)")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(Capsule().fill(CCCTheme.nodeFail))
                }
                Spacer()
                if let c = model.opsRisksCount {
                    Text("共 \(c)")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if model.opsRisks.isEmpty {
                emptyHint("暂无风险")
            } else {
                ForEach(model.opsRisks) { risk in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: severityIcon(risk.severity))
                            .font(.system(size: 16))
                            .foregroundStyle(severityColor(risk.severity))
                            .frame(width: 22)
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(risk.title)
                                    .font(.system(size: 14, weight: .semibold))
                                Spacer()
                                Text(risk.severity.uppercased())
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundStyle(severityColor(risk.severity))
                                    .padding(.horizontal, 7)
                                    .padding(.vertical, 2)
                                    .background(
                                        Capsule().fill(severityColor(risk.severity).opacity(0.14))
                                    )
                            }
                            if !risk.detail.isEmpty {
                                Text(risk.detail)
                                    .font(CCCTheme.callout)
                                    .foregroundStyle(CCCTheme.secondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(12)
                    .background(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .stroke(severityColor(risk.severity).opacity(0.25), lineWidth: 1)
                    )
                }
            }
        }
    }

    // MARK: - Workspaces

    private var workspacesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("工作区", systemImage: "folder.fill")
            if let wss = model.opsSummary?.workspaces?.workspaces, !wss.isEmpty {
                ForEach(wss) { ws in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Label(ws.workspace, systemImage: "shippingbox.fill")
                                .font(.system(size: 14, weight: .semibold))
                            Spacer()
                            if let abnormal = ws.abnormal, abnormal > 0 {
                                Label("异常 \(abnormal)", systemImage: "flame.fill")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(CCCTheme.nodeFail)
                            }
                        }
                        HStack(spacing: 8) {
                            boardChip("待办", ws.backlog)
                            boardChip("规划", ws.planned)
                            boardChip("进行", ws.in_progress)
                            boardChip("验收", ws.testing)
                            boardChip("异常", ws.abnormal)
                            boardChip("已验", ws.verified)
                            boardChip("发布", ws.released)
                        }
                        if let ev = ws.last_event, !ev.isEmpty {
                            Text(ev)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(1)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(.regularMaterial)
                    )
                }
            } else {
                emptyHint("暂无工作区数据")
            }
        }
    }

    private func boardChip(_ label: String, _ n: Int?) -> some View {
        Group {
            if let n {
                VStack(spacing: 2) {
                    Text("\(n)")
                        .font(.system(size: 14, weight: .semibold, design: .rounded))
                        .foregroundStyle(CCCTheme.ink)
                    Text(label)
                        .font(.system(size: 10))
                        .foregroundStyle(CCCTheme.faint)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(CCCTheme.chatBg)
                )
            }
        }
    }

    // MARK: - Daily / quality / docs / ports

    private var dailyReviewSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("日审", systemImage: "calendar")
            if let daily = model.opsSummary?.daily {
                if let latest = daily.latest {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("\(latest.workspace) · \(latest.name)", systemImage: "doc.text")
                            .font(.system(size: 14, weight: .medium))
                        if let mt = latest.mtime {
                            Text(mt)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                        }
                        if let body = daily.latest_body, !body.isEmpty {
                            Text(body)
                                .font(.system(size: 12, design: .monospaced))
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(16)
                                .textSelection(.enabled)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                } else {
                    emptyHint("暂无日审报告")
                }
            }
        }
    }

    private var qualitySection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("质量", systemImage: "checkmark.seal.fill")
            if let digests = model.opsSummary?.quality?.workspaces, !digests.isEmpty {
                ForEach(digests) { d in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(d.workspace)
                                .font(.system(size: 14, weight: .semibold))
                            Spacer()
                            if let c = d.commits_24h {
                                Label("\(c)", systemImage: "arrow.triangle.branch")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.secondary)
                            }
                            if let r = d.released_total {
                                Label("\(r)", systemImage: "flag.checkered")
                                    .font(CCCTheme.caption)
                                    .foregroundStyle(CCCTheme.nodeDone)
                            }
                        }
                        if let sample = d.commit_sample, !sample.isEmpty {
                            Text(sample.prefix(4).joined(separator: "\n"))
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(4)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(.regularMaterial)
                    )
                }
            } else {
                emptyHint("暂无质量摘要")
            }
        }
    }

    private var docsDebtSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionTitle("文档债", systemImage: "books.vertical.fill")
                Spacer()
                if let c = model.opsSummary?.docs?.count {
                    Text("共 \(c)")
                        .font(CCCTheme.caption)
                        .foregroundStyle(CCCTheme.faint)
                }
            }
            if let items = model.opsSummary?.docs?.items, !items.isEmpty {
                ForEach(items.prefix(10)) { item in
                    VStack(alignment: .leading, spacing: 4) {
                        if let f = item.file {
                            Label("\(item.workspace ?? "?") · \(f)", systemImage: "doc")
                                .font(.system(size: 13, design: .monospaced))
                                .lineLimit(1)
                        }
                        if let issue = item.issue, !issue.isEmpty {
                            Text(issue)
                                .font(CCCTheme.callout)
                                .foregroundStyle(CCCTheme.faint)
                                .lineLimit(2)
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                            .fill(CCCTheme.surface)
                    )
                }
            } else {
                emptyHint("暂无文档债")
            }
        }
    }

    private var downPortsSection: some View {
        Group {
            if let ports = model.opsOverview?.down_ports, !ports.isEmpty {
                VStack(alignment: .leading, spacing: 10) {
                    sectionTitle("宕口", systemImage: "network.slash")
                    ForEach(ports) { p in
                        Label("\(p.host):\(p.port) · \(p.name)", systemImage: "antenna.radiowaves.left.and.right.slash")
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundStyle(CCCTheme.nodeFail)
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(
                                RoundedRectangle(cornerRadius: 8, style: .continuous)
                                    .fill(CCCTheme.nodeFail.opacity(0.08))
                            )
                    }
                }
            }
        }
    }

    private var adoptSheet: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("采纳建议 → 业务仓 backlog")
                .font(.system(size: 16, weight: .semibold))
            LabeledContent("工作区") {
                TextField("ccc-demo（禁 CCC）", text: $adoptWorkspace)
                    .textFieldStyle(.roundedBorder)
            }
            if preferredAmmoWorkspace.isEmpty {
                Text("无 engine-eligible 业务仓，无法采纳")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
            } else if adoptWorkspace.uppercased() == "CCC" {
                Text("禁止对 CCC orch 供弹")
                    .font(CCCTheme.caption)
                    .foregroundStyle(CCCTheme.nodeFail)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("标题").font(CCCTheme.callout).foregroundStyle(CCCTheme.faint)
                TextField("一句话建议", text: $adoptTitle)
                    .textFieldStyle(.roundedBorder)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("描述").font(CCCTheme.callout).foregroundStyle(CCCTheme.faint)
                TextEditor(text: $adoptDesc)
                    .font(CCCTheme.callout)
                    .frame(height: 80)
                    .border(CCCTheme.border)
            }
            HStack {
                Spacer()
                Button("取消") { showAdoptSheet = false }
                    .buttonStyle(.bordered)
                Button("采纳") {
                    Task {
                        guard canAdoptAmmo else {
                            model.opsAdoptError = "须指定业务仓（禁 CCC orch）"
                            return
                        }
                        await model.adoptSuggestion(
                            workspace: adoptWorkspace.trimmingCharacters(in: .whitespacesAndNewlines),
                            title: adoptTitle,
                            description: adoptDesc
                        )
                        if model.opsAdoptError == nil {
                            showAdoptSheet = false
                            adoptTitle = ""
                            adoptDesc = ""
                        }
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(CCCTheme.accent)
                .disabled(adoptTitle.isEmpty || model.opsAdoptBusy || !canAdoptAmmo)
            }
        }
        .padding(20)
        .frame(width: 440, height: 340, alignment: .topLeading)
        .background(CCCTheme.chatBg)
    }

    private func sectionTitle(_ title: String, systemImage: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(.system(size: 15, weight: .semibold))
            .foregroundStyle(CCCTheme.ink)
    }

    private func emptyHint(_ text: String) -> some View {
        Text(text)
            .font(CCCTheme.caption)
            .foregroundStyle(CCCTheme.faint)
            .padding(.vertical, 4)
    }

    private func severityColor(_ s: String) -> Color {
        switch s.lowercased() {
        case "high", "critical": return CCCTheme.nodeFail
        case "medium", "warn", "warning": return Color.orange
        default: return CCCTheme.faint
        }
    }

    private func severityIcon(_ s: String) -> String {
        switch s.lowercased() {
        case "high", "critical": return "exclamationmark.octagon.fill"
        case "medium", "warn", "warning": return "exclamationmark.triangle.fill"
        default: return "info.circle.fill"
        }
    }
}
