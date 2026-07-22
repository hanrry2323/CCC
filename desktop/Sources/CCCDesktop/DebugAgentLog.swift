import Foundation

/// Former mid-pane debug NDJSON probe (session f3bb58). Disabled — no disk I/O.
enum DebugAgentLog {
    static func log(
        hypothesisId: String,
        location: String,
        message: String,
        data: [String: Any] = [:],
        runId: String = "pre"
    ) {
        // no-op: investigation closed; do not recreate .cursor/debug-*.log
    }
}
