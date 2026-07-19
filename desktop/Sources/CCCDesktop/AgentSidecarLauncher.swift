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
            _ = runArgv([
                "/bin/launchctl", "kickstart", "-k",
                "gui/\(getuid())/\(launchdLabel)",
            ])
            return Result(launched: true, cccHome: home, detail: "launchd kickstart")
        }

        // 2) 安装并 load plist（常驻）— argv 数组，禁止 bash -c 拼接路径
        let install = (home as NSString)
            .appendingPathComponent("scripts/install-agent-sidecar-plist.sh")
        if FileManager.default.fileExists(atPath: install) {
            let r = runArgv(["/bin/bash", install, "--start"])
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
        let r = runArgv([
            "/bin/launchctl", "print", "gui/\(uid)/\(launchdLabel)",
        ])
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
        // 路径经 $1/$2/$3 传入，避免字符串拼接注入；& 后台避免 Process 等长驻进程
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        let cmd = #"cd "$1" && nohup bash "$2" >>"$3" 2>&1 &"#
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
    private static func runArgv(_ args: [String]) -> ShellResult {
        guard let exe = args.first else {
            return ShellResult(ok: false, output: "empty argv")
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: exe)
        process.arguments = Array(args.dropFirst())
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

    /// 遗留：仅固定字面量命令；路径相关请用 runArgv
    @discardableResult
    private static func runShell(_ command: String) -> ShellResult {
        runArgv(["/bin/bash", "-c", command])
    }
}
