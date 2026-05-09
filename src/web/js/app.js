/* ============================================================
   UNS Backup v3.0 - Frontend Logic
   Bridge to Python via window.pywebview.api
   ============================================================ */

const App = {
    accounts: [],         // [{smtp, display_name, type, selected}]
    psts: [],             // [{path, filename, account, size_mb, created, selected}]
    cacheFiles: [],       // [{path, filename, extension, size_mb, account_smtp, selected}]
    config: {},
    currentTab: 'backup',
    backupPolling: null,
    importPolling: null,

    // Wait for pywebview to be ready
    async init() {
        // pywebview.api may not be ready immediately
        if (!window.pywebview || !window.pywebview.api) {
            await new Promise(resolve => {
                const check = setInterval(() => {
                    if (window.pywebview && window.pywebview.api) {
                        clearInterval(check);
                        resolve();
                    }
                }, 50);
            });
        }
        this.api = window.pywebview.api;

        this.bindUI();
        this.bindTools();
        await this.initTools();
        await this.loadConfig();
        this.startConnect();
    },

    // ===== Connect to Outlook =====
    async startConnect() {
        this.setStatus('📡 Connecting to Outlook...');
        try {
            const r = await this.api.connect_outlook();
            if (r.success) {
                this.setConnection(true);
                this.setStatus('✓ Connected to Outlook');
                await this.detectAccounts();
            } else {
                this.setConnection(false);
                this.setStatus('❌ ' + (r.error || 'Connection failed'));
                this.showToast('Outlook connection failed: ' + r.error, 'error');
            }
        } catch (e) {
            this.setConnection(false);
            this.setStatus('❌ Bridge error');
            console.error(e);
        }
    },

    setConnection(online) {
        const badge = document.getElementById('connection-status');
        const text = badge.querySelector('.conn-text');
        if (online) {
            badge.classList.remove('offline');
            badge.classList.add('online');
            text.textContent = 'OUTLOOK ONLINE';
        } else {
            badge.classList.remove('online');
            badge.classList.add('offline');
            text.textContent = 'OFFLINE';
        }
    },

    setStatus(msg) {
        document.getElementById('sb-status').textContent = '● ' + msg;
    },

    // ===== UI Bindings =====
    bindUI() {
        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Backup tab
        document.getElementById('btn-detect').addEventListener('click', () => this.detectAccounts());
        document.getElementById('btn-select-domain').addEventListener('click', () => this.selectDomainOnly());
        document.getElementById('btn-choose-folder').addEventListener('click', () => this.chooseOutputDir());
        document.getElementById('btn-start-backup').addEventListener('click', () => this.startBackup());
        document.getElementById('btn-cancel-backup').addEventListener('click', () => this.cancelBackup());
        document.getElementById('btn-open-folder').addEventListener('click', () => this.openOutputFolder());
        document.getElementById('all-accounts').addEventListener('change', (e) => this.toggleAllAccounts(e.target.checked));
        document.getElementById('domain-filter').addEventListener('change', () => this.persistConfig({domain_filter: document.getElementById('domain-filter').value}));

        // Inventory section
        document.getElementById('inv-enabled').addEventListener('change', (e) => {
            document.getElementById('inv-options').style.display = e.target.checked ? 'block' : 'none';
            this.persistConfig({inventory_enabled: e.target.checked});
        });
        document.getElementById('inv-passwords').addEventListener('change', (e) => {
            document.getElementById('pwd-fields').style.display = e.target.checked ? 'block' : 'none';
            if (e.target.checked) this.warnPasswordExtraction();
            this.persistConfig({inventory_include_passwords: e.target.checked});
        });
        document.getElementById('inv-servers').addEventListener('change', (e) => {
            this.persistConfig({inventory_include_servers: e.target.checked});
        });

        // Restore tab
        document.getElementById('btn-restore-browse').addEventListener('click', () => this.chooseRestoreFolder());
        document.getElementById('btn-restore-search').addEventListener('click', () => this.searchPSTs());
        document.getElementById('btn-start-import').addEventListener('click', () => this.startImport());
        document.getElementById('btn-preview-pst').addEventListener('click', () => this.previewPST());
        document.querySelectorAll('input[name="import-method"]').forEach(r => {
            r.addEventListener('change', (e) => this.onMethodChange(e.target.value));
        });

        // History tab
        document.getElementById('btn-refresh-history').addEventListener('click', () => this.loadHistory());

        // Auto/Schedule tab
        document.getElementById('btn-save-schedule').addEventListener('click', () => this.saveSchedule());
        document.getElementById('btn-test-schedule').addEventListener('click', () => this.testSchedule());
        document.getElementById('btn-remove-schedule').addEventListener('click', () => this.removeSchedule());
        document.getElementById('btn-auto-folder').addEventListener('click', () => this.chooseAutoFolder());
        document.querySelectorAll('input[name="auto-freq"]').forEach(r => {
            r.addEventListener('change', () => this.onFreqChange());
        });

        // Progress overlay
        document.getElementById('btn-progress-cancel').addEventListener('click', () => this.cancelBackup());

        // CACHE tab (v3.1)
        document.getElementById('btn-cache-scan').addEventListener('click', () => this.scanCache());
        document.getElementById('btn-cache-folder').addEventListener('click', () => this.chooseCacheFolder());
        document.getElementById('btn-cache-backup').addEventListener('click', () => this.startCacheBackup());
        document.getElementById('btn-cache-cancel').addEventListener('click', () => this.cancelBackup());
    },

    switchTab(tabName) {
        document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.toggle('active', c.dataset.tabContent === tabName));
        this.currentTab = tabName;

        if (tabName === 'history') this.loadHistory();
        if (tabName === 'auto') this.loadScheduleStatus();
    },

    // ===== Config persistence =====
    async loadConfig() {
        const cfg = await this.api.get_config();
        this.config = cfg;
        document.getElementById('domain-filter').value = cfg.domain_filter || 'uns-kikaku.com';
        document.getElementById('output-dir').value = cfg.default_backup_dir || '';
        document.getElementById('restore-folder').value = cfg.default_backup_dir || '';
        document.getElementById('auto-savepath').value = cfg.schedule_save_to || cfg.default_backup_dir || '';
        document.getElementById('cache-output-dir').value = cfg.default_backup_dir || '';
        document.getElementById('all-accounts').checked = cfg.backup_all_accounts || false;
        document.getElementById('inv-enabled').checked = cfg.inventory_enabled || false;
        document.getElementById('inv-options').style.display = cfg.inventory_enabled ? 'block' : 'none';
        document.getElementById('inv-servers').checked = cfg.inventory_include_servers !== false;
        document.getElementById('inv-passwords').checked = cfg.inventory_include_passwords || false;
        document.getElementById('pwd-fields').style.display = cfg.inventory_include_passwords ? 'block' : 'none';
        // format
        const fmt = cfg.default_format || 'pst';
        document.querySelector(`input[name="format"][value="${fmt}"]`).checked = true;
        // Default import method
        const im = cfg.default_import_mode || 'separate_folder';
        document.querySelector(`input[name="import-method"][value="${im}"]`).checked = true;
        document.querySelectorAll('.method-card').forEach(c => c.classList.toggle('selected', c.dataset.method === im));

        // Auto schedule
        const f = cfg.schedule_frequency || 'weekly';
        document.querySelector(`input[name="auto-freq"][value="${f}"]`).checked = true;
        const d = cfg.schedule_day_of_week || 'MON';
        document.querySelector(`input[name="auto-day"][value="${d}"]`).checked = true;
        document.getElementById('auto-enabled').checked = cfg.schedule_enabled || false;
        document.getElementById('custom-days').value = cfg.schedule_custom_days || 7;
        const time = (cfg.schedule_time || '02:00').split(':');
        document.getElementById('auto-hour').value = parseInt(time[0]);
        document.getElementById('auto-minute').value = parseInt(time[1] || 0);
        document.getElementById('keep-last').value = cfg.schedule_keep_last !== undefined ? cfg.schedule_keep_last : 4;
        const sc = cfg.schedule_scope || 'uns_only';
        document.querySelector(`input[name="auto-scope"][value="${sc}"]`).checked = true;
        this.onFreqChange();
    },

    async persistConfig(updates) {
        await this.api.update_config(updates);
        Object.assign(this.config, updates);
    },

    // ===== Account detection & selection =====
    async detectAccounts() {
        this.setStatus('🔍 Detecting accounts...');
        const r = await this.api.detect_accounts();
        if (!r.success) {
            this.showToast('Detection failed: ' + r.error, 'error');
            return;
        }
        this.accounts = r.accounts.map(a => ({
            ...a, selected: a.matches_domain
        }));
        this.renderAccounts();
        this.updateStats();
        this.setStatus(`✓ Detected ${this.accounts.length} accounts`);
    },

    renderAccounts() {
        const grid = document.getElementById('account-grid');
        if (this.accounts.length === 0) {
            grid.innerHTML = `<div class="empty-state"><div style="font-size:48px;">📭</div><p>No accounts found</p></div>`;
            return;
        }
        grid.innerHTML = this.accounts.map((a, i) => {
            const initial = a.smtp.charAt(0).toUpperCase();
            const colorClass = a.smtp.startsWith('info') ? 'style="background: linear-gradient(135deg, #ff3838, #b91c1c);"' : '';
            return `
                <div class="account-item ${a.selected ? 'selected' : ''}" data-idx="${i}">
                    <div class="acc-icon" ${colorClass}>${this.escape(initial)}</div>
                    <div class="acc-info">
                        <div class="acc-email">${this.escape(a.smtp)}</div>
                        <div class="acc-meta">${this.escape(a.type || 'IMAP')} · ${this.escape(a.display_name || '')}</div>
                    </div>
                </div>
            `;
        }).join('');
        grid.querySelectorAll('.account-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx);
                this.accounts[i].selected = !this.accounts[i].selected;
                el.classList.toggle('selected');
                this.updateStats();
            });
        });

        // Populate target dropdown for merge mode
        const target = document.getElementById('target-account');
        if (target) {
            target.innerHTML = this.accounts.map(a => `<option value="${a.smtp}">${a.smtp}</option>`).join('');
        }
    },

    selectDomainOnly() {
        document.getElementById('all-accounts').checked = false;
        const domain = document.getElementById('domain-filter').value.trim().toLowerCase();
        this.accounts.forEach(a => {
            a.selected = a.smtp.toLowerCase().endsWith('@' + domain);
        });
        this.renderAccounts();
        this.updateStats();
    },

    toggleAllAccounts(checked) {
        if (checked) {
            this.accounts.forEach(a => a.selected = true);
        } else {
            this.selectDomainOnly();
        }
        this.persistConfig({backup_all_accounts: checked});
        this.renderAccounts();
        this.updateStats();
    },

    updateStats() {
        document.getElementById('stat-detected').textContent = this.accounts.length;
        const selected = this.accounts.filter(a => a.selected).length;
        document.getElementById('stat-selected').textContent = selected;

        // Estimate size async
        if (selected > 0 && this.api) {
            this.api.estimate_backup_size(this.accounts.filter(a => a.selected).map(a => a.smtp))
                .then(r => {
                    if (r.success) {
                        document.getElementById('stat-size').textContent = r.estimated_mb >= 1024 ? (r.estimated_mb/1024).toFixed(1) : r.estimated_mb.toFixed(0);
                        document.getElementById('stat-size-sub').textContent = r.estimated_mb >= 1024 ? 'gigabytes' : 'megabytes';
                        document.getElementById('sb-info').textContent = `${r.total_emails.toLocaleString()} emails · ~${(r.estimated_mb/1024).toFixed(1)} GB`;
                    }
                }).catch(() => {});
        } else {
            document.getElementById('stat-size').textContent = '0';
            document.getElementById('sb-info').textContent = '';
        }
    },

    // ===== Choose folders =====
    async chooseOutputDir() {
        const f = await this.api.choose_folder(this.config.default_backup_dir);
        if (f) {
            document.getElementById('output-dir').value = f;
            await this.persistConfig({default_backup_dir: f});
        }
    },
    async chooseRestoreFolder() {
        const f = await this.api.choose_folder();
        if (f) document.getElementById('restore-folder').value = f;
    },
    async chooseAutoFolder() {
        const f = await this.api.choose_folder();
        if (f) document.getElementById('auto-savepath').value = f;
    },
    async openOutputFolder() {
        const path = document.getElementById('output-dir').value;
        if (path) await this.api.open_path(path);
    },

    // ===== Backup =====
    async startBackup() {
        const selected = this.accounts.filter(a => a.selected);
        if (selected.length === 0) {
            this.showToast('Select at least one account', 'warning');
            return;
        }
        const outputDir = document.getElementById('output-dir').value;
        if (!outputDir) {
            this.showToast('Choose an output folder', 'warning');
            return;
        }

        const fmt = document.querySelector('input[name="format"]:checked').value;
        const invEnabled = document.getElementById('inv-enabled').checked;
        const invServers = document.getElementById('inv-servers').checked;
        const invPasswords = document.getElementById('inv-passwords').checked;

        let masterPwd = null;
        if (invEnabled && invPasswords) {
            const p1 = document.getElementById('master-pwd').value;
            const p2 = document.getElementById('master-pwd2').value;
            if (!p1) { this.showToast('Enter master password', 'warning'); return; }
            if (p1 !== p2) { this.showToast('Passwords do not match', 'warning'); return; }
            if (p1.length < 8) { this.showToast('Password must be 8+ chars', 'warning'); return; }
            masterPwd = p1;
        }

        const ok = await this.confirm('CONFIRM BACKUP',
            `${selected.length} accounts will be backed up to:\n${outputDir}\n\nProceed?`);
        if (!ok) return;

        this.showProgress();

        const r = await this.api.start_backup({
            output_dir: outputDir,
            accounts: selected.map(a => a.smtp),
            format: fmt,
            export_inventory: invEnabled,
            inv_servers: invServers,
            inv_passwords: invPasswords,
            master_password: masterPwd,
        });

        if (!r.success) {
            this.hideProgress();
            this.showToast('Failed to start: ' + r.error, 'error');
            return;
        }

        document.getElementById('btn-start-backup').disabled = true;
        document.getElementById('btn-cancel-backup').disabled = false;
        this.startBackupPolling();
    },

    startBackupPolling() {
        if (this.backupPolling) clearInterval(this.backupPolling);
        this.backupPolling = setInterval(async () => {
            const p = await this.api.get_backup_progress();
            this.updateBackupUI(p);
            if (p.state === 'success' || p.state === 'failed') {
                clearInterval(this.backupPolling);
                this.backupPolling = null;
                this.onBackupDone(p);
            }
        }, 500);
    },

    updateBackupUI(p) {
        // Update log
        const logEl = document.getElementById('backup-log');
        if (logEl) {
            logEl.innerHTML = p.log.map(l => {
                const t = new Date(l.ts).toLocaleTimeString();
                let cls = 'log-line';
                if (l.msg.includes('✅')) cls += ' ok';
                else if (l.msg.includes('❌')) cls += ' err';
                else if (l.msg.includes('🚀') || l.msg.includes('📡')) cls += ' info';
                return `<div class="${cls}"><span class="ts">[${t}]</span>${this.escape(l.msg)}</div>`;
            }).join('');
            logEl.scrollTop = logEl.scrollHeight;
            document.getElementById('backup-log-section').style.display = 'block';
        }

        // Estimate progress percent from log content
        const lastMsg = p.log.length > 0 ? p.log[p.log.length - 1].msg : '';
        document.getElementById('progress-status').textContent = lastMsg.substring(0, 80);

        // Try to extract percent from log
        const match = lastMsg.match(/(\d+)\/(\d+)/);
        if (match) {
            const cur = parseInt(match[1]), total = parseInt(match[2]);
            const pct = total > 0 ? Math.round(cur / total * 100) : 0;
            document.getElementById('progress-percent').textContent = pct + '%';
            document.getElementById('progress-fill').style.width = pct + '%';
            document.getElementById('progress-substatus').textContent = `${cur} / ${total}`;
        }
    },

    onBackupDone(p) {
        this.hideProgress();
        document.getElementById('btn-start-backup').disabled = false;
        document.getElementById('btn-cancel-backup').disabled = true;

        if (p.state === 'success') {
            this.alert('✅ BACKUP COMPLETE',
                `Backup completed successfully!\n\nLocation: ${p.result}`);
            this.setStatus('✓ Backup complete');
        } else {
            this.alert('❌ BACKUP FAILED', String(p.result || 'Unknown error'));
            this.setStatus('❌ Backup failed');
        }
    },

    async cancelBackup() {
        if (!await this.confirm('Cancel?', 'Abort current backup operation?')) return;
        await this.api.cancel_backup();
    },

    showProgress() {
        document.getElementById('progress-overlay').style.display = 'flex';
        document.getElementById('progress-fill').style.width = '0%';
        document.getElementById('progress-percent').textContent = '0%';
        document.getElementById('progress-status').textContent = '準備中...';
        document.getElementById('progress-substatus').textContent = '';
    },
    hideProgress() {
        document.getElementById('progress-overlay').style.display = 'none';
    },

    // ===== Restore =====
    async searchPSTs() {
        const folder = document.getElementById('restore-folder').value;
        if (!folder) { this.showToast('Choose a folder first', 'warning'); return; }

        this.setStatus('🔍 Searching for PSTs...');
        const r = await this.api.search_pst_files(folder);
        if (!r.success) { this.showToast('Search failed: ' + r.error, 'error'); return; }

        this.psts = r.files.map(f => ({...f, selected: true}));
        this.renderPSTs();
        this.setStatus(`✓ Found ${this.psts.length} PST files`);
    },

    renderPSTs() {
        const list = document.getElementById('pst-list');
        if (this.psts.length === 0) {
            list.innerHTML = `<div class="empty-state"><div style="font-size:48px;">📂</div><p>No PSTs found</p></div>`;
            return;
        }
        list.innerHTML = this.psts.map((p, i) => `
            <div class="pst-item ${p.selected ? 'selected' : ''}" data-idx="${i}">
                <div class="pst-icon">📦</div>
                <div class="pst-info">
                    <div class="pst-name">${this.escape(p.filename)}</div>
                    <div class="pst-meta">${this.escape(p.account || '—')} · ${this.escape(p.created)}</div>
                </div>
                <div class="pst-size">${p.size_mb} MB</div>
            </div>
        `).join('');
        list.querySelectorAll('.pst-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx);
                this.psts[i].selected = !this.psts[i].selected;
                el.classList.toggle('selected');
            });
        });
    },

    onMethodChange(method) {
        document.querySelectorAll('.method-card').forEach(c => c.classList.toggle('selected', c.dataset.method === method));
        const merge = document.querySelector('.method-card[data-method="merge"] .merge-target');
        if (merge) merge.style.display = method === 'merge' ? 'flex' : 'none';
        this.persistConfig({default_import_mode: method});
    },

    async startImport() {
        const selected = this.psts.filter(p => p.selected);
        if (selected.length === 0) { this.showToast('Select at least one PST', 'warning'); return; }

        const method = document.querySelector('input[name="import-method"]:checked').value;
        const target = method === 'merge' ? document.getElementById('target-account').value : null;
        if (method === 'merge' && !target) {
            this.showToast('Choose target account for merge', 'warning');
            return;
        }

        const ok = await this.confirm('CONFIRM IMPORT',
            `${selected.length} PST file(s) will be imported.\nMethod: ${method}\n\nProceed?`);
        if (!ok) return;

        const r = await this.api.start_import({
            files: selected.map(p => p.path),
            mode: method,
            target_smtp: target,
        });
        if (!r.success) { this.showToast('Failed: ' + r.error, 'error'); return; }

        document.getElementById('btn-start-import').disabled = true;
        this.startImportPolling();
    },

    startImportPolling() {
        if (this.importPolling) clearInterval(this.importPolling);
        this.importPolling = setInterval(async () => {
            const p = await this.api.get_import_progress();
            this.updateImportUI(p);
            if (p.state === 'success' || p.state === 'failed') {
                clearInterval(this.importPolling);
                this.importPolling = null;
                this.onImportDone(p);
            }
        }, 500);
    },

    updateImportUI(p) {
        const logEl = document.getElementById('import-log');
        if (logEl) {
            logEl.innerHTML = p.log.map(l => {
                const t = new Date(l.ts).toLocaleTimeString();
                let cls = 'log-line';
                if (l.msg.includes('✅')) cls += ' ok';
                else if (l.msg.includes('❌')) cls += ' err';
                return `<div class="${cls}"><span class="ts">[${t}]</span>${this.escape(l.msg)}</div>`;
            }).join('');
            logEl.scrollTop = logEl.scrollHeight;
            document.getElementById('import-log-section').style.display = 'block';
        }
    },

    onImportDone(p) {
        document.getElementById('btn-start-import').disabled = false;
        if (p.state === 'success') {
            const r = p.result || {};
            this.alert('✅ IMPORT COMPLETE',
                `${r.ok_count}/${r.total} PSTs imported successfully.\nCheck your Outlook.`);
        } else {
            this.alert('❌ IMPORT FAILED', String(p.result || ''));
        }
    },

    async previewPST() {
        const sel = this.psts.find(p => p.selected);
        if (!sel) { this.showToast('Select a PST first', 'warning'); return; }
        this.setStatus('🔍 Previewing PST...');
        const r = await this.api.preview_pst(sel.path);
        if (!r.success) { this.showToast('Preview failed: ' + r.error, 'error'); return; }
        const i = r.info;
        let body = `${i.filename}\n\n`;
        body += `Size: ${i.size_mb} MB\n`;
        body += `Total emails: ${(i.total_emails || 0).toLocaleString()}\n`;
        body += `Folders: ${i.total_folders || 0}\n\n`;
        if (i.folders) {
            body += '📁 Folders:\n';
            i.folders.slice(0, 20).forEach(f => {
                body += `${'  '.repeat(f.depth)}${f.name}: ${f.count.toLocaleString()}\n`;
            });
        }
        this.alert('🔍 PST PREVIEW', body);
    },

    // ===== History =====
    async loadHistory() {
        const r = await this.api.list_history();
        const list = document.getElementById('history-list');
        if (!r.success || !r.backups || r.backups.length === 0) {
            list.innerHTML = `<div class="empty-state"><div style="font-size:48px;">📭</div><p>No backup history</p></div>`;
            return;
        }
        list.innerHTML = r.backups.map(b => {
            const icon = {success:'✅', partial:'⚠️', failed:'❌', incomplete:'⚪'}[b.status] || '❓';
            const date = b.start_time ? new Date(b.start_time).toLocaleString() : '';
            return `
                <div class="history-item" data-path="${this.escape(b.path)}">
                    <div class="h-status">${icon}</div>
                    <div class="h-info">
                        <div class="h-date">${this.escape(date)}</div>
                        <div class="h-name">${this.escape(b.name)}</div>
                    </div>
                    <div class="h-stat"><strong>${b.accounts_count || 0}</strong>accounts</div>
                    <div class="h-stat"><strong>${(b.total_emails || 0).toLocaleString()}</strong>emails</div>
                    <div class="h-stat"><strong>${(b.total_size_mb || 0).toFixed(1)}</strong>MB</div>
                    <div class="h-actions">
                        <button class="btn btn-secondary" onclick="App.openHistoryFolder('${this.escape(b.path)}')">📂</button>
                        <button class="btn btn-danger" onclick="App.deleteHistory('${this.escape(b.path)}')">🗑️</button>
                    </div>
                </div>
            `;
        }).join('');
    },

    async openHistoryFolder(path) {
        await this.api.open_path(path);
    },
    async deleteHistory(path) {
        if (!await this.confirm('DELETE BACKUP', `Permanently delete?\n\n${path}`)) return;
        const r = await this.api.delete_history(path);
        if (r.success) { this.loadHistory(); this.showToast('Deleted', 'success'); }
        else this.showToast('Delete failed: ' + r.error, 'error');
    },

    // ===== Schedule =====
    async loadScheduleStatus() {
        const r = await this.api.get_schedule_info();
        const banner = document.getElementById('auto-status-banner');
        const detail = document.getElementById('auto-status-detail');
        if (r.active) {
            banner.classList.remove('inactive');
            banner.classList.add('active');
            banner.querySelector('strong').textContent = '✅ AUTO BACKUP ACTIVE';
            if (r.info) {
                detail.innerHTML = `Next run: ${this.escape(r.info.next_run || '?')}<br>Last run: ${this.escape(r.info.last_run || 'Never')}`;
            }
        } else {
            banner.classList.remove('active');
            banner.classList.add('inactive');
            banner.querySelector('strong').textContent = '⏸️ AUTO BACKUP DISABLED';
            detail.textContent = '';
        }
    },

    onFreqChange() {
        const f = document.querySelector('input[name="auto-freq"]:checked').value;
        document.getElementById('day-row').style.display = (f === 'weekly' || f === 'biweekly') ? 'flex' : 'none';
        document.getElementById('custom-row').style.display = f === 'custom' ? 'flex' : 'none';
    },

    async saveSchedule() {
        if (!document.getElementById('auto-enabled').checked) {
            this.showToast('Enable auto backup first', 'warning');
            return;
        }
        const params = {
            frequency: document.querySelector('input[name="auto-freq"]:checked').value,
            day_of_week: document.querySelector('input[name="auto-day"]:checked').value,
            time: `${String(document.getElementById('auto-hour').value).padStart(2,'0')}:${String(document.getElementById('auto-minute').value).padStart(2,'0')}`,
            custom_days: parseInt(document.getElementById('custom-days').value),
            save_to: document.getElementById('auto-savepath').value,
            scope: document.querySelector('input[name="auto-scope"]:checked').value,
            keep_last: parseInt(document.getElementById('keep-last').value),
        };
        const r = await this.api.save_schedule(params);
        if (r.success) {
            this.alert('✅ SCHEDULE SAVED', `Auto backup will run at ${params.time}.`);
            this.loadScheduleStatus();
        } else {
            this.showToast('Save failed: ' + (r.error || 'Unknown'), 'error');
        }
    },

    async removeSchedule() {
        if (!await this.confirm('REMOVE SCHEDULE', 'Delete the scheduled task?')) return;
        const r = await this.api.remove_schedule();
        if (r.success) { this.loadScheduleStatus(); this.showToast('Removed', 'success'); }
        else this.showToast('Remove failed', 'error');
    },

    async testSchedule() {
        const r = await this.api.test_schedule_now();
        if (r.success) this.showToast('Test executed', 'success');
        else this.showToast('Test failed: ' + (r.error || ''), 'error');
    },

    // ===== Modals & toasts =====
    confirm(title, body) {
        return new Promise(resolve => {
            this.showModal(title, body, [
                {text: 'CANCEL', class: 'btn-secondary', action: () => resolve(false)},
                {text: 'OK', class: 'btn-primary', action: () => resolve(true)},
            ]);
        });
    },
    alert(title, body) {
        return new Promise(resolve => {
            this.showModal(title, body, [{text: 'OK', class: 'btn-primary', action: () => resolve()}]);
        });
    },
    showModal(title, body, actions) {
        document.getElementById('modal-header').textContent = title;
        document.getElementById('modal-body').textContent = body;
        const ac = document.getElementById('modal-actions');
        ac.innerHTML = '';
        actions.forEach(a => {
            const btn = document.createElement('button');
            btn.className = 'btn ' + a.class;
            btn.textContent = a.text;
            btn.onclick = () => {
                this.hideModal();
                a.action && a.action();
            };
            ac.appendChild(btn);
        });
        document.getElementById('modal-overlay').style.display = 'block';
        document.getElementById('modal').style.display = 'block';
    },
    hideModal() {
        document.getElementById('modal-overlay').style.display = 'none';
        document.getElementById('modal').style.display = 'none';
    },

    showToast(msg, type) {
        // Simple status message for now
        this.setStatus(msg);
    },

    warnPasswordExtraction() {
        this.alert('⚠️ PASSWORD EXTRACTION',
`This will attempt to extract Outlook passwords.

【WARNING】
• Old HostBig passwords won't work after Xserver migration
• Passwords will be encrypted with AES-256-GCM
• Master password is REQUIRED for decryption
• If lost, recovery is IMPOSSIBLE
• File leak = all accounts compromised

Continue?`);
    },

    // ===== CACHE BACKUP (v3.1 - works offline) =====
    async scanCache() {
        this.setStatus('🔍 Scanning Outlook cache...');
        const r = await this.api.scan_cache_files();
        if (!r.success) {
            this.showToast('Scan failed: ' + r.error, 'error');
            return;
        }
        this.cacheFiles = (r.files || []).map(f => ({...f, selected: true}));
        this.renderCacheList();
        this.updateCacheStats();
        this.setStatus(`✓ Found ${this.cacheFiles.length} cache file(s)`);
    },

    renderCacheList() {
        const list = document.getElementById('cache-list');
        if (this.cacheFiles.length === 0) {
            list.innerHTML = `<div class="empty-state"><div style="font-size:48px;">💾</div><p>No cache files found</p><p style="font-size:10px; margin-top: 4px;">Outlook may not be installed or configured</p></div>`;
            return;
        }
        list.innerHTML = this.cacheFiles.map((f, i) => {
            const ext = (f.extension || '').replace('.', '').toUpperCase();
            const account = f.account_smtp ? `<div class="cache-account">📧 ${this.escape(f.account_smtp)}</div>` : '';
            return `
                <div class="cache-item ${f.selected ? 'selected' : ''}" data-idx="${i}">
                    <div class="cache-icon">${f.extension === '.ost' ? '🔄' : '📦'}</div>
                    <div class="cache-info">
                        <div class="cache-name">${this.escape(f.filename)}<span class="cache-type ${ext.toLowerCase()}">${ext}</span></div>
                        <div class="cache-meta">📂 ${this.escape(f.path)}</div>
                        ${account}
                        <div class="cache-meta">📅 ${this.escape(f.modified)}</div>
                    </div>
                    <div class="cache-size">${f.size_mb} MB</div>
                </div>
            `;
        }).join('');
        list.querySelectorAll('.cache-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx);
                this.cacheFiles[i].selected = !this.cacheFiles[i].selected;
                el.classList.toggle('selected');
                this.updateCacheStats();
            });
        });
    },

    updateCacheStats() {
        document.getElementById('cache-stat-count').textContent = this.cacheFiles.length;
        const selected = this.cacheFiles.filter(f => f.selected);
        document.getElementById('cache-stat-selected').textContent = selected.length;
        const totalMB = selected.reduce((s, f) => s + f.size_mb, 0);
        if (totalMB >= 1024) {
            document.getElementById('cache-stat-size').textContent = (totalMB / 1024).toFixed(1);
            document.getElementById('cache-stat-size-sub').textContent = 'gigabytes';
        } else {
            document.getElementById('cache-stat-size').textContent = totalMB.toFixed(0);
            document.getElementById('cache-stat-size-sub').textContent = 'megabytes';
        }
    },

    async chooseCacheFolder() {
        const f = await this.api.choose_folder(this.config.default_backup_dir);
        if (f) document.getElementById('cache-output-dir').value = f;
    },

    async startCacheBackup() {
        const selected = this.cacheFiles.filter(f => f.selected);
        if (selected.length === 0) {
            this.showToast('Select at least one cache file', 'warning');
            return;
        }
        const outputDir = document.getElementById('cache-output-dir').value;
        if (!outputDir) {
            this.showToast('Choose output folder', 'warning');
            return;
        }

        const verify = document.getElementById('cache-verify').checked;
        const closeOutlook = document.getElementById('cache-close-outlook').checked;

        let confirmMsg = `${selected.length} cache file(s) will be backed up to:\n${outputDir}`;
        const totalMB = selected.reduce((s, f) => s + f.size_mb, 0);
        confirmMsg += `\n\nTotal size: ${(totalMB/1024).toFixed(2)} GB`;
        if (closeOutlook) {
            confirmMsg += '\n\n⚠️ Outlook will be CLOSED before backup.';
        }
        confirmMsg += '\n\nProceed?';

        const ok = await this.confirm('CONFIRM CACHE BACKUP', confirmMsg);
        if (!ok) return;

        this.showProgress();
        document.getElementById('progress-status').textContent = 'キャッシュバックアップ中...';

        const r = await this.api.start_cache_backup({
            files: selected.map(f => f.path),
            output_dir: outputDir,
            verify_integrity: verify,
            close_outlook: closeOutlook,
        });

        if (!r.success) {
            this.hideProgress();
            this.showToast('Failed to start: ' + r.error, 'error');
            return;
        }

        document.getElementById('btn-cache-backup').disabled = true;
        document.getElementById('btn-cache-cancel').disabled = false;
        this.startCacheBackupPolling();
    },

    startCacheBackupPolling() {
        if (this.backupPolling) clearInterval(this.backupPolling);
        this.backupPolling = setInterval(async () => {
            const p = await this.api.get_backup_progress();
            this.updateCacheBackupUI(p);
            if (p.state === 'success' || p.state === 'failed') {
                clearInterval(this.backupPolling);
                this.backupPolling = null;
                this.onCacheBackupDone(p);
            }
        }, 500);
    },

    updateCacheBackupUI(p) {
        const logEl = document.getElementById('cache-log');
        if (logEl) {
            logEl.innerHTML = p.log.map(l => {
                const t = new Date(l.ts).toLocaleTimeString();
                let cls = 'log-line';
                if (l.msg.includes('✅')) cls += ' ok';
                else if (l.msg.includes('❌')) cls += ' err';
                else if (l.msg.includes('💾') || l.msg.includes('🔐')) cls += ' info';
                return `<div class="${cls}"><span class="ts">[${t}]</span>${this.escape(l.msg)}</div>`;
            }).join('');
            logEl.scrollTop = logEl.scrollHeight;
            document.getElementById('cache-log-section').style.display = 'block';
        }

        const lastMsg = p.log.length > 0 ? p.log[p.log.length - 1].msg : '';
        document.getElementById('progress-status').textContent = lastMsg.substring(0, 80);

        // Estimate: count file completed
        const fileMatch = lastMsg.match(/\[(\d+)\/(\d+)\]/);
        if (fileMatch) {
            const cur = parseInt(fileMatch[1]), total = parseInt(fileMatch[2]);
            const pct = Math.round(cur / total * 100);
            document.getElementById('progress-percent').textContent = pct + '%';
            document.getElementById('progress-fill').style.width = pct + '%';
            document.getElementById('progress-substatus').textContent = `${cur} / ${total} files`;
        }
        // Or progress within a file
        const pctMatch = lastMsg.match(/(\d+)%/);
        if (pctMatch && !fileMatch) {
            const pct = parseInt(pctMatch[1]);
            document.getElementById('progress-fill').style.width = pct + '%';
        }
    },

    onCacheBackupDone(p) {
        this.hideProgress();
        document.getElementById('btn-cache-backup').disabled = false;
        document.getElementById('btn-cache-cancel').disabled = true;

        if (p.state === 'success') {
            this.alert('✅ CACHE BACKUP COMPLETE',
                `Cache backup completed successfully!\n\nLocation: ${p.result}\n\n💡 These OST files are tied to your original Outlook profile.\nIf you need to open them on another PC, use scanpst.exe to convert.`);
            this.setStatus('✓ Cache backup complete');
        } else {
            this.alert('❌ CACHE BACKUP FAILED', String(p.result || 'Unknown error'));
            this.setStatus('❌ Cache backup failed');
        }
    },

    escape(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
        }[c]));
    },

    // ===== TOOLS TAB (RAR Extractor + Script Runner) =====
    rarFiles: [],       // [{path, filename, size_mb, selected}]
    extractedFiles: [],  // archivos extraidos
    toolsPolling: null,

    async initTools() {
        // Check if RAR extraction is available
        const r = await this.api.can_extract_rar();
        if (!r.available) {
            this.showToast('⚠️ RAR extraction unavailable: ' + (r.error || 'unrar/7z not found'), 'warning');
        }
    },

    bindTools() {
        document.getElementById('btn-tools-browse').addEventListener('click', () => this.chooseToolsFolder());
        document.getElementById('btn-tools-scan').addEventListener('click', () => this.scanRarFiles());
        document.getElementById('btn-tools-extract').addEventListener('click', () => this.extractSelectedRar());
        document.getElementById('btn-tools-run').addEventListener('click', () => this.runSelectedScript());
        document.getElementById('btn-tools-open-folder').addEventListener('click', () => this.openToolsFolder());
    },

    async chooseToolsFolder() {
        const f = await this.api.choose_folder();
        if (f) {
            document.getElementById('tools-rar-folder').value = f;
        }
    },

    async scanRarFiles() {
        const folder = document.getElementById('tools-rar-folder').value;
        if (!folder) {
            this.showToast('Choose a folder first', 'warning');
            return;
        }

        this.setStatus('🔍 Scanning for RAR files...');
        const r = await this.api.find_rar_files(folder);
        if (!r.success) {
            this.showToast('Scan failed: ' + r.error, 'error');
            return;
        }

        this.rarFiles = (r.files || []).map(f => ({...f, selected: false}));
        this.renderRarList();
        document.getElementById('tools-stat-rar').textContent = this.rarFiles.length;
        this.setStatus(`✓ Found ${this.rarFiles.length} RAR files`);
    },

    renderRarList() {
        const list = document.getElementById('rar-list');
        if (this.rarFiles.length === 0) {
            list.innerHTML = `<div class="empty-state"><div style="font-size:48px;">📦</div><p>No RAR files found</p></div>`;
            return;
        }
        list.innerHTML = this.rarFiles.map((f, i) => `
            <div class="rar-item ${f.selected ? 'selected' : ''}" data-idx="${i}">
                <div class="rar-icon">📦</div>
                <div class="rar-info">
                    <div class="rar-name">${this.escape(f.filename)}</div>
                    <div class="rar-meta">${this.escape(f.path)}</div>
                </div>
                <div class="rar-size">${f.size_mb} MB</div>
            </div>
        `).join('');
        list.querySelectorAll('.rar-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx);
                this.rarFiles[i].selected = !this.rarFiles[i].selected;
                el.classList.toggle('selected');
            });
        });
    },

    async extractSelectedRar() {
        const selected = this.rarFiles.filter(f => f.selected);
        if (selected.length === 0) {
            this.showToast('Select at least one RAR file', 'warning');
            return;
        }

        const ok = await this.confirm('EXTRACT RAR',
            `${selected.length} RAR file(s) will be extracted.\nExtracted files will be saved to a temp folder.\n\nProceed?`);
        if (!ok) return;

        this.showProgress();
        document.getElementById('progress-status').textContent = 'RAR展開中...';
        this.extractedFiles = [];
        let scriptsFound = [];

        for (const rar of selected) {
            const r = await this.api.extract_rar({rar_path: rar.path});
            if (r.success) {
                this.extractedFiles.push(...(r.files_extracted || []));
                scriptsFound.push(...(r.scripts_found || []));
            }
        }

        this.hideProgress();
        document.getElementById('tools-stat-extracted').textContent = this.extractedFiles.length;
        document.getElementById('tools-stat-scripts').textContent = scriptsFound.length;

        this.alert('✅ EXTRACTION COMPLETE',
            `${this.extractedFiles.length} files extracted.\n${scriptsFound.length} script(s) detected.\n\nClick "OPEN FOLDER" to view files.`);
        this.setStatus('✓ RAR extraction complete');
    },

    async runSelectedScript() {
        const selected = this.rarFiles.filter(f => f.selected);
        if (selected.length === 0) {
            this.showToast('Select a RAR file first', 'warning');
            return;
        }

        const rar = selected[0];

        // Extract first
        const ok = await this.confirm('RUN SCRIPT',
            `Extract "${rar.filename}" and run scripts automatically?\n\n⚠️ Make sure you trust the contents!`);
        if (!ok) return;

        this.showProgress();
        document.getElementById('progress-status').textContent = 'Extracting...';

        const extractR = await this.api.extract_rar({rar_path: rar.path});
        if (!extractR.success) {
            this.hideProgress();
            this.showToast('Extraction failed: ' + extractR.error, 'error');
            return;
        }

        const scripts = extractR.scripts_found || [];
        if (scripts.length === 0) {
            this.hideProgress();
            this.alert('📦 NO SCRIPTS FOUND',
                'RAR extracted but no executable scripts found.\n\nOpen folder to view contents.');
            return;
        }

        // Run first script found
        const script = scripts[0];
        document.getElementById('progress-status').textContent = 'Running script...';

        const runR = await this.api.run_migration_script({script_path: script});
        this.hideProgress();

        if (runR.success) {
            this.alert('✅ SCRIPT COMPLETE',
                `Script: ${this.escape(script)}\n\nOutput:\n${this.escape(runR.output || 'No output')}`);
        } else {
            this.alert('❌ SCRIPT FAILED',
                `Script: ${this.escape(script)}\n\nError: ${this.escape(runR.error || 'Unknown error')}`);
        }
        this.setStatus(runR.success ? '✓ Script complete' : '❌ Script failed');
    },

    async openToolsFolder() {
        await this.api.open_extracted_folder();
    },
};

window.app = App;

// Auto-init when DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}
