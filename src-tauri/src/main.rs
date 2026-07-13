// CCC Cockpit Desktop — Tauri main entry
//
// Phase 1: Tauri 窗口骨架 → http://127.0.0.1:8084
// Phase 2: 启动时 sidecar spawn `python3 scripts/ccc-chat-server.py`，等待就绪
//          窗口关闭时通过 ServerHandle.stop() 杀子进程
// Phase 3: 菜单、托盘、通知、原生体验（在 menu.rs 中实现）

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::{Manager, WindowEvent};

mod server;
mod menu;

use server::{spawn_chat_server, ServerHandle, DEFAULT_PORT};
use menu::{build_app_menu, build_tray, handle_menu_event, handle_tray_event, register_commands};

fn main() {
    let port: u16 = std::env::var("CCC_COCKPIT_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_PORT);

    let project_root = server::project_root();
    eprintln!("[ccc-cockpit] project_root = {}", project_root.display());

    // Phase 2: 启动 sidecar（如果端口已被占用就复用现有实例）
    let server_handle: Option<ServerHandle> = match spawn_chat_server(port, &project_root) {
        Ok(h) => h,
        Err(e) => {
            eprintln!("[ccc-cockpit] WARN: sidecar 启动失败: {e}");
            eprintln!("[ccc-cockpit] 继续打开窗口，用户可手动启动 chat-server");
            None
        }
    };

    let server_for_setup: Option<ServerHandle> = server_handle.clone();
    let server_for_close: Option<ServerHandle> = server_handle.clone();

    let app_menu = build_app_menu();
    let system_tray = build_tray();

    let builder = tauri::Builder::default()
        .menu(app_menu)
        .system_tray(system_tray)
        .on_menu_event(|event| {
            handle_menu_event_inner(event);
        })
        .on_system_tray_event(|app, event| {
            handle_tray_event(app, event);
        })
        .setup(move |app| {
            if let Some(win) = app.get_window("main") {
                let url = win.url();
                eprintln!("[ccc-cockpit] window opened, url={url}");
                win.set_title("CCC Cockpit").ok();
            } else {
                eprintln!("[ccc-cockpit] WARN: main window not found in setup");
            }

            if let Some(h) = server_for_setup.as_ref() {
                eprintln!("[ccc-cockpit] sidecar running on port {}", h.port);
            } else {
                eprintln!("[ccc-cockpit] no sidecar (reusing existing or failed)");
            }

            Ok(())
        })
        .on_window_event(move |event| {
            if let WindowEvent::CloseRequested { .. } = event.event() {
                if let Some(h) = server_for_close.as_ref() {
                    eprintln!("[ccc-cockpit] window close: stopping sidecar");
                    h.stop();
                }
            }
        });

    register_commands(builder)
        .run(tauri::generate_context!())
        .expect("error while running CCC Cockpit desktop application");
}
