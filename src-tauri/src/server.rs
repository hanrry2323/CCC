// CCC Cockpit — Python Chat Server 侧载管理 (sidecar)
//
// 职责：
//   - 启动时：spawn `python3 scripts/ccc-chat-server.py --port <P> --no-open` 子进程
//   - 就绪探测：轮询 http://127.0.0.1:<P>/ 是否返回 200
//   - 退出时：通过 Arc<Mutex<Option<Child>>> 共享给 main.rs，窗口关闭时 kill 子进程
//   - panic 安全：Drop 中兜底 kill
//
// 设计要点：
//   - 默认端口 8084，与 tauri.conf.json 的 devPath/distDir 对应
//   - 端口冲突时（已有 chat-server 跑着）跳过 spawn，直接用现有实例（向后兼容）
//   - 子进程在独立的 process group (macOS: posix_spawnattr_setpgroup) 中，
//     退出时 kill 整个 group，避免 uvicorn worker 残留

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub const DEFAULT_PORT: u16 = 8084;
pub const READY_TIMEOUT_SECS: u64 = 30;
pub const PROBE_INTERVAL_MS: u64 = 500;

#[derive(Clone)]
pub struct ServerHandle {
    inner: Arc<Mutex<Option<Child>>>,
    pub port: u16,
}

impl ServerHandle {
    pub fn new(inner: Arc<Mutex<Option<Child>>>, port: u16) -> Self {
        Self { inner, port }
    }

    /// 优雅退出：发送 SIGTERM，3s 内未退出则 SIGKILL。
    pub fn stop(&self) {
        let mut guard = match self.inner.lock() {
            Ok(g) => g,
            Err(p) => p.into_inner(),
        };
        if let Some(child) = guard.as_mut() {
            // 1) 先尝试 wait（如果已退出，wait 返回 Ok）
            match child.try_wait() {
                Ok(Some(_)) => {
                    *guard = None;
                    return;
                }
                _ => {}
            }
            // 2) 整个进程组 kill（macOS: pgid = pid）
            #[cfg(unix)]
            {
                let pid = child.id() as i32;
                // kill 整个进程组（pgid = pid，因为我们用 pre_exec setsid）
                unsafe { libc::killpg(pid, libc::SIGTERM); }
                let start = Instant::now();
                while start.elapsed() < Duration::from_secs(3) {
                    if let Ok(Some(_)) = child.try_wait() {
                        break;
                    }
                    thread::sleep(Duration::from_millis(100));
                }
                if let Ok(None) = child.try_wait() {
                    unsafe { libc::killpg(pid, libc::SIGKILL); }
                    let _ = child.wait();
                }
            }
            #[cfg(not(unix))]
            {
                let _ = child.kill();
                let _ = child.wait();
            }
            *guard = None;
        }
    }
}

impl Drop for ServerHandle {
    fn drop(&mut self) {
        self.stop();
    }
}

/// 探测 127.0.0.1:<port>/ 是否可连接（HTTP 200 视为就绪）。
/// 不解析 HTTP body，纯 TCP connect 即可。
fn probe_ready(port: u16) -> bool {
    match TcpStream::connect(("127.0.0.1", port)) {
        Ok(mut s) => {
            s.set_read_timeout(Some(Duration::from_millis(500))).ok();
            s.set_write_timeout(Some(Duration::from_millis(500))).ok();
            // 极简 HTTP/1.0 GET
            let req = format!(
                "GET / HTTP/1.0\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Basic Y2NjOmNsYXVkZTIwMjY=\r\n\r\n"
            );
            if s.write_all(req.as_bytes()).is_err() {
                return false;
            }
            let mut buf = [0u8; 64];
            if s.read(&mut buf).is_err() {
                return false;
            }
            // 任何 HTTP 响应（2xx/401/200）都认为端口在响应
            buf.starts_with(b"HTTP/")
        }
        Err(_) => false,
    }
}

/// 检测端口是否已被占用（用 connect 一次判定）
pub fn port_in_use(port: u16) -> bool {
    TcpStream::connect(("127.0.0.1", port)).is_ok()
}

/// 找到项目根目录：<exe>/../../  （devPath = "../tauri.conf.json" 在 src-tauri 下）
pub fn project_root() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(p) = exe.parent() {
            // dev: target/debug/ccc-cockpit-desktop → <root>/src-tauri/target/debug
            if let Some(src_tauri) = p.parent().and_then(|x| x.parent()) {
                if src_tauri.join("Cargo.toml").exists() {
                    if let Some(root) = src_tauri.parent() {
                        return root.to_path_buf();
                    }
                }
            }
            // bundle: CCC Cockpit.app/Contents/MacOS/ccc-cockpit-desktop
            // → ../../../
            if let Some(root) = p.ancestors().nth(3) {
                let has_scripts = root.join("scripts").join("ccc-chat-server.py").exists();
                if has_scripts {
                    return root.to_path_buf();
                }
            }
        }
    }
    // fallback：env CWD
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// spawn python 子进程并返回共享句柄。
///
/// 行为：
///   - 若 port 已被占用：返回 None（不 spawn，沿用现有实例）
///   - 若 port 空闲：spawn python3，probe 就绪后返回 Some(handle)
///   - spawn 或 probe 失败：返回 Err
pub fn spawn_chat_server(
    port: u16,
    cwd: &PathBuf,
) -> Result<Option<ServerHandle>, String> {
    if port_in_use(port) {
        eprintln!("[ccc-cockpit] port {port} 已被占用，复用现有实例");
        return Ok(None);
    }

    let script = cwd.join("scripts").join("ccc-chat-server.py");
    if !script.exists() {
        return Err(format!("找不到 chat-server 脚本: {}", script.display()));
    }

    eprintln!("[ccc-cockpit] 启动 sidecar: python3 {}", script.display());

    let mut cmd = Command::new("python3");
    cmd.arg(&script)
        .arg("--port")
        .arg(port.to_string())
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--no-open")
        .current_dir(cwd)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    // 在 Unix 上把子进程放入新进程组，便于 killpg
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        unsafe {
            cmd.pre_exec(|| {
                libc::setsid();
                Ok(())
            });
        }
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("spawn python3 失败: {e}"))?;

    // 启动一个独立线程读 stderr，避免 pipe 阻塞
    if let Some(mut stderr) = child.stderr.take() {
        thread::spawn(move || {
            use std::io::BufRead;
            let reader = std::io::BufReader::new(&mut stderr);
            for line in reader.lines().flatten() {
                eprintln!("[chat-server] {line}");
            }
        });
    }

    // probe 就绪
    let start = Instant::now();
    let timeout = Duration::from_secs(READY_TIMEOUT_SECS);
    let mut last_err = String::new();
    while start.elapsed() < timeout {
        if probe_ready(port) {
            eprintln!(
                "[ccc-cockpit] sidecar 就绪 port={port} ({}ms)",
                start.elapsed().as_millis()
            );
            let inner = Arc::new(Mutex::new(Some(child)));
            return Ok(Some(ServerHandle::new(inner, port)));
        }
        // 中途退出？
        if let Ok(Some(status)) = child.try_wait() {
            return Err(format!(
                "chat-server 启动后立即退出: status={status}"
            ));
        }
        last_err = format!("probe not ready ({}ms)", start.elapsed().as_millis());
        thread::sleep(Duration::from_millis(PROBE_INTERVAL_MS));
    }

    // 超时 — 清理
    let _ = child.kill();
    let _ = child.wait();
    Err(format!(
        "chat-server 在 {READY_TIMEOUT_SECS}s 内未就绪: {last_err}"
    ))
}
