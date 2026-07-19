import Foundation

/// Desktop 拉起本机 Agent Sidecar：优先 launchd KeepAlive，失败再 nohup。
enum AgentSidecarLauncher {
    static let launchdLabel = "com.ccc.agent-sidecar"
    static let defaultAgentBase = "http://127.0.0.1:7788"

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

    /// 同步探测 sidecar /health（短超时）；健康则勿 kickstart -k
    static func isHealthy(agentBase: String = defaultAgentBase) -> Bool {
        let raw = agentBase.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !raw.isEmpty,
              let base = URL(string: raw),
              let url = URL(string: "health", relativeTo: base)?.absoluteURL
        else { return false }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.timeoutInterval = 2
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        let task = URLSession.shared.dataTask(with: req) { data, resp, _ in
            defer { sem.signal() }
            guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else { return }
            if let data,
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let flag = obj["ok"] as? Bool {
                ok = flag
            } else {
                ok = true
            }
        }
        task.resume()
        _ = sem.wait(timeout: .now() + 2.5)
        return ok
    }

    /// 确保 sidecar 在跑：health 优先 → soft kickstart → 必要时 -k → install → nohup
    @discardableResult
    static func ensureRunning(cccHomeHint: String?, agentBase: String = defaultAgentBase) -> Result {
        let home = resolveCCCHome(configured: cccHomeHint)

        // 0) 已健康：禁止 kickstart -k（避免 SIGTERM 风暴丢 live slot）
        if isHealthy(agentBase: agentBase) {
            return Result(
                launched: true,
                cccHome: home,
                detail: "already healthy"
            )
        }

        guard let home else {
            return Result(
                launched: false,
                cccHome: nil,
                detail: "找不到 CCC 仓（设 CCC_HOME 或设置里 CCC 仓根）"
            )
        }

        // 1) launchd job 已 load：先 soft kickstart，仍不健康再 -k
        if launchdJobLoaded() {
            _ = runArgv([
                "/bin/launchctl", "kickstart",
                "gui/\(getuid())/\(launchdLabel)",
            ])
            if waitHealthy(agentBase: agentBase, seconds: 3) {
                return Result(launched: true, cccHome: home, detail: "launchd kickstart")
            }
            _ = runArgv([
                "/bin/launchctl", "kickstart", "-k",
                "gui/\(getuid())/\(launchdLabel)",
            ])
            if waitHealthy(agentBase: agentBase, seconds: 5) {
                return Result(launched: true, cccHome: home, detail: "launchd kickstart -k")
            }
            return Result(launched: true, cccHome: home, detail: "launchd kickstart -k (warming)")
        }

        // 2) 安装并 load plist（常驻）— argv 数组，禁止 bash -c 拼接路径
        let install = (home as NSString)
            .appendingPathComponent("scripts/install-agent-sidecar-plist.sh")
        if FileManager.default.fileExists(atPath: install) {
            let r = runArgv(["/bin/bash", install, "--start"])
            if r.ok {
                _ = waitHealthy(agentBase: agentBase, seconds: 5)
                return Result(launched: true, cccHome: home, detail: "launchd installed")
            }
            // 继续兜底
        }

        // 3) nohup 兜底（无 launchd / 权限失败）
        return nohupStart(home: home)
    }

    @discardableResult
    private static func waitHealthy(agentBase: String, seconds: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(seconds)
        while Date() < deadline {
            if isHealthy(agentBase: agentBase) { return true }
            Thread.sleep(forTimeInterval: 0.35)
        }
        return isHealthy(agentBase: agentBase)
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
