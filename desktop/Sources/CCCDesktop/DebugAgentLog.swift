import Foundation

/// Debug-mode NDJSON logger (session f3bb58). Do not log secrets.
enum DebugAgentLog {
    private static let sessionId = "f3bb58"
    private static let lock = NSLock()
    private static let workspacePath = "/Users/apple/program/CCC/.cursor/debug-f3bb58.log"

    private static var appSupportPath: String {
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Application Support")
        return root
            .appendingPathComponent("CCCDesktop")
            .appendingPathComponent("debug-f3bb58.log")
            .path
    }

    static func log(
        hypothesisId: String,
        location: String,
        message: String,
        data: [String: Any] = [:],
        runId: String = "pre"
    ) {
        // #region agent log
        let payload: [String: Any] = [
            "sessionId": sessionId,
            "hypothesisId": hypothesisId,
            "location": location,
            "message": message,
            "timestamp": Int(Date().timeIntervalSince1970 * 1000),
            "runId": runId,
            "data": data,
        ]
        guard JSONSerialization.isValidJSONObject(payload),
              let json = try? JSONSerialization.data(withJSONObject: payload),
              var line = String(data: json, encoding: .utf8)
        else { return }
        line.append("\n")
        let bytes = Data(line.utf8)
        lock.lock()
        defer { lock.unlock() }
        append(bytes, to: workspacePath)
        append(bytes, to: appSupportPath)
        // #endregion
    }

    private static func append(_ bytes: Data, to path: String) {
        let fm = FileManager.default
        let dir = URL(fileURLWithPath: path).deletingLastPathComponent().path
        if !fm.fileExists(atPath: dir) {
            try? fm.createDirectory(atPath: dir, withIntermediateDirectories: true)
        }
        if fm.fileExists(atPath: path), let handle = FileHandle(forWritingAtPath: path) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: bytes)
        } else {
            fm.createFile(atPath: path, contents: bytes)
        }
    }
}
