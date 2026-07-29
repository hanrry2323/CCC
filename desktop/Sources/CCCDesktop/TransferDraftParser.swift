import Foundation

/// 转任务表单（按 thread 隔离；对齐 OpenCode session 级表单态）
struct TransferFormState: Equatable {
    var title: String = ""
    var goal: String = ""
    var acceptance: String = ""
    var pipeline: String = "dev"
    var executor: String = "opencode"
    var feasibility: String = "ok"
    var feasibilityReason: String = ""
    var planMd: String = ""
    var complexity: String = "medium"
    var bumpVersion: Bool = false
    var humanNote: String = ""
    /// "ccc-transfer" | "heuristic" | ""
    var source: String = ""
    var error: String?
}

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
    var complexity: String = "medium"
    var bumpVersion: Bool = false
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
        parseAll(from: content).first
    }

    /// v0.65：解析全部 `ccc-transfer` 块（大方案多意图卡）；顺序保留
    static func parseAll(from content: String) -> [TransferDraft] {
        let fences = extractAllFences(content, language: "ccc-transfer")
        var out: [TransferDraft] = []
        for jsonText in fences {
            guard let data = jsonText.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { continue }
            // 单块内 cards: [...] 展开为多卡
            if let cards = obj["cards"] as? [[String: Any]], !cards.isEmpty {
                for c in cards {
                    if let d = draftFromObject(c) { out.append(d) }
                }
                continue
            }
            if let d = draftFromObject(obj) { out.append(d) }
        }
        return out
    }

    private static func draftFromObject(_ obj: [String: Any]) -> TransferDraft? {
        var draft = TransferDraft(source: "ccc-transfer")
        draft.title = stringField(obj, "title")
        draft.goal = stringField(obj, "goal")
        draft.pipeline = stringField(obj, "pipeline", default: "dev")
        draft.feasibility = stringField(obj, "feasibility", default: "ok").lowercased()
        draft.feasibilityReason = stringField(obj, "feasibility_reason")
        draft.executorIntent = stringField(obj, "executor_intent", default: "opencode").lowercased()
        draft.planMd = stringField(obj, "plan_md")
        draft.complexity = stringField(obj, "complexity", default: "medium").lowercased()
        if let b = obj["bump_version"] as? Bool {
            draft.bumpVersion = b
        } else if let s = obj["bump_version"] as? String {
            draft.bumpVersion = ["true", "1", "yes"].contains(s.lowercased())
        }

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

    /// 用户可见正文：去掉 `ccc-transfer` fence（契约折叠另显）
    static func humanVisibleMarkdown(from content: String) -> String {
        stripTransferFence(content).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// 原始 fence 内 JSON 文本（展开契约区用）；无则 nil
    static func transferFenceJSON(from content: String) -> String? {
        extractFence(content, language: "ccc-transfer")
    }

    /// 去掉所有 ```ccc-transfer ... ``` 块
    static func stripTransferFence(_ text: String) -> String {
        let pattern = "```\\s*ccc-transfer\\s*\\r?\\n[\\s\\S]*?\\r?\\n```"
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else {
            return text
        }
        let ns = text as NSString
        let range = NSRange(location: 0, length: ns.length)
        return regex.stringByReplacingMatches(in: text, options: [], range: range, withTemplate: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
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
        extractAllFences(text, language: language).first
    }

    private static func extractAllFences(_ text: String, language: String) -> [String] {
        let pattern = "```\\s*\(language)\\s*\\r?\\n([\\s\\S]*?)\\r?\\n```"
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else {
            return []
        }
        let ns = text as NSString
        let range = NSRange(location: 0, length: ns.length)
        var out: [String] = []
        regex.enumerateMatches(in: text, options: [], range: range) { match, _, _ in
            guard let match, match.numberOfRanges >= 2 else { return }
            let body = ns.substring(with: match.range(at: 1))
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !body.isEmpty { out.append(body) }
        }
        return out
    }
}
