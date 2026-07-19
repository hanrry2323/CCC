import Foundation

/// 定稿协议：```ccc-transfer ... ``` JSON，字段对齐 transfer-gate.md
struct TransferDraft: Equatable {
    var title: String = ""
    var goal: String = ""
    var acceptance: String = ""
    var pipeline: String = "dev"
    var feasibility: String = "ok"
    var feasibilityReason: String = ""
    var executorIntent: String = "opencode"
    var planMd: String = ""
    /// "ccc-transfer" | "heuristic"
    var source: String = "heuristic"

    var isGateReady: Bool {
        // 门禁：必填齐且 feasibility 必须为 ok（blocked 不可转任务）
        !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !goal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !pipeline.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !acceptanceLines.isEmpty
            && feasibility == "ok"
    }

    var acceptanceLines: [String] {
        acceptance
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
    }

    var previewLine: String {
        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let g = goal.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.isEmpty { return String(g.prefix(60)) }
        return t
    }
}

enum TransferDraftParser {
    /// 从助手正文解析 fenced `ccc-transfer` JSON
    static func parse(from content: String) -> TransferDraft? {
        guard let jsonText = extractFence(content, language: "ccc-transfer") else { return nil }
        guard let data = jsonText.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }

        var draft = TransferDraft(source: "ccc-transfer")
        draft.title = stringField(obj, "title")
        draft.goal = stringField(obj, "goal")
        draft.pipeline = stringField(obj, "pipeline", default: "dev")
        draft.feasibility = stringField(obj, "feasibility", default: "ok").lowercased()
        draft.feasibilityReason = stringField(obj, "feasibility_reason")
        draft.executorIntent = stringField(obj, "executor_intent", default: "opencode").lowercased()
        draft.planMd = stringField(obj, "plan_md")

        if let arr = obj["acceptance"] as? [Any] {
            draft.acceptance = arr.compactMap { $0 as? String }
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
                .joined(separator: "\n")
        } else {
            draft.acceptance = stringField(obj, "acceptance")
        }

        if draft.title.isEmpty && draft.goal.isEmpty { return nil }
        return draft
    }

    private static func stringField(_ obj: [String: Any], _ key: String, default def: String = "") -> String {
        if let s = obj[key] as? String {
            return s.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        if let n = obj[key] as? NSNumber {
            return n.stringValue
        }
        return def
    }

    private static func extractFence(_ text: String, language: String) -> String? {
        let pattern = "```\\s*\(language)\\s*\\n([\\s\\S]*?)\\n```"
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else {
            return nil
        }
        let ns = text as NSString
        let range = NSRange(location: 0, length: ns.length)
        guard let match = regex.firstMatch(in: text, options: [], range: range),
              match.numberOfRanges >= 2
        else { return nil }
        return ns.substring(with: match.range(at: 1)).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
