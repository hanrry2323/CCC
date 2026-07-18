import CoreGraphics
import Foundation

enum FlowLayout {
    static let nodeWidth: CGFloat = 168
    static let nodeHeight: CGFloat = 72
    static let epicHeight: CGFloat = 86
    static let hGap: CGFloat = 20
    static let vGap: CGFloat = 36
    static let pad: CGFloat = 16

    /// 简单分层 DAG：无依赖并排，有依赖落在下层
    static func layout(
        epic: FlowEpic?,
        epicId: String?,
        works: [FlowWork]
    ) -> (nodes: [FlowGraphNode], edges: [FlowGraphEdge], size: CGSize) {
        var nodes: [FlowGraphNode] = []
        var edges: [FlowGraphEdge] = []

        let eid = epic?.id ?? epicId ?? "epic"
        let epicNode = FlowGraphNode(
            id: eid,
            kind: .epic,
            title: epic?.title ?? eid,
            subtitle: epic?.headline ?? epic?.user_stage.map { stageLabel($0) } ?? "待拆解",
            statusKey: epic?.user_stage ?? "pending",
            badge: "意图",
            detail: epic?.goal_summary
        )
        nodes.append(epicNode)

        let workIds = Set(works.map(\.id))
        var depth: [String: Int] = [:]
        func computeDepth(_ id: String, stack: Set<String> = []) -> Int {
            if let d = depth[id] { return d }
            if stack.contains(id) { return 0 }
            guard let w = works.first(where: { $0.id == id }) else { return 0 }
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
        for w in works { _ = computeDepth(w.id) }

        let maxDepth = depth.values.max() ?? 0
        var layers: [[FlowWork]] = Array(repeating: [], count: maxDepth + 1)
        for w in works {
            let d = depth[w.id] ?? 0
            layers[d].append(w)
        }

        var placed: [String: CGPoint] = [:]
        let epicX = pad
        let epicY = pad
        placed[eid] = CGPoint(x: epicX, y: epicY)
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
            var x = pad
            if layer.count == 1 {
                x = pad + (nodeWidth) * 0.15
            }
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
                placed[w.id] = CGPoint(x: x, y: y)
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
            _ = totalW
        }

        // epic → 所有 depth0
        if layers.first == nil || (layers.first?.isEmpty ?? true), works.isEmpty {
            // only epic
        }

        let size = CGSize(width: max(maxX + pad, 280), height: max(maxY + pad, 200))
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
}
