import Foundation

/// Debug-mode NDJSON logger (session f3bb58). Do not log secrets.
enum DebugAgentLog {
    private static let path = "/Users/apple/program/CCC/.cursor/debug-f3bb58.log"
    private static let sessionId = "f3bb58"
    private static let lock = NSLock()

    static func log(
        hypothesisId: String,
        location: String,
        message: String,
        data: [String: Any] = [:],
        runId: String = "pre"
    ) {
        // #region agent log
        var payload: [String: Any] = [
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
        if FileManager.default.fileExists(atPath: path),
           let handle = FileHandle(forWritingAtPath: path) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: bytes)
        } else {
            FileManager.default.createFile(atPath: path, contents: bytes)
        }
        // #endregion
    }
}
