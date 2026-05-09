/**
 * settings.js - Account Settings Page Module
 * UNS Backup App v3.1
 * CONTAINS THE 3 CRITICAL FIXES:
 * - FIX 1: Uses 'account-domain-filter' as input ID (NOT 'settings-domain-filter')
 * - FIX 2: bindEvents() includes: btn-settings-save-domain, btn-settings-save-all, btn-settings-refresh-accounts
 * - FIX 3: persistAccountSettings() uses correct bindings
 */
const SettingsPage = (() => {
    'use strict';

    let container = null;
    let config = {};
    let accounts = [];

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        bindEvents();
    }

    function mount() {
        loadAccountSettings();
    }

    function unmount() {
        // Nothing to clean up
    }

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        // FIX 2: All required binds
        document.getElementById('btn-settings-save-domain')?.addEventListener('click', persistAccountSettings);
        document.getElementById('btn-settings-save-all')?.addEventListener('click', persistAccountSettings);
        document.getElementById('btn-settings-refresh-accounts')?.addEventListener('click', refreshAccounts);

        // Format and import mode radios
        document.querySelectorAll('input[name="settings-format"]').forEach(r => {
            r.addEventListener('change', () => persistAccountSettings());
        });
        document.querySelectorAll('input[name="settings-import-mode"]').forEach(r => {
            r.addEventListener('change', () => persistAccountSettings());
        });

        // Inventory toggles
        document.getElementById('inv-enabled')?.addEventListener('change', (e) => {
            const opts = document.getElementById('inv-options');
            if (opts) opts.style.display = e.target.checked ? 'block' : 'none';
        });
        document.getElementById('inv-passwords')?.addEventListener('change', (e) => {
            const pwdFields = document.getElementById('pwd-fields');
            if (pwdFields) pwdFields.style.display = e.target.checked ? 'block' : 'none';
        });
    }

    // ─── Load Account Settings ─────────────────────────────────
    async function loadAccountSettings() {
        setStatus('🔍 Loading accounts...');
        try {
            // Load config first
            config = await Api.get_config() || {};
            State.set('config', config);

            // Load account details
            const r = await Api.get_account_details();
            if (!r.success) {
                Toast.show('Failed to load accounts: ' + r.error, 'error');
                setStatus('❌ Load failed');
                return;
            }
            accounts = r.accounts || [];
            State.set('accounts', accounts);
            renderAccountSettingsList();
            applyConfigToUI();
            setStatus(`✓ Loaded ${accounts.length} accounts`);
        } catch (err) {
            console.error('[SettingsPage] loadAccountSettings:', err);
            Toast.show('Load error: ' + err.message, 'error');
        }
    }

    function applyConfigToUI() {
        // FIX 1: Use 'account-domain-filter' (NOT 'settings-domain-filter')
        const domainEl = document.getElementById('account-domain-filter');
        if (domainEl) domainEl.value = config.domain_filter || '';

        const fmt = config.default_format || 'pst';
        const fmtEl = document.querySelector(`input[name="settings-format"][value="${fmt}"]`);
        if (fmtEl) fmtEl.checked = true;

        const im = config.default_import_mode || 'separate_folder';
        const imEl = document.querySelector(`input[name="settings-import-mode"][value="${im}"]`);
        if (imEl) imEl.checked = true;

        const invEnabledEl = document.getElementById('inv-enabled');
        if (invEnabledEl) {
            invEnabledEl.checked = config.inventory_enabled || false;
            const invOpts = document.getElementById('inv-options');
            if (invOpts) invOpts.style.display = invEnabledEl.checked ? 'block' : 'none';
        }
        const invServersEl = document.getElementById('inv-servers');
        if (invServersEl) invServersEl.checked = config.inventory_include_servers !== false;
        const invPasswordsEl = document.getElementById('inv-passwords');
        if (invPasswordsEl) {
            invPasswordsEl.checked = config.inventory_include_passwords || false;
            const pwdFields = document.getElementById('pwd-fields');
            if (pwdFields) pwdFields.style.display = invPasswordsEl.checked ? 'block' : 'none';
        }
    }

    function renderAccountSettingsList() {
        const grid = document.getElementById('account-settings-grid');
        if (!grid) return;

        if (accounts.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:48px;">📭</div>
                    <p>No accounts found</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = accounts.map((a, i) => {
            const initial = (a.smtp || '?').charAt(0).toUpperCase();
            const colorStyle = (a.smtp || '').startsWith('info')
                ? 'style="background: linear-gradient(135deg, #ff3838, #b91c1c);"'
                : '';
            return `
                <div class="account-item" data-idx="${i}">
                    <div class="acc-icon" ${colorStyle}>${escapeHtml(initial)}</div>
                    <div class="acc-info">
                        <div class="acc-email">${escapeHtml(a.smtp || '')}</div>
                        <div class="acc-meta">${escapeHtml(a.type || 'IMAP')} · ${escapeHtml(a.display_name || '')}</div>
                    </div>
                    <div class="acc-actions">
                        <button class="btn btn-secondary" data-action="detail" data-smtp="${escapeHtml(a.smtp || '')}">詳細</button>
                        <button class="btn btn-secondary" data-action="test" data-smtp="${escapeHtml(a.smtp || '')}">テスト</button>
                        <button class="btn btn-primary" data-action="export" data-smtp="${escapeHtml(a.smtp || '')}">Export</button>
                    </div>
                </div>
            `;
        }).join('');

        grid.querySelectorAll('[data-action="detail"]').forEach(btn => {
            btn.addEventListener('click', () => openAccountDetail(btn.dataset.smtp));
        });
        grid.querySelectorAll('[data-action="test"]').forEach(btn => {
            btn.addEventListener('click', () => testConnection(btn.dataset.smtp));
        });
        grid.querySelectorAll('[data-action="export"]').forEach(btn => {
            btn.addEventListener('click', () => exportSingleAccount(btn.dataset.smtp));
        });
    }

    // ─── Persist Account Settings ───────────────────────────────
    async function persistAccountSettings() {
        // FIX 1: Read from 'account-domain-filter' (NOT 'settings-domain-filter')
        const domainFilter = document.getElementById('account-domain-filter')?.value || '';
        const fmtEl = document.querySelector('input[name="settings-format"]:checked');
        const format = fmtEl ? fmtEl.value : 'pst';
        const imEl = document.querySelector('input[name="settings-import-mode"]:checked');
        const importMode = imEl ? imEl.value : 'separate_folder';

        const updates = {
            domain_filter: domainFilter,
            default_format: format,
            default_import_mode: importMode,
        };

        try {
            await Api.update_config(updates);
            Object.assign(config, updates);
            Toast.show('設定が保存されました', 'success');
        } catch (err) {
            console.error('[SettingsPage] persistAccountSettings:', err);
            Toast.show('Save error: ' + err.message, 'error');
        }
    }

    // ─── Refresh Accounts ──────────────────────────────────────
    async function refreshAccounts() {
        setStatus('🔍 Refreshing accounts...');
        try {
            const r = await Api.detect_accounts();
            if (!r.success) {
                Toast.show('Detection failed: ' + r.error, 'error');
                setStatus('❌ Detection failed');
                return;
            }
            accounts = r.accounts || [];
            State.set('accounts', accounts);
            renderAccountSettingsList();
            setStatus(`✓ ${accounts.length} accounts detected`);
        } catch (err) {
            console.error('[SettingsPage] refreshAccounts:', err);
            Toast.show('Refresh error: ' + err.message, 'error');
        }
    }

    // ─── Account Detail ────────────────────────────────────────
    async function openAccountDetail(smtp) {
        setStatus('🔍 Loading account details...');
        try {
            const r = await Api.get_account_details(smtp);
            if (!r.success) {
                Toast.show('Failed to load details: ' + r.error, 'error');
                return;
            }
            const a = r.account || {};
            let body = `SMTP: ${escapeHtml(a.smtp || smtp)}\n`;
            body += `Display Name: ${escapeHtml(a.display_name || '—')}\n`;
            body += `Account Type: ${escapeHtml(a.type || '—')}\n\n`;
            if (a.server) {
                body += `Server: ${escapeHtml(a.server)}\n`;
                body += `Port: ${a.port || '—'}\n`;
                body += `Security: ${escapeHtml(a.security || '—')}\n`;
            }
            Modal.alert('📧 ACCOUNT DETAILS', body);
            setStatus('✓ Details loaded');
        } catch (err) {
            console.error('[SettingsPage] openAccountDetail:', err);
            Toast.show('Load error: ' + err.message, 'error');
        }
    }

    // ─── Test Connection ──────────────────────────────────────
    async function testConnection(smtp) {
        const ok = await Modal.confirm('TEST CONNECTION', `Test connection for ${smtp}?`);
        if (!ok) return;

        showProgress();
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = '接続テスト中...';

        try {
            const r = await Api.test_connection({ smtp: smtp });
            hideProgress();
            if (r.success) {
                Modal.alert('✅ CONNECTION TEST',
                    `Connection to ${smtp} successful!\n\nResponse time: ${r.response_time || '?'} ms`);
            } else {
                Modal.alert('❌ CONNECTION FAILED',
                    `Could not connect to ${smtp}.\n\nError: ${escapeHtml(r.error || 'Unknown error')}`);
            }
        } catch (err) {
            hideProgress();
            console.error('[SettingsPage] testConnection:', err);
            Toast.show('Test error: ' + err.message, 'error');
        }
    }

    // ─── Export Inventory ──────────────────────────────────────
    async function exportSingleAccount(smtp) {
        const ok = await Modal.confirm('EXPORT ACCOUNT', `Export inventory for ${smtp}?`);
        if (!ok) return;

        showProgress();
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = 'エクスポート中...';

        try {
            const r = await Api.export_account_inventory({ smtp: smtp });
            hideProgress();
            if (r.success) {
                Modal.alert('✅ EXPORT COMPLETE',
                    `Account inventory exported to:\n${escapeHtml(r.path || '')}`);
                setStatus('✓ Export complete');
            } else {
                Toast.show('Export failed: ' + (r.error || 'Unknown'), 'error');
            }
        } catch (err) {
            hideProgress();
            console.error('[SettingsPage] exportSingleAccount:', err);
            Toast.show('Export error: ' + err.message, 'error');
        }
    }

    // ─── Progress Overlay ─────────────────────────────────────
    function showProgress() {
        const overlay = document.getElementById('progress-overlay');
        if (overlay) overlay.style.display = 'flex';
    }

    function hideProgress() {
        const overlay = document.getElementById('progress-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    // ─── Helpers ──────────────────────────────────────────────
    function setStatus(msg) {
        const el = document.getElementById('sb-status');
        if (el) el.textContent = '● ' + msg;
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ─── Public API ────────────────────────────────────────────
    return { init, mount, unmount, bindEvents, loadAccountSettings, refreshAccounts };
})();