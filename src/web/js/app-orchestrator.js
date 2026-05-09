/**
 * app.js - UNS Backup App v3.1 Orchestrator
 * ============================================
 * Maneja routing de tabs, init sequence, y coordinación global.
 * Los pages modules (backup.js, restore.js, etc.) hacen el trabajo pesado.
 */
(function() {
    'use strict';

    // ─── Pages Registry ────────────────────────────────────────────────────────
    const pages = {
        backup: BackupPage,
        restore: RestorePage,
        history: HistoryPage,
        auto: AutoPage,
        cache: CachePage,
        tools: ToolsPage,
        settings: SettingsPage,
    };

    // ─── State ─────────────────────────────────────────────────────────────────
    let currentTab = 'backup';
    let isInitialized = false;

    // ─── Init Sequence ────────────────────────────────────────────────────────
    async function init() {
        console.log('[App] Initializing...');

        // 1. Wait for pywebview bridge
        await waitForBridge();

        // 2. Init i18n
        if (window.I18n && typeof window.I18n.init === 'function') {
            await window.I18n.init();
        }

        // 3. Init state
        if (window.State && typeof window.State.init === 'function') {
            await window.State.init();
        }

        // 4. Load config
        try {
            const config = await Api.get_config();
            State.set('config', config);
        } catch (err) {
            console.error('[App] Failed to load config:', err);
        }

        // 5. Bind global events
        bindTabs();
        bindGlobalElements();
        updateConnectionBadge();

        // 6. Connect to Outlook
        await startConnect();

        // 7. Mount initial tab
        switchTab('backup');

        isInitialized = true;
        console.log('[App] Ready');
    }

    // ─── Wait for pywebview bridge ───────────────────────────────────────────
    async function waitForBridge() {
        if (window.pywebview && window.pywebview.api) return;

        return new Promise((resolve) => {
            const check = setInterval(() => {
                if (window.pywebview && window.pywebview.api) {
                    clearInterval(check);
                    resolve();
                }
            }, 50);
        });
    }

    // ─── Tab Routing ─────────────────────────────────────────────────────────
    function switchTab(tabName) {
        if (!pages[tabName]) {
            console.warn('[App] Unknown tab:', tabName);
            return;
        }

        // Unmount current page
        if (pages[currentTab] && pages[currentTab].unmount) {
            pages[currentTab].unmount();
        }

        // Update tab UI
        document.querySelectorAll('.tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tabName);
        });

        document.querySelectorAll('.tab-content').forEach(c => {
            c.classList.toggle('active', c.dataset.tabContent === tabName);
        });

        // Mount new page
        currentTab = tabName;
        State.set('currentTab', tabName);

        const content = document.querySelector(`.tab-content[data-tab-content="${tabName}"]`);
        if (content && pages[tabName] && pages[tabName].init) {
            pages[tabName].init(content);
        }
        if (pages[tabName] && pages[tabName].mount) {
            pages[tabName].mount();
        }
    }

    // ─── Event Binding ───────────────────────────────────────────────────────
    function bindTabs() {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                if (tabName) switchTab(tabName);
            });
        });
    }

    function bindGlobalElements() {
        // Connection badge
        const connBadge = document.querySelector('.conn-badge');
        if (connBadge) {
            connBadge.style.cursor = 'pointer';
            connBadge.addEventListener('click', () => switchTab('settings'));
        }
    }

    // ─── Outlook Connection ──────────────────────────────────────────────────
    async function startConnect() {
        setStatus('📡 Connecting to Outlook...');
        try {
            const r = await Api.connect_outlook();
            if (r.success) {
                setConnectionBadge(true);
                setStatus('✓ Connected to Outlook');
            } else {
                setConnectionBadge(false);
                setStatus('❌ ' + (r.error || 'Connection failed'));
            }
        } catch (err) {
            setConnectionBadge(false);
            setStatus('❌ Connection failed');
            console.error('[App] Outlook connection:', err);
        }
    }

    function setConnectionBadge(connected) {
        const badge = document.querySelector('.conn-badge');
        if (badge) {
            badge.classList.toggle('online', connected);
            badge.classList.toggle('offline', !connected);
            badge.querySelector('.conn-dot').nextSibling.textContent = connected ? 'Connected' : 'Disconnected';
        }
    }

    function updateConnectionBadge() {
        // Called periodically or on user action
    }

    // ─── Status Bar ──────────────────────────────────────────────────────────
    function setStatus(msg) {
        const statusEl = document.getElementById('sb-status');
        if (statusEl) {
            statusEl.textContent = '● ' + msg;
        }
    }

    // ─── Modal/Toast wrappers (for pages) ─────────────────────────────────────
    async function confirm(title, body) {
        if (window.Modal && window.Modal.confirm) {
            return window.Modal.confirm(title, body);
        }
        return window.confirm(body);
    }

    async function alert(title, body) {
        if (window.Modal && window.Modal.alert) {
            return window.Modal.alert(title, body);
        }
        window.alert(body);
    }

    function showToast(msg, type) {
        if (window.Toast && window.Toast.show) {
            return window.Toast.show(msg, type);
        }
        console.log(`[${type}] ${msg}`);
    }

    // ─── Helpers ────────────────────────────────────────────────────────────
    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ─── Public API (window.App) ─────────────────────────────────────────────
    window.App = {
        init,
        switchTab,
        confirm,
        alert,
        showToast,
        setStatus,
        escapeHtml,
        isReady: () => isInitialized,
        getCurrentTab: () => currentTab,
    };

    // ─── Auto-init ──────────────────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();