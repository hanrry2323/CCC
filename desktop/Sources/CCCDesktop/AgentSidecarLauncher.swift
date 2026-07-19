import Foundation

/// Desktop 负责拉起本机 Agent Sidecar（不杀进程保暖）。
enum AgentSidecarLauncher {
    struct Result: Sendable {
        let launched: Bool
        let cccHome: String?
        let detail: String
    }

    /// 解析 CCC 仓根：CCC_HOME → 设置 → 常见本机路径
    static func resolveCCCHome(configured: String?) -> String? {
        if let env = ProcessInfo.processInfo.environment["CCC_HOME"]?
            .trimmingCharacters(in: .whitespacesAndNewlines),
           !env.isEmpty,
           FileManager.default.fileExists(atPath: (env as NSString).appendingPathComponent("scripts/ccc-agent-sidecar.sh")) {
            return env
        }
        if let configured, !configured.isEmpty {
            let root = (configured as NSString).standardizingPath
            let script = (root as NSString).appendingPathComponent("scripts/ccc-agent-sidecar.sh")
            if FileManager.default.fileExists(atPath: script) {
                return root
            }
        }
        let candidates = [
            NSHomeDirectory() + "/program/CCC",
            "/Users/apple/program/CCC",
            "/Users/fan/program/CCC",
        ]
        for root in candidates {
            let script = root + "/scripts/ccc-agent-sidecar.sh"
            if FileManager.default.fileExists(atPath: script) {
                return root
            }
        }
        return nil
    }

    /// 若未在跑则后台启动 sidecar；用 nohup 脱离，App 退出不杀。
    @discardableResult
    static func ensureRunning(cccHomeHint: String?) -> Result {
        guard let home = resolveCCCHome(configured: cccHomeHint) else {
            return Result(
                launched: false,
                cccHome: nil,
                detail: "找不到 CCC 仓（设 CCC_HOME 或设置里 CCC 仓根）"
            )
        }
        let script = (home as NSString).appendingPathComponent("scripts/ccc-agent-sidecar.sh")
        guard FileManager.default.fileExists(atPath: script) else {
            return Result(launched: false, cccHome: home, detail: "缺少 ccc-agent-sidecar.sh")
        }

        let logDir = (NSHomeDirectory() as NSString)
            .appendingPathComponent("Library/Logs/CCC")
        try? FileManager.default.createDirectory(
            atPath: logDir,
            withIntermediateDirectories: true
        )
        let logPath = (logDir as NSString).appendingPathComponent("agent-sidecar.log")

        // nohup + background：短命 shell 退出后 sidecar 仍活着
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        let cmd = """
        cd "$1" && nohup bash "$2" >>"$3" 2>&1 &
        """
        process.arguments = ["-c", cmd, "--", home, script, logPath]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
            let ok = process.terminationStatus == 0
            return Result(
                launched: ok,
                cccHome: home,
                detail: ok ? "nohup started" : "launch exit=\(process.terminationStatus)"
            )
        } catch {
            return Result(launched: false, cccHome: home, detail: error.localizedDescription)
        }
    }
}
