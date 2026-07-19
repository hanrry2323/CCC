import Foundation

/// Desktop 拉起本机 Agent Sidecar：优先 launchd KeepAlive，失败再 nohup。
enum AgentSidecarLauncher {
    static let launchdLabel = "com.ccc.agent-sidecar"

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

    /// 确保 sidecar 在跑：launchd kickstart → install plist → nohup 兜底
    @discardableResult
    static func ensureRunning(cccHomeHint: String?) -> Result {
        guard let home = resolveCCCHome(configured: cccHomeHint) else {
            return Result(
                launched: false,
                cccHome: nil,
                detail: "找不到 CCC 仓（设 CCC_HOME 或设置里 CCC 仓根）"
            )
        }

        // 1) 已有 launchd job：kickstart（KeepAlive 会自愈，这里催一下）
        if launchdJobLoaded() {
            _ = runShell("launchctl kickstart -k \"gui/$(id -u)/\(launchdLabel)\" 2>/dev/null || true")
            return Result(launched: true, cccHome: home, detail: "launchd kickstart")
        }

        // 2) 安装并 load plist（常驻）
        let install = (home as NSString)
            .appendingPathComponent("scripts/install-agent-sidecar-plist.sh")
        if FileManager.default.fileExists(atPath: install) {
            let r = runShell("bash \"\(install)\" --start")
            if r.ok {
                return Result(launched: true, cccHome: home, detail: "launchd installed")
            }
            // 继续兜底
        }

        // 3) nohup 兜底（无 launchd / 权限失败）
        return nohupStart(home: home)
    }

    private static func launchdJobLoaded() -> Bool {
        let uid = getuid()
        let r = runShell("launchctl print \"gui/\(uid)/\(launchdLabel)\" >/dev/null 2>&1")
        return r.ok
    }

    private static func nohupStart(home: String) -> Result {
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
                detail: ok ? "nohup fallback" : "launch exit=\(process.terminationStatus)"
            )
        } catch {
            return Result(launched: false, cccHome: home, detail: error.localizedDescription)
        }
    }

    private struct ShellResult {
        let ok: Bool
        let output: String
    }

    @discardableResult
    private static func runShell(_ command: String) -> ShellResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = ["-c", command]
        let out = Pipe()
        process.standardOutput = out
        process.standardError = out
        do {
            try process.run()
            process.waitUntilExit()
            let data = out.fileHandleForReading.readDataToEndOfFile()
            let text = String(data: data, encoding: .utf8) ?? ""
            return ShellResult(ok: process.terminationStatus == 0, output: text)
        } catch {
            return ShellResult(ok: false, output: error.localizedDescription)
        }
    }
}
