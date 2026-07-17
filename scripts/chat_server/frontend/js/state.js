class State {
  constructor() {
    this.listeners = {};
    this.data = {
      sessions: [],
      currentSessionId: null,
      currentMessages: [],
      currentProject: 'ccc',
      streaming: false,
      streamingCount: 0,
      model: 'flash',
      abortController: null,
      tabs: [],
      activeTabId: null,
      projectWorkspaceMap: {},
    };
  }

  get(key) { return this.data[key]; }
  set(key, value) {
    this.data[key] = value;
    this.emit(key, value);
  }

  on(event, fn) {
    (this.listeners[event] = this.listeners[event] || []).push(fn);
  }
  emit(event, data) {
    (this.listeners[event] || []).forEach(fn => fn(data));
  }
}

export const state = new State();
