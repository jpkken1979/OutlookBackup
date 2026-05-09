/**
 * state.js - Central state management + Polling
 */
const State = (() => {
  // Private state
  let _state = {
    accounts: [],
    psts: [],
    cacheFiles: [],
    config: {},
    history: [],
    currentTab: 'backup',
    isConnected: false,
  };

  // Listeners for reactive updates
  const _listeners = new Map();

  function set(key, value) {
    if (!_state.hasOwnProperty(key)) {
      console.warn(`[State] Unknown key: ${key}`);
      return;
    }
    _state[key] = value;
    // Notify listeners
    const callbacks = _listeners.get(key);
    if (callbacks) {
      callbacks.forEach(cb => cb(value));
    }
  }

  function get(key) {
    return _state[key];
  }

  function all() {
    return { ..._state };
  }

  function onChange(key, callback) {
    if (!_listeners.has(key)) {
      _listeners.set(key, new Set());
    }
    _listeners.get(key).add(callback);
    // Return unsubscribe function
    return () => _listeners.get(key)?.delete(callback);
  }

  function cleanup() {
    _listeners.clear();
  }

  function reset() {
    _state = {
      accounts: [],
      psts: [],
      cacheFiles: [],
      config: {},
      history: [],
      currentTab: 'backup',
      isConnected: false,
    };
  }

  async function init() {
    try {
      const config = await Api.get_config();
      set('config', config);
    } catch (err) {
      console.error('[State] Failed to load config:', err);
    }
  }

  return { set, get, all, onChange, cleanup, reset, init };
})();

// Polling manager
const Polling = (() => {
  const _intervals = new Map();
  const _callbacks = new Map();

  function start(operation, callback, interval = 500) {
    if (_intervals.has(operation)) {
      console.warn(`[Polling] ${operation} already running`);
      return;
    }

    _callbacks.set(operation, callback);

    const id = setInterval(async () => {
      try {
        await callback();
      } catch (err) {
        console.error(`[Polling] ${operation}:`, err);
      }
    }, interval);

    _intervals.set(operation, id);
    console.log(`[Polling] Started: ${operation} (${interval}ms)`);
  }

  function stop(operation) {
    const id = _intervals.get(operation);
    if (id) {
      clearInterval(id);
      _intervals.delete(operation);
      _callbacks.delete(operation);
      console.log(`[Polling] Stopped: ${operation}`);
    }
  }

  function stopAll() {
    _intervals.forEach((id, op) => {
      clearInterval(id);
      console.log(`[Polling] Stopped: ${op}`);
    });
    _intervals.clear();
    _callbacks.clear();
  }

  function isActive(operation) {
    return _intervals.has(operation);
  }

  function activeOperations() {
    return Array.from(_intervals.keys());
  }

  return { start, stop, stopAll, isActive, activeOperations };
})();

window.State = State;
window.Polling = Polling;