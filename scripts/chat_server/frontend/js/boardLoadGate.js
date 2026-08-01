/**
 * boardLoadGate — 看板加载竞态门（无 DOM 依赖，可 node 单测）。
 *
 * 15s 轮询与移卡竞态：移卡 in-flight 期间挂起新加载（suppress），
 * 已在途的旧响应由 latest-wins（seq）丢弃，消除快速操作闪回。
 */
export function createLoadGate() {
  let seq = 0;
  let suppressed = 0;
  return {
    /** 请求开始：suppressed 期间返回 null（调用方应直接 return，不发起请求）。 */
    begin() {
      if (suppressed > 0) return null;
      seq += 1;
      return seq;
    },
    /** 结果是否仍是最新：仅最新 seq 可应用到状态（旧响应丢弃）。 */
    isLatest(s) {
      return s === seq;
    },
    /** 移卡等写操作开始：抑制并发加载。 */
    suppress() {
      suppressed += 1;
    },
    /** 写操作结束：恢复加载（计数式，支持并发多卡移动）。 */
    resume() {
      if (suppressed > 0) suppressed -= 1;
    },
    isSuppressed() {
      return suppressed > 0;
    },
  };
}
