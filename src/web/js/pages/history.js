/**
 * history.js - History Page Module
 * UNS Backup App v3.1
 * Pattern: IIFE with init/mount/unmount + Api/State/Polling/Modal/Toast
 */
const HistoryPage = (() => {
    'use strict';

    let container = null;
    let backups = [];

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        bindEvents();
    }

    function mount() {
        loadHistory();
    }

    function unmount() {
        // Nothing to clean up
    }

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        document.getElementById('btn-refresh-history')?.addEventListener('click', () => {
            // Limpiar búsqueda al refrescar
            const input = document.getElementById('history-search-input');
            if (input) input.value = '';
            loadHistory();
        });
        document.getElementById('btn-history-search')?.addEventListener('click', runSearch);
        document.getElementById('history-search-input')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') runSearch();
        });
        document.getElementById('btn-history-search-clear')?.addEventListener('click', clearSearch);
    }

    // ─── Search (Feature B v3.2.0) ─────────────────────────────
    async function runSearch() {
        const input = document.getElementById('history-search-input');
        const query = (input?.value || '').trim();
        if (!query) {
            Toast.show('Enter a search term', 'info');
            return;
        }
        setStatus(`🔍 Searching "${query}"...`);
        try {
            const r = await Api.search_backups({ query, limit: 50 });
            if (!r?.success) throw new Error(r?.error || 'Search failed');
            backups = r.results || [];
            State.set('history', backups);
            renderHistoryList();
            setStatus(`✓ ${backups.length} result(s) for "${query}"`);
        } catch (err) {
            console.error('[HistoryPage] runSearch:', err);
            Toast.show('Search failed: ' + err.message, 'error');
            setStatus('❌ Search failed');
        }
    }

    function clearSearch() {
        const input = document.getElementById('history-search-input');
        if (input) input.value = '';
        loadHistory();
    }

    // ─── Load History ─────────────────────────────────────────
    async function loadHistory() {
        setStatus('🔍 Loading backup history...');
        try {
            const r = await Api.get_backup_history();
            backups = r?.backups || [];
            State.set('history', backups);
            renderHistoryList();
            setStatus(`✓ ${backups.length} backups loaded`);
        } catch (err) {
            console.error('[HistoryPage] loadHistory:', err);
            Toast.show('Failed to load history: ' + err.message, 'error');
            setStatus('❌ Load failed');
        }
    }

    function renderHistoryList() {
        const list = document.getElementById('history-list');
        if (!list) return;

        if (backups.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:48px;">📭</div>
                    <p>No backup history</p>
                </div>
            `;
            return;
        }

        list.innerHTML = backups.map(b => {
            const icon = { success: '✅', partial: '⚠️', failed: '❌', incomplete: '⚪' }[b.status] || '❓';
            const date = b.start_time ? new Date(b.start_time).toLocaleString() : '';
            return `
                <div class="history-item" data-path="${escapeHtml(b.path || '')}">
                    <div class="h-status">${icon}</div>
                    <div class="h-info">
                        <div class="h-date">${escapeHtml(date)}</div>
                        <div class="h-name">${escapeHtml(b.name || '')}</div>
                    </div>
                    <div class="h-stat"><strong>${b.accounts_count || 0}</strong> accts</div>
                    <div class="h-stat"><strong>${(b.total_emails || 0).toLocaleString()}</strong> mails</div>
                    <div class="h-stat"><strong>${(b.total_size_mb || 0).toFixed(1)}</strong> MB</div>
                    <div class="h-actions">
                        <button class="btn btn-secondary" data-action="open" data-path="${escapeHtml(b.path || '')}">📂</button>
                        <button class="btn btn-danger" data-action="delete" data-path="${escapeHtml(b.path || '')}">🗑️</button>
                    </div>
                </div>
            `;
        }).join('');

        list.querySelectorAll('[data-action="open"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                openBackupFolder(btn.dataset.path);
            });
        });
        list.querySelectorAll('[data-action="delete"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteBackup(btn.dataset.path);
            });
        });
    }

    async function openBackupFolder(path) {
        try {
            await Api.open_backup_folder(path);
        } catch (err) {
            console.error('[HistoryPage] openBackupFolder:', err);
            Toast.show('Cannot open folder: ' + err.message, 'error');
        }
    }

    async function deleteBackup(path) {
        const ok = await Modal.confirm('DELETE BACKUP', `Permanently delete?\n\n${path}`);
        if (!ok) return;
        try {
            const r = await Api.delete_backup(path);
            if (r.success) {
                Toast.show('Deleted', 'success');
                loadHistory();
            } else {
                Toast.show('Delete failed: ' + (r.error || 'Unknown'), 'error');
            }
        } catch (err) {
            console.error('[HistoryPage] deleteBackup:', err);
            Toast.show('Delete error: ' + err.message, 'error');
        }
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
    return { init, mount, unmount, bindEvents, loadHistory, runSearch, clearSearch };
})();