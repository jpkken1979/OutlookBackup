/**
 * i18n.js - UNS Backup i18n loader
 * Carga ja.json y provee t(key, params) para el frontend
 */
const I18n = (() => {
  let _strings = {};
  let _ready = false;

  async function init() {
    try {
      const response = await fetch('./js/i18n/ja.json');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      _strings = await response.json();
      _ready = true;
      console.log('[i18n] Loaded:', Object.keys(_strings).length, 'strings');
    } catch (err) {
      console.error('[i18n] Failed to load ja.json:', err);
      _ready = true;
    }
  }

  function t(key, params) {
    if (!_ready) {
      console.warn('[i18n] Not initialized yet');
    }

    const template = _strings[key];
    if (template === undefined) {
      console.warn(`[i18n] Key not found: "${key}"`);
      return key;
    }

    if (params === undefined || params === null) {
      return template;
    }

    try {
      return template.replace(/\{(\w+)\}/g, (match, varName) => {
        return params.hasOwnProperty(varName) ? params[varName] : match;
      });
    } catch (err) {
      console.error('[i18n] Interpolation error:', err);
      return template;
    }
  }

  function isReady() {
    return _ready;
  }

  return { init, t, isReady };
})();

// Auto-init
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => I18n.init());
} else {
  I18n.init();
}

// Export for global access
window.I18n = I18n;
window.t = I18n.t;