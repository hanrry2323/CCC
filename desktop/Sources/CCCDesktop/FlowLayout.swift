import CoreGraphics
import Foundation

enum FlowLayout {
    /// 适配右栏窄宽：节点略瘦、间距收紧、大卡居中
    static let nodeWidth: CGFloat = 156
    static let nodeHeight: CGFloat = 68
    static let epicHeight: CGFloat = 78
    static let hGap: CGFloat = 14
    static let vGap: CGFloat = 28
    static let pad: CGFloat = 14
    static let railContentWidth: CGFloat = 280

    /// 简单分层 DAG：epic 置顶居中；work 按依赖分层、层内居中
    static func layout(
        epic: FlowEpic?,
        epicId: String?,
        works: [FlowWork]
    ) -> (nodes: [FlowGraphNode], edges: [FlowGraphEdge], size: CGSize) {
        var nodes: [FlowGraphNode] = []
        var edges: [FlowGraphEdge] = []

        let eid = epic?.id ?? epicId ?? "epic"
        let contentW = max(railContentWidth, nodeWidth + pad * 2)

        let epicNode = FlowGraphNode(
            id: eid,
            kind: .epic,
            title: epic?.title ?? eid,
            subtitle: epic?.headline ?? epic?.user_stage.map { stageLabel($0) } ?? "待拆解",
            statusKey: epic?.user_stage ?? "pending",
            badge: "任务",
            detail: epic?.goal_summary
        )
        nodes.append(epicNode)

        let depth = workDepths(works)
        let maxDepth = depth.values.max() ?? 0
        var layers: [[FlowWork]] = Array(repeating: [], count: max(1, maxDepth + 1))
        let workIds = Set(works.map(\.id))
        if !works.isEmpty {
            layers = Array(repeating: [], count: maxDepth + 1)
            for w in works {
                let d = depth[w.id] ?? 0
                layers[d].append(w)
            }
        } else {
            layers = []
        }

        let epicX = (contentW - nodeWidth) / 2
        let epicY = pad
        if var n = nodes.first {
            n.x = epicX
            n.y = epicY
            nodes[0] = n
        }

        var maxX: CGFloat = epicX + nodeWidth
        var maxY: CGFloat = epicY + epicHeight

        for (layerIdx, layer) in layers.enumerated() {
            let y = pad + epicHeight + vGap + CGFloat(layerIdx) * (nodeHeight + vGap)
            let totalW = CGFloat(layer.count) * nodeWidth + CGFloat(max(0, layer.count - 1)) * hGap
            var x = pad + max(0, (contentW - totalW) / 2)
            for w in layer {
                let node = FlowGraphNode(
                    id: w.id,
                    kind: .work,
                    title: w.title,
                    subtitle: w.displayStatus,
                    statusKey: w.status,
                    badge: w.displayExecutor,
                    detail: w.failureNote ?? (w.dependsOnTitles?.isEmpty == false
                        ? "依赖 \(w.dependsOnTitles!.joined(separator: "、"))"
                        : nil),
                    x: x,
                    y: y
                )
                nodes.append(node)
                maxX = max(maxX, x + nodeWidth)
                maxY = max(maxY, y + nodeHeight)
                x += nodeWidth + hGap

                let deps = w.dependsOn.filter { workIds.contains($0) }
                if deps.isEmpty {
                    edges.append(FlowGraphEdge(from: eid, to: w.id, active: w.isActive || w.status == "planned"))
                } else {
                    for d in deps {
                        edges.append(FlowGraphEdge(from: d, to: w.id, active: w.isActive))
                    }
                }
            }
        }

        let size = CGSize(
            width: max(maxX + pad, contentW),
            height: max(maxY + pad, epicHeight + pad * 2)
        )
        return (nodes, edges, size)
    }

    static func stageLabel(_ stage: String) -> String {
        switch stage {
        case "pending": return "待拆解"
        case "planned": return "已拆解"
        case "running": return "执行中"
        case "testing": return "验收中"
        case "done": return "已完成"
        case "failed": return "异常"
        default: return stage
        }
    }

    static func statusColorKey(_ key: String) -> String {
        if ["in_progress", "running", "testing"].contains(key) { return "running" }
        if ["released", "verified", "done"].contains(key) { return "done" }
        if ["abnormal", "failed"].contains(key) { return "fail" }
        return "pending"
    }

    /// 按依赖分层（供拆分动画 stagger）
    static func layers(works: [FlowWork]) -> [[FlowWork]] {
        guard !works.isEmpty else { return [] }
        let depth = workDepths(works)
        let maxDepth = depth.values.max() ?? 0
        var layers: [[FlowWork]] = Array(repeating: [], count: maxDepth + 1)
        for w in works {
            layers[depth[w.id] ?? 0].append(w)
        }
        for i in layers.indices {
            layers[i].sort { a, b in
                let sa = stageRank(a.status)
                let sb = stageRank(b.status)
                if sa != sb { return sa < sb }
                return a.id < b.id
            }
        }
        return layers
    }

    /// 单列时间线排序：看板阶段 → 依赖深度 → id（阶段分组连续）
    static func orderedWorks(_ works: [FlowWork]) -> [FlowWork] {
        let depth = workDepths(works)
        return works.sorted { a, b in
            let sa = stageRank(a.status)
            let sb = stageRank(b.status)
            if sa != sb { return sa < sb }
            let da = depth[a.id] ?? 0
            let db = depth[b.id] ?? 0
            if da != db { return da < db }
            return a.id < b.id
        }
    }

    /// 阶段分组标题（纵向列表用）
    static func stageSectionTitle(_ status: String) -> String {
        switch status {
        case "planned": return "拆解 / 排队"
        case "in_progress": return "开发"
        case "testing": return "验收"
        case "verified", "released": return "完成"
        case "abnormal": return "异常"
        default: return "其它"
        }
    }

    static func stageRank(_ status: String) -> Int {
        switch status {
        case "planned": return 0
        case "in_progress": return 1
        case "testing": return 2
        case "verified": return 3
        case "released": return 4
        case "abnormal": return 5
        default: return 6
        }
    }

    static func graphNode(from work: FlowWork) -> FlowGraphNode {
        FlowGraphNode(
            id: work.id,
            kind: .work,
            title: work.title,
            subtitle: work.displayStatus,
            statusKey: work.status,
            badge: work.displayExecutor,
            detail: work.failureNote ?? (work.dependsOnTitles?.isEmpty == false
                ? "依赖 \(work.dependsOnTitles!.joined(separator: "、"))"
                : nil)
        )
    }

    static func epicGraphNode(epic: FlowEpic?, epicId: String?) -> FlowGraphNode {
        let eid = epic?.id ?? epicId ?? "epic"
        return FlowGraphNode(
            id: eid,
            kind: .epic,
            title: epic?.title ?? eid,
            subtitle: epic?.headline ?? epic?.user_stage.map { stageLabel($0) } ?? "待拆解",
            statusKey: epic?.user_stage ?? "pending",
            badge: "任务",
            detail: epic?.goal_summary
        )
    }

    /// 共享深度计算：环检测 + 深度硬上限 32
    private static func workDepths(_ works: [FlowWork]) -> [String: Int] {
        let byId = Dictionary(uniqueKeysWithValues: works.map { ($0.id, $0) })
        let workIds = Set(byId.keys)
        var depth: [String: Int] = [:]
        func computeDepth(_ id: String, stack: Set<String>) -> Int {
            if let d = depth[id] { return d }
            if stack.contains(id) { return 0 }
            if stack.count >= 32 { return 0 }
            guard let w = byId[id] else { return 0 }
            let deps = w.dependsOn.filter { workIds.contains($0) }
            if deps.isEmpty {
                depth[id] = 0
                return 0
            }
            var next = stack
            next.insert(id)
            let d = 1 + (deps.map { computeDepth($0, stack: next) }.max() ?? 0)
            depth[id] = d
            return d
        }
        for w in works { _ = computeDepth(w.id, stack: []) }
        return depth
    }
}
