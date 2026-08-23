class State {
  constructor() {
    this.listeners = {};
    this.data = {
      sessions: [],
      currentSessionId: null,
      currentMessages: [],
      currentProject: null,
      defaultProject: null,
      streaming: false,
      streamingCount: 0,
      maxLiveStreams: 4,
      historySource: 'all',
      model: 'flash',
      toolMode: 'engineer',
      claudeSessionIdByThread: {},
      abortController: null,
      tabs: [],
      activeTabId: null,
      projectWorkspaceMap: {},
      dualPaneEnabled: false,
      dualPaneFocus: 'left',
      paneLeftTabId: null,
      paneRightTabId: null,
    };
  }

  get(key) { return this.data[key]; }
  set(key, value) {
    this.data[key] = value;
    this.emit(key, value);
  }

  on(event, fn) {
    (this.listeners[event] = this.listeners[event] || []).push(fn);
    // 2026-08-24：返回退订函数（此前无 off 途径）
    return () => {
      this.listeners[event] = (this.listeners[event] || []).filter(f => f !== fn);
    };
  }
  emit(event, data) {
    // 2026-08-24：逐个隔离异常——一个监听器抛错不再中断后续监听器
    (this.listeners[event] || []).forEach(fn => {
      try { fn(data); } catch (e) { console.error('state listener error:', event, e); }
    });
  }
}

export const state = new State();
