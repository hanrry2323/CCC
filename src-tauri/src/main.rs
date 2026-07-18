// CCC Desktop — Tauri shell for LAN Hub (multi-session UI)
//
// Default: load remote CCC_SERVER (Mac2017 Hub), no local sidecar.
// Dev fallback: CCC_DESKTOP_LOCAL=1 spawns local chat-server sidecar.

#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::{Manager, WindowEvent};

mod menu;
mod server;

use menu::{build_app_menu, build_tray, handle_menu_event, handle_tray_event, register_commands};
use server::{spawn_chat_server, ServerHandle, DEFAULT_PORT};

fn default_server_url() -> String {
    std::env::var("CCC_SERVER").unwrap_or_else(|_| "http://192.168.3.116:7777".to_string())
}

fn use_local_sidecar() -> bool {
    matches!(
        std::env::var("CCC_DESKTOP_LOCAL").as_deref(),
        Ok("1") | Ok("true") | Ok("yes")
    )
}

fn hub_url_with_desktop_flag(base: &str) -> String {
    let base = base.trim_end_matches('/');
    if base.contains("desktop=1") {
        base.to_string()
    } else if base.contains('?') {
        format!("{base}&desktop=1")
    } else {
        format!("{base}?desktop=1")
    }
}

fn main() {
    let remote_url = hub_url_with_desktop_flag(&default_server_url());
    let local = use_local_sidecar();

    let port: u16 = std::env::var("CCC_COCKPIT_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(DEFAULT_PORT);

    let project_root = server::project_root();
    eprintln!("[ccc-desktop] project_root = {}", project_root.display());
    eprintln!("[ccc-desktop] CCC_SERVER target = {remote_url}");
    eprintln!("[ccc-desktop] local_sidecar = {local}");

    let server_handle: Option<ServerHandle> = if local {
        match spawn_chat_server(port, &project_root) {
            Ok(h) => h,
            Err(e) => {
                eprintln!("[ccc-desktop] WARN: sidecar failed: {e}");
                None
            }
        }
    } else {
        None
    };

    let server_for_setup = server_handle.clone();
    let server_for_close = server_handle.clone();
    let nav_url = if local {
        hub_url_with_desktop_flag(&format!("http://127.0.0.1:{port}"))
    } else {
        remote_url.clone()
    };

    let app_menu = build_app_menu();
    let system_tray = build_tray();

    let builder = tauri::Builder::default()
        .menu(app_menu)
        .system_tray(system_tray)
        .on_menu_event(|event| {
            handle_menu_event(event);
        })
        .on_system_tray_event(|app, event| {
            handle_tray_event(app, event);
        })
        .setup(move |app| {
            if let Some(win) = app.get_window("main") {
                win.set_title("CCC Desktop").ok();
                let target = nav_url.clone();
                eprintln!("[ccc-desktop] navigate → {target}");
                // Prefer location.replace so remote Hub loads with ?desktop=1
                let js = format!(
                    "window.location.replace({})",
                    serde_json::to_string(&target).unwrap_or_else(|_| "\"/\"".into())
                );
                if let Err(e) = win.eval(&js) {
                    eprintln!("[ccc-desktop] WARN: navigate eval failed: {e}");
                }
            }

            if let Some(h) = server_for_setup.as_ref() {
                eprintln!("[ccc-desktop] sidecar on port {}", h.port);
            }

            Ok(())
        })
        .on_window_event(move |event| {
            if let WindowEvent::CloseRequested { .. } = event.event() {
                if let Some(h) = server_for_close.as_ref() {
                    eprintln!("[ccc-desktop] stop sidecar");
                    h.stop();
                }
            }
        });

    register_commands(builder)
        .run(tauri::generate_context!())
        .expect("error while running CCC Desktop");
}
