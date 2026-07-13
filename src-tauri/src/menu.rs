// CCC Cockpit — 原生菜单 + 系统托盘 + 通知
//
// Phase 3 实现：
//   1. macOS 菜单栏（应用 / 文件 / 编辑 / 视图 / 窗口 / 帮助）
//   2. 系统托盘（左键切显示/隐藏，右键菜单：显示/隐藏/退出）
//   3. 通知 Tauri 命令 `notify_user`（WebView 通过 invoke 调用）
//   4. 菜单事件 → WebView 派发（reload / new-session / devtools）
//
// 设计要点：
//   - 菜单事件统一在 main.rs 的 on_menu_event 处理
//   - 系统托盘图标用 tauri.conf.json 中已配置的 icons/icon.png
//   - 通知点击：默认聚焦到主窗口（macOS 通知中心）

use tauri::{
    AppHandle, CustomMenuItem, Manager, Menu, MenuItem, Submenu, SystemTray,
    SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem, WindowMenuEvent, Wry,
};

/// 全局菜单 ID 集合（main.rs 中 match 用）
pub mod ids {
    pub const RELOAD: &str = "menu_reload";
    pub const DEVTOOLS: &str = "menu_devtools";
    pub const NEW_SESSION: &str = "menu_new_session";
    pub const SAVE_SESSION: &str = "menu_save_session";
    pub const CLOSE_WINDOW: &str = "menu_close_window";
    pub const ABOUT: &str = "menu_about";
    pub const REPOSITORY: &str = "menu_repository";
    pub const QUIT: &str = "menu_quit";

    // tray
    pub const TRAY_SHOW: &str = "tray_show";
    pub const TRAY_HIDE: &str = "tray_hide";
    pub const TRAY_QUIT: &str = "tray_quit";
}

/// 构建 macOS 主菜单
pub fn build_app_menu() -> Menu {
    let app_submenu = Submenu::new(
        "CCC Cockpit",
        Menu::new()
            .add_item(CustomMenuItem::new(ids::ABOUT, "关于 CCC Cockpit"))
            .add_native_item(MenuItem::Separator)
            .add_native_item(MenuItem::Quit),
    );

    let file_submenu = Submenu::new(
        "文件",
        Menu::new()
            .add_item(
                CustomMenuItem::new(ids::NEW_SESSION, "新建会话")
                    .accelerator("CmdOrCtrl+N"),
            )
            .add_item(
                CustomMenuItem::new(ids::SAVE_SESSION, "保存")
                    .accelerator("CmdOrCtrl+S"),
            )
            .add_native_item(MenuItem::Separator)
            .add_item(
                CustomMenuItem::new(ids::CLOSE_WINDOW, "关闭窗口")
                    .accelerator("CmdOrCtrl+W"),
            ),
    );

    let edit_submenu = Submenu::new(
        "编辑",
        Menu::new()
            .add_native_item(MenuItem::Undo)
            .add_native_item(MenuItem::Redo)
            .add_native_item(MenuItem::Separator)
            .add_native_item(MenuItem::Cut)
            .add_native_item(MenuItem::Copy)
            .add_native_item(MenuItem::Paste)
            .add_native_item(MenuItem::SelectAll),
    );

    let view_submenu = Submenu::new(
        "视图",
        Menu::new()
            .add_item(
                CustomMenuItem::new(ids::RELOAD, "重新加载")
                    .accelerator("CmdOrCtrl+R"),
            )
            .add_item(
                CustomMenuItem::new(ids::DEVTOOLS, "开发者工具")
                    .accelerator("CmdOrCtrl+Shift+I"),
            )
            .add_native_item(MenuItem::Separator)
            .add_native_item(MenuItem::EnterFullScreen),
    );

    let window_submenu = Submenu::new(
        "窗口",
        Menu::new()
            .add_native_item(MenuItem::Minimize),
    );

    let help_submenu = Submenu::new(
        "帮助",
        Menu::new()
            .add_item(CustomMenuItem::new(ids::ABOUT, "关于 CCC Cockpit"))
            .add_item(CustomMenuItem::new(ids::REPOSITORY, "GitHub 仓库")),
    );

    Menu::new()
        .add_submenu(app_submenu)
        .add_submenu(file_submenu)
        .add_submenu(edit_submenu)
        .add_submenu(view_submenu)
        .add_submenu(window_submenu)
        .add_submenu(help_submenu)
}

/// 构建系统托盘 + 右键菜单
pub fn build_tray() -> SystemTray {
    let tray_menu = SystemTrayMenu::new()
        .add_item(CustomMenuItem::new(ids::TRAY_SHOW, "显示窗口"))
        .add_item(CustomMenuItem::new(ids::TRAY_HIDE, "隐藏窗口"))
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(CustomMenuItem::new(ids::TRAY_QUIT, "退出 CCC Cockpit"));

    SystemTray::new()
        .with_menu(tray_menu)
        .with_title("CCC Cockpit")
}

/// 菜单事件处理（main.rs 在 on_menu_event 调用此函数）
pub fn handle_menu_event(event: WindowMenuEvent) {
    let id = event.menu_item_id();
    let app = event.window().app_handle();
    match id {
        ids::RELOAD => {
            if let Some(win) = app.get_window("main") {
                let _ = win.eval("window.location.reload()");
            }
        }
        ids::DEVTOOLS => {
            #[cfg(debug_assertions)]
            if let Some(win) = app.get_window("main") {
                win.open_devtools();
            }
            #[cfg(not(debug_assertions))]
            {
                eprintln!("[ccc-cockpit] devtools only available in debug build");
            }
        }
        ids::NEW_SESSION => {
            if let Some(win) = app.get_window("main") {
                let _ = win.eval("window.dispatchEvent(new CustomEvent('ccc:new-session'))");
            }
        }
        ids::SAVE_SESSION => {
            if let Some(win) = app.get_window("main") {
                let _ = win.eval("window.dispatchEvent(new CustomEvent('ccc:save-session'))");
            }
        }
        ids::CLOSE_WINDOW => {
            if let Some(win) = app.get_window("main") {
                let _ = win.close();
            }
        }
        ids::ABOUT => {
            if let Some(win) = app.get_window("main") {
                let _ = win.eval("window.dispatchEvent(new CustomEvent('ccc:show-about'))");
            }
        }
         ids::REPOSITORY => {
            let _ = app.shell_scope().open("https://github.com/anomalyco/opencode", None);
        }
        _ => {
            eprintln!("[ccc-cockpit] unhandled menu id: {id}");
        }
    }
}

/// 托盘事件处理（main.rs 在 on_system_tray_event 调用此函数）
pub fn handle_tray_event(app: &AppHandle, event: SystemTrayEvent) {
    match event {
        SystemTrayEvent::LeftClick { .. } => {
            toggle_main_window(app);
        }
        SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
            ids::TRAY_SHOW => {
                if let Some(win) = app.get_window("main") {
                    let _ = win.show();
                    let _ = win.set_focus();
                }
            }
            ids::TRAY_HIDE => {
                if let Some(win) = app.get_window("main") {
                    let _ = win.hide();
                }
            }
            ids::TRAY_QUIT => {
                eprintln!("[ccc-cockpit] tray quit");
                std::process::exit(0);
            }
            _ => {
                eprintln!("[ccc-cockpit] unhandled tray id: {id}");
            }
        },
        _ => {}
    }
}

fn toggle_main_window(app: &AppHandle) {
    if let Some(win) = app.get_window("main") {
        match win.is_visible() {
            Ok(true) => {
                let _ = win.hide();
            }
            _ => {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }
    }
}

 /// Tauri 命令：发送 macOS 通知
#[tauri::command]
pub fn notify_user(app: AppHandle, title: String, body: String) -> Result<(), String> {
    let identifier = app.config().tauri.bundle.identifier;
    let id: &str = identifier.as_str();
    tauri::api::notification::Notification::new(id)
        .title(title)
        .body(body)
        .show()
        .map_err(|e| e.to_string())
}

/// 把命令注册到 Tauri builder
pub fn register_commands(builder: tauri::Builder<Wry>) -> tauri::Builder<Wry> {
    builder.invoke_handler(tauri::generate_handler![notify_user])
}
