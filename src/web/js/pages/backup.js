/**
 * backup.js - Backup Page Module
 * UNS Backup App v3.1
 * Pattern: IIFE with init/mount/unmount + Api/State/Polling/Modal/Toast/I18n
 */
const BackupPage = (() => {
    'use strict';

    let container = null;
    let accounts = [];
    let config = {};
    let pollingInterval = null;

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        loadConfig();
        bindEvents();
    }

    function mount() {
        render();
        detectAccounts();
    }

    function unmount() {
        Polling.stop('backup');
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    // ─── Load config ───────────────────────────────────────────
    async function loadConfig() {
        try {
            config = await Api.get_config();
            applyConfigToUI();
        } catch (err) {
            console.error('[BackupPage] loadConfig:', err);
        }
    }

    function applyConfigToUI() {
        const domainEl = document.getElementById('domain-filter');
        if (domainEl && config.domain_filter) domainEl.value = config.domain_filter;

        const outputEl = document.getElementById('output-dir');
        if (outputEl && config.default_backup_dir) outputEl.value = config.default_backup_dir;

        const allAccountsEl = document.getElementById('all-accounts');
        if (allAccountsEl) allAccountsEl.checked = config.backup_all_accounts || false;

        const fmt = config.default_format || 'pst';
        const fmtEl = document.querySelector(`input[name="format"][value="${fmt}"]`);
        if (fmtEl) fmtEl.checked = true;

        // Inventory section
        const invEnabledEl = document.getElementById('inv-enabled');
        if (invEnabledEl) {
            invEnabledEl.checked = config.inventory_enabled || false;
            const opts = document.getElementById('inv-options');
            if (opts) opts.style.display = invEnabledEl.checked ? 'block' : 'none';
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

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        document.getElementById('btn-detect')?.addEventListener('click', detectAccounts);
        document.getElementById('btn-select-domain')?.addEventListener('click', selectDomainOnly);
        document.getElementById('btn-choose-folder')?.addEventListener('click', chooseOutputDir);
        document.getElementById('btn-start-backup')?.addEventListener('click', startBackup);
        document.getElementById('btn-cancel-backup')?.addEventListener('click', cancelBackup);
        document.getElementById('btn-open-folder')?.addEventListener('click', openOutputFolder);

        document.getElementById('all-accounts')?.addEventListener('change', (e) => toggleAllAccounts(e.target.checked));

        document.getElementById('domain-filter')?.addEventListener('change', () => {
            persistConfig({ domain_filter: document.getElementById('domain-filter')?.value || '' });
        });

        document.getElementById('inv-enabled')?.addEventListener('change', (e) => {
            const opts = document.getElementById('inv-options');
            if (opts) opts.style.display = e.target.checked ? 'block' : 'none';
            persistConfig({ inventory_enabled: e.target.checked });
        });

        document.getElementById('inv-passwords')?.addEventListener('change', (e) => {
            const pwdFields = document.getElementById('pwd-fields');
            if (pwdFields) pwdFields.style.display = e.target.checked ? 'block' : 'none';
            if (e.target.checked) warnPasswordExtraction();
            persistConfig({ inventory_include_passwords: e.target.checked });
        });

        document.getElementById('inv-servers')?.addEventListener('change', (e) => {
            persistConfig({ inventory_include_servers: e.target.checked });
        });

        // Fase 6 partial Feature C: filter por fecha
        document.getElementById('date-filter-enabled')?.addEventListener('change', (e) => {
            const fields = document.getElementById('date-filter-fields');
            if (fields) fields.style.display = e.target.checked ? 'flex' : 'none';
        });
    }

    function render() {
        updateStats();
    }

    // ─── Detect Accounts ───────────────────────────────────────
    async function detectAccounts() {
        setStatus('🔍 Detecting accounts...');
        try {
            const r = await Api.detect_accounts();
            if (!r.success) {
                Toast.show('Detection failed: ' + r.error, 'error');
                setStatus('❌ Detection failed');
                return;
            }
            accounts = (r.accounts || []).map(a => ({ ...a, selected: a.matches_domain }));
            renderAccounts();
            updateStats();
            State.set('accounts', accounts);
            setStatus(`✓ Detected ${accounts.length} accounts`);
        } catch (err) {
            console.error('[BackupPage] detectAccounts:', err);
            Toast.show('Detection error: ' + err.message, 'error');
        }
    }

    function renderAccounts() {
        const grid = document.getElementById('account-grid');
        if (!grid) return;

        if (accounts.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:48px;">📭</div>
                    <p>Click "DETECT" to scan Outlook accounts</p>
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
                <div class="account-item ${a.selected ? 'selected' : ''}" data-idx="${i}">
                    <div class="acc-icon" ${colorStyle}>${escapeHtml(initial)}</div>
                    <div class="acc-info">
                        <div class="acc-email">${escapeHtml(a.smtp)}</div>
                        <div class="acc-meta">${escapeHtml(a.type || 'IMAP')} · ${escapeHtml(a.display_name || '')}</div>
                    </div>
                </div>
            `;
        }).join('');

        grid.querySelectorAll('.account-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx, 10);
                accounts[i].selected = !accounts[i].selected;
                el.classList.toggle('selected');
                updateStats();
            });
        });

        // Populate target dropdown for merge mode
        const target = document.getElementById('target-account');
        if (target) {
            target.innerHTML = accounts.map(a =>
                `<option value="${escapeHtml(a.smtp)}">${escapeHtml(a.smtp)}</option>`
            ).join('');
        }
    }

    function selectDomainOnly() {
        const allAccountsEl = document.getElementById('all-accounts');
        if (allAccountsEl) allAccountsEl.checked = false;

        const domain = (document.getElementById('domain-filter')?.value || '').trim().toLowerCase();
        accounts.forEach(a => {
            a.selected = a.smtp.toLowerCase().endsWith('@' + domain);
        });
        renderAccounts();
        updateStats();
    }

    function toggleAllAccounts(checked) {
        if (checked) {
            accounts.forEach(a => { a.selected = true; });
        } else {
            selectDomainOnly();
            return;
        }
        persistConfig({ backup_all_accounts: checked });
        renderAccounts();
        updateStats();
    }

    function updateStats() {
        const detectedEl = document.getElementById('stat-detected');
        if (detectedEl) detectedEl.textContent = accounts.length;

        const selected = accounts.filter(a => a.selected);
        const selectedEl = document.getElementById('stat-selected');
        if (selectedEl) selectedEl.textContent = selected.length;

        const sizeEl = document.getElementById('stat-size');
        const sizeSubEl = document.getElementById('stat-size-sub');
        const infoEl = document.getElementById('sb-info');

        if (selected.length > 0) {
            Api.call('estimate_backup_size', selected.map(a => a.smtp))
                .then(r => {
                    if (r && r.success) {
                        if (sizeEl) sizeEl.textContent = r.estimated_mb >= 1024 ? (r.estimated_mb / 1024).toFixed(1) : r.estimated_mb.toFixed(0);
                        if (sizeSubEl) sizeSubEl.textContent = r.estimated_mb >= 1024 ? 'gigabytes' : 'megabytes';
                        if (infoEl) infoEl.textContent = `${r.total_emails.toLocaleString()} emails · ~${(r.estimated_mb / 1024).toFixed(1)} GB`;
                    }
                })
                .catch(() => {});
        } else {
            if (sizeEl) sizeEl.textContent = '0';
            if (infoEl) infoEl.textContent = '';
        }
    }

    // ─── Folder Selection ──────────────────────────────────────
    async function chooseOutputDir() {
        const f = await Api.select_folder();
        if (f) {
            const el = document.getElementById('output-dir');
            if (el) el.value = f;
            await persistConfig({ default_backup_dir: f });
        }
    }

    async function openOutputFolder() {
        const path = document.getElementById('output-dir')?.value;
        if (path) Api.call('open_backup_folder', path).catch(() => {});
    }

    // ─── Backup ───────────────────────────────────────────────
    async function startBackup() {
        const selected = accounts.filter(a => a.selected);
        if (selected.length === 0) {
            Toast.show('Select at least one account', 'warning');
            return;
        }
        const outputDir = document.getElementById('output-dir')?.value;
        if (!outputDir) {
            Toast.show('Choose an output folder', 'warning');
            return;
        }
        const fmtEl = document.querySelector('input[name="format"]:checked');
        const fmt = fmtEl ? fmtEl.value : 'pst';

        // Fase 6 partial Feature C: filter por fecha (opcional, ISO 8601)
        const dateFilterEnabled = document.getElementById('date-filter-enabled')?.checked || false;
        const dateFrom = dateFilterEnabled ? (document.getElementById('date-from')?.value || null) : null;
        const dateTo = dateFilterEnabled ? (document.getElementById('date-to')?.value || null) : null;
        if (dateFilterEnabled && !dateFrom && !dateTo) {
            Toast.show('日付範囲フィルタが有効ですが、開始日も終了日も未指定です', 'warning');
            return;
        }

        // Feature A plan v3.2: backup incremental
        const incremental = document.getElementById('incremental-enabled')?.checked || false;
        if (incremental && dateFilterEnabled && dateFrom) {
            Toast.show('日付フィルタと差分モードは同時に使えません', 'warning');
            return;
        }

        const invEnabled = document.getElementById('inv-enabled')?.checked || false;
        const invServers = document.getElementById('inv-servers')?.checked !== false;
        const invPasswords = document.getElementById('inv-passwords')?.checked || false;

        let masterPwd = null;
        if (invEnabled && invPasswords) {
            const p1 = document.getElementById('master-pwd')?.value || '';
            const p2 = document.getElementById('master-pwd2')?.value || '';
            if (!p1) { Toast.show('Enter master password', 'warning'); return; }
            if (p1 !== p2) { Toast.show('Passwords do not match', 'warning'); return; }
            if (p1.length < 8) { Toast.show('Password must be 8+ chars', 'warning'); return; }
            masterPwd = p1;
        }

        const ok = await Modal.confirm(
            'CONFIRM BACKUP',
            `${selected.length} accounts will be backed up to:\n${outputDir}\n\nProceed?`
        );
        if (!ok) return;

        showProgress();
        try {
            const r = await Api.start_backup({
                output_dir: outputDir,
                accounts: selected.map(a => a.smtp),
                format: fmt,
                export_inventory: invEnabled,
                inv_servers: invServers,
                inv_passwords: invPasswords,
                master_password: masterPwd,
                date_from: dateFrom,
                date_to: dateTo,
                incremental: incremental,
            });
            if (!r.success) {
                hideProgress();
                Toast.show('Failed to start: ' + r.error, 'error');
                return;
            }
            document.getElementById('btn-start-backup').disabled = true;
            document.getElementById('btn-cancel-backup').disabled = false;
            startBackupPolling();
        } catch (err) {
            hideProgress();
            Toast.show('Start backup error: ' + err.message, 'error');
        }
    }

    function startBackupPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = setInterval(async () => {
            try {
                const p = await Api.get_backup_progress();
                updateBackupUI(p);
                if (p.state === 'success' || p.state === 'failed') {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                    onBackupDone(p);
                }
            } catch (err) {
                console.error('[BackupPage] polling:', err);
            }
        }, 500);
    }

    function updateBackupUI(p) {
        const logEl = document.getElementById('backup-log');
        if (logEl && p.log) {
            logEl.innerHTML = p.log.map(l => {
                const t = new Date(l.ts).toLocaleTimeString();
                let cls = 'log-line';
                if (l.msg.includes('✅')) cls += ' ok';
                else if (l.msg.includes('❌')) cls += ' err';
                else if (l.msg.includes('🚀') || l.msg.includes('📡')) cls += ' info';
                return `<div class="${cls}"><span class="ts">[${t}]</span>${escapeHtml(l.msg)}</div>`;
            }).join('');
            logEl.scrollTop = logEl.scrollHeight;
            const logSection = document.getElementById('backup-log-section');
            if (logSection) logSection.style.display = 'block';
        }

        const lastMsg = p.log && p.log.length > 0 ? p.log[p.log.length - 1].msg : '';
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = lastMsg.substring(0, 80);

        const match = lastMsg.match(/\[(\d+)\/(\d+)\]/);
        if (match) {
            const cur = parseInt(match[1], 10), total = parseInt(match[2], 10);
            const pct = total > 0 ? Math.round(cur / total * 100) : 0;
            const pctEl = document.getElementById('progress-percent');
            const fillEl = document.getElementById('progress-fill');
            const subEl = document.getElementById('progress-substatus');
            if (pctEl) pctEl.textContent = pct + '%';
            if (fillEl) fillEl.style.width = pct + '%';
            if (subEl) subEl.textContent = `${cur} / ${total}`;
        }
    }

    function onBackupDone(p) {
        hideProgress();
        document.getElementById('btn-start-backup').disabled = false;
        document.getElementById('btn-cancel-backup').disabled = true;

        if (p.state === 'success') {
            Modal.alert('✅ BACKUP COMPLETE', `Backup completed successfully!\n\nLocation: ${p.result}`);
            setStatus('✓ Backup complete');
        } else {
            Modal.alert('❌ BACKUP FAILED', String(p.result || 'Unknown error'));
            setStatus('❌ Backup failed');
        }
    }

    async function cancelBackup() {
        const ok = await Modal.confirm('Cancel?', 'Abort current backup operation?');
        if (!ok) return;
        await Api.cancel_backup();
    }

    // ─── Progress Overlay ─────────────────────────────────────
    function showProgress() {
        const overlay = document.getElementById('progress-overlay');
        if (overlay) overlay.style.display = 'flex';
        const fill = document.getElementById('progress-fill');
        if (fill) fill.style.width = '0%';
        const pctEl = document.getElementById('progress-percent');
        if (pctEl) pctEl.textContent = '0%';
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = '準備中...';
        const subEl = document.getElementById('progress-substatus');
        if (subEl) subEl.textContent = '';
    }

    function hideProgress() {
        const overlay = document.getElementById('progress-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    // ─── Persist Config ────────────────────────────────────────
    async function persistConfig(updates) {
        try {
            await Api.update_config(updates);
            Object.assign(config, updates);
        } catch (err) {
            console.error('[BackupPage] persistConfig:', err);
        }
    }

    // ─── Helpers ──────────────────────────────────────────────
    function setStatus(msg) {
        const el = document.getElementById('sb-status');
        if (el) el.textContent = '● ' + msg;
    }

    function warnPasswordExtraction() {
        Modal.alert(
            '⚠️ PASSWORD EXTRACTION',
            'This will attempt to extract Outlook passwords.\n\n' +
            '【WARNING】\n' +
            '• Old HostBig passwords won\'t work after Xserver migration\n' +
            '• Passwords will be encrypted with AES-256-GCM\n' +
            '• Master password is REQUIRED for decryption\n' +
            '• If lost, recovery is IMPOSSIBLE\n' +
            '• File leak = all accounts compromised\n\n' +
            'Continue?'
        );
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ─── Public API ────────────────────────────────────────────
    return { init, mount, unmount, bindEvents, render };
})();