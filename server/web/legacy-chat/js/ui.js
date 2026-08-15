/**
 * ui.js — 共享 UI 原语（2026-08-15 前端架构重构收敛）
 *
 * 收敛目标（P0-3 / P1-4）：
 * - esc：5 份各页自写实现 → 统一 re-export utils.escapeHtml（P0-3）
 * - STATE_TONES：五态色板 3 份重复（taskCard/boardPage/consolePage）→ 一份（P1-4）
 *
 * 新页面（如 dshPage）一律从这里取原语，禁止本地再定义。
 */
import { escapeHtml } from './utils.js';

/** HTML 转义（别名，替代各页本地自写 esc()）。 */
export { escapeHtml as esc };

/** 卡五态色板（唯一真值；taskCard/boardPage/consolePage 从这 import）。 */
export const STATE_TONES = {
  待分派: '#a39e93',
  执行中: '#c47a2c',
  机审: '#8b6cc1',
  已回写: '#3d9a5f',
  打回: '#c44',
};
