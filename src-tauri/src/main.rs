// CCC Cockpit Desktop — Tauri main entry
//
// Phase 1 scaffold: 启动 Tauri 窗口加载 http://127.0.0.1:8084
// Phase 2 会在此基础上增加 Python 服务侧载（见 server.rs）
// Phase 3 会在此基础上增加菜单、托盘、通知、原生体验
//
// 架构说明：
//   - tauri.conf.json 指向 http://127.0.0.1:8084，WebView 加载 Chat Server
//   - 8084 服务由独立 Python 进程提供（CCC 现有架构，桌面端仅做窗口壳）
//   - 此文件最小化 Phase 1 目标：编译通过、窗口打开、加载目标 URL
#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::Manager;

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // 启动时记录：哪个窗口打开了、目标 URL 是什么
            if let Some(win) = app.get_window("main") {
                let url = win.url();
                eprintln!("[ccc-cockpit] window opened, url={url}");
            } else {
                eprintln!("[ccc-cockpit] WARN: main window not found in setup");
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running CCC Cockpit desktop application");
}
