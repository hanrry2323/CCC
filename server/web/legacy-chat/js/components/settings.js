/**
 * settings.js — CCC 设置面板（ccc-plan-045 P2 残留清理后）。
 *
 * 已清理的残留项（2026-08-24，均为旧架构遗留、零消费者的死配置）：
 * - 「连接」组：服务端地址 / 对话 Agent 地址（ports.js 早已定稿前端同源相对路径，
 *   hubBase()/agentBase() 恒空串；写入的 window.__CCC_HUB_BASE__ 等无人读取）
 * - 「连接」组：workspace 路径映射（唯一消费者 utils.resolveProjectPath 全仓无调用方）
 * - 「项目」组：当前项目下拉（消费者 composer/taskDialog 随对话栈拆除）
 * - 双壳提示文案（isDialogueShell，双壳架构已退役）
 * 保留：外观（主题三态）、关于（版本）。
 */

import { getThemeScheme, setThemeScheme } from '../theme.js';

export async function openSettings() {
  // 重复打开：先移除旧面板（幂等）
  document.querySelector('.settings-sheet')?.remove();
  document.querySelector('.dialog-overlay')?.remove();

  const overlay = document.createElement('div');
  overlay.className = 'dialog-overlay';
  overlay.addEventListener('click', closeSettings);
  document.body.appendChild(overlay);

  const dialog = document.createElement('div');
  dialog.className = 'settings-sheet';
  dialog.innerHTML =
    '<div class="settings-panel">' +
    '<div class="settings-header">' +
    '<span class="settings-title">' +
    '<svg class="settings-title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="12" r="3"/>' +
    '<path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>' +
    '</svg>' +
    '设置' +
    '</span>' +
    '<button class="settings-close" id="settings-close-btn">×</button>' +
    '</div>' +
    '<div class="settings-body">' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">外观</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">主题</span>' +
    '<select class="settings-select" id="settings-theme">' +
    '<option value="light">浅色</option>' +
    '<option value="dark">深色</option>' +
    '<option value="system">跟随系统</option>' +
    '</select>' +
    '</div>' +
    '</div>' +
    '<div class="settings-group">' +
    '<div class="settings-group-title">关于</div>' +
    '<div class="settings-row">' +
    '<span class="settings-label">版本</span>' +
    '<span class="settings-row-value">CCC v0.70.0（2017 单端 :7788 · 信息墙默认视图）</span>' +
    '</div>' +
    '</div>' +
    '</div>' +
    '</div>';
  document.body.appendChild(dialog);

  // 异步续跑前校验对话框仍在（快速关开防 null 解引用与重复绑定）
  const themeSelect = document.getElementById('settings-theme');
  if (themeSelect && themeSelect.isConnected) {
    themeSelect.value = getThemeScheme();
    themeSelect.addEventListener('change', () => {
      setThemeScheme(themeSelect.value);
    });
  }

  document
    .getElementById('settings-close-btn')
    ?.addEventListener('click', closeSettings);
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      closeSettings();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
}

function closeSettings() {
  document.querySelector('.settings-sheet')?.remove();
  document.querySelector('.dialog-overlay')?.remove();
}
