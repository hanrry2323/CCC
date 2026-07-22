import SwiftUI

/// 原生运维：Apple 组件呈现（Gauge / Grid / Material / Section）
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
                    statusBarSection
                    logisticsSection
                    highAlertsSection
                    DisclosureGroup("舰队详情", isExpanded: $showFleet) {
                        VStack(alignment: .leading, spacing: 22) {
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
                    inboxProposalsSection
                    DisclosureGroup("例外动作", isExpanded: $showActions) {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("日审默认 dry-run all-apps；采纳须业务仓（禁 CCC）。")
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
            Label("运维", systemImage: "wrench.and.screwdriver.fill")
                .font(.system(size: 18, weight: .semibold))
            if let n = model.opsOverview?.alert_count, n > 0 {
                Text("\(n)")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(CCCTheme.nodeFail))
            }
            Spacer()
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

    // MARK: - Status bar

    private var statusBarSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionTitle("状态", systemImage: "heart.text.square")
            let risks = model.opsRisks
            let engineDown = risks.contains { $0.id == "engine-down" }
            let high = risks.filter { $0.severity.lowercased() == "high" }.count
            let plist = model.opsSummary?.logistics?.plist
            let loaded = plist?.any_loaded == true
            let applyAmmo = plist?.any_apply_ammo == true
            HStack(spacing: 8) {
                statusPill(ok: !engineDown, text: engineDown ? "Engine 停" : "Engine 在跑")
                statusPill(ok: loaded, text: loaded ? (applyAmmo ? "plist apply" : "plist dry") : "plist 未启用")
                statusPill(ok: high == 0, text: high > 0 ? "红灯 \(high)" : "无红灯")
            }
            if let headline = model.opsSummary?.logistics?.headline {
                Text(headline)
                    .font(.system(size: 13, weight: (model.opsSummary?.logistics?.needs_attention == true) ? .semibold : .regular))
                    .foregroundStyle(
                        (model.opsSummary?.logistics?.needs_attention == true)
                            ? Color.orange : CCCTheme.secondary
                    )
            }
            Text("定时：install-ops-plist.sh --enable --apply-ammo（界面不代启）")
                .font(CCCTheme.caption)
                .foregroundStyle(CCCTheme.faint)
        }
    }

    private func statusPill(ok: Bool, text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(ok ? CCCTheme.nodeDone : CCCTheme.nodeFail)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(
                Capsule().fill((ok ? CCCTheme.nodeDone : CCCTheme.nodeFail).opacity(0.12))
            )
    }

    // MARK: - High alerts only

    private var highAlertsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("需关注", systemImage: "exclamationmark.octagon.fill")
            let high = model.opsRisks.filter { $0.severity.lowercased() == "high" }
            let downs = model.opsOverview?.down_ports ?? []
            if high.isEmpty && downs.isEmpty {
                emptyHint("当前无红灯")
            } else {
                ForEach(high) { risk in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "exclamationmark.octagon.fill")
                            .foregroundStyle(CCCTheme.nodeFail)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(risk.title)
                                .font(.system(size: 14, weight: .semibold))
                            Text(risk.detail)
                                .font(CCCTheme.caption)
                                .foregroundStyle(CCCTheme.secondary)
                                .lineLimit(3)
                        }
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(CCCTheme.nodeFail.opacity(0.08))
                    )
                }
                ForEach(downs.prefix(6)) { p in
                    Label("\(p.host):\(p.port) · \(p.name)", systemImage: "network.slash")
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundStyle(CCCTheme.nodeFail)
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
