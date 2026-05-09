/**
 * cache.js - Cache Backup Page Module
 * UNS Backup App v3.1
 * Pattern: IIFE with init/mount/unmount + Api/State/Polling/Modal/Toast
 */
const CachePage = (() => {
    'use strict';

    let container = null;
    let cacheFiles = [];
    let pollingInterval = null;

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        bindEvents();
    }

    function mount() {
        // Nothing to auto-load on mount
    }

    function unmount() {
        Polling.stop('cache');
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        document.getElementById('btn-cache-scan')?.addEventListener('click', scanCacheFiles);
        document.getElementById('btn-cache-folder')?.addEventListener('click', chooseCacheFolder);
        document.getElementById('btn-cache-backup')?.addEventListener('click', startCacheBackup);
        document.getElementById('btn-cache-cancel')?.addEventListener('click', cancelBackup);
    }

    // ─── Scan Cache ─────────────────────────────────────────────
    async function scanCacheFiles() {
        setStatus('🔍 Scanning Outlook cache...');
        try {
            const r = await Api.scan_cache_files();
            if (!r.success) {
                Toast.show('Scan failed: ' + r.error, 'error');
                setStatus('❌ Scan failed');
                return;
            }
            cacheFiles = (r.files || []).map(f => ({ ...f, selected: true }));
            State.set('cacheFiles', cacheFiles);
            renderCacheList();
            updateCacheStats();
            setStatus(`✓ Found ${cacheFiles.length} cache file(s)`);
        } catch (err) {
            console.error('[CachePage] scanCacheFiles:', err);
            Toast.show('Scan error: ' + err.message, 'error');
        }
    }

    function renderCacheList() {
        const list = document.getElementById('cache-list');
        if (!list) return;

        if (cacheFiles.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:48px;">💾</div>
                    <p>No cache files found</p>
                    <p style="font-size:10px; margin-top:4px;">Outlook may not be installed or configured</p>
                </div>
            `;
            return;
        }

        list.innerHTML = cacheFiles.map((f, i) => {
            const ext = (f.extension || '').replace('.', '').toUpperCase();
            const account = f.account_smtp
                ? `<div class="cache-account">📧 ${escapeHtml(f.account_smtp)}</div>`
                : '';
            return `
                <div class="cache-item ${f.selected ? 'selected' : ''}" data-idx="${i}">
                    <div class="cache-icon">${f.extension === '.ost' ? '🔄' : '📦'}</div>
                    <div class="cache-info">
                        <div class="cache-name">${escapeHtml(f.filename)}<span class="cache-type ${ext.toLowerCase()}">${ext}</span></div>
                        <div class="cache-meta">📂 ${escapeHtml(f.path)}</div>
                        ${account}
                        <div class="cache-meta">📅 ${escapeHtml(f.modified || '')}</div>
                    </div>
                    <div class="cache-size">${f.size_mb || 0} MB</div>
                </div>
            `;
        }).join('');

        list.querySelectorAll('.cache-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx, 10);
                cacheFiles[i].selected = !cacheFiles[i].selected;
                el.classList.toggle('selected');
                updateCacheStats();
            });
        });
    }

    function updateCacheStats() {
        const countEl = document.getElementById('cache-stat-count');
        const selectedEl = document.getElementById('cache-stat-selected');
        const sizeEl = document.getElementById('cache-stat-size');
        const sizeSubEl = document.getElementById('cache-stat-size-sub');

        if (countEl) countEl.textContent = cacheFiles.length;
        const selected = cacheFiles.filter(f => f.selected);
        if (selectedEl) selectedEl.textContent = selected.length;

        const totalMB = selected.reduce((s, f) => s + (f.size_mb || 0), 0);
        if (totalMB >= 1024) {
            if (sizeEl) sizeEl.textContent = (totalMB / 1024).toFixed(1);
            if (sizeSubEl) sizeSubEl.textContent = 'gigabytes';
        } else {
            if (sizeEl) sizeEl.textContent = totalMB.toFixed(0);
            if (sizeSubEl) sizeSubEl.textContent = 'megabytes';
        }
    }

    // ─── Folder Selection ──────────────────────────────────────
    async function chooseCacheFolder() {
        const f = await Api.select_folder();
        if (f) {
            const el = document.getElementById('cache-output-dir');
            if (el) el.value = f;
        }
    }

    // ─── Cache Backup ──────────────────────────────────────────
    async function startCacheBackup() {
        const selected = cacheFiles.filter(f => f.selected);
        if (selected.length === 0) {
            Toast.show('Select at least one cache file', 'warning');
            return;
        }
        const outputDir = document.getElementById('cache-output-dir')?.value;
        if (!outputDir) {
            Toast.show('Choose output folder', 'warning');
            return;
        }

        const verify = document.getElementById('cache-verify')?.checked || false;
        const closeOutlook = document.getElementById('cache-close-outlook')?.checked || false;

        let confirmMsg = `${selected.length} cache file(s) will be backed up to:\n${outputDir}`;
        const totalMB = selected.reduce((s, f) => s + (f.size_mb || 0), 0);
        confirmMsg += `\n\nTotal size: ${(totalMB / 1024).toFixed(2)} GB`;
        if (closeOutlook) confirmMsg += '\n\n⚠️ Outlook will be CLOSED before backup.';
        confirmMsg += '\n\nProceed?';

        const ok = await Modal.confirm('CONFIRM CACHE BACKUP', confirmMsg);
        if (!ok) return;

        showProgress();
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = 'キャッシュバックアップ中...';

        try {
            const r = await Api.start_cache_backup({
                files: selected.map(f => f.path),
                output_dir: outputDir,
                verify_integrity: verify,
                close_outlook: closeOutlook,
            });
            if (!r.success) {
                hideProgress();
                Toast.show('Failed to start: ' + r.error, 'error');
                return;
            }
            const btnBackup = document.getElementById('btn-cache-backup');
            const btnCancel = document.getElementById('btn-cache-cancel');
            if (btnBackup) btnBackup.disabled = true;
            if (btnCancel) btnCancel.disabled = false;
            startCacheBackupPolling();
        } catch (err) {
            hideProgress();
            Toast.show('Start error: ' + err.message, 'error');
        }
    }

    function startCacheBackupPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = setInterval(async () => {
            try {
                const p = await Api.get_cache_progress();
                updateCacheBackupUI(p);
                if (p.state === 'success' || p.state === 'failed') {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                    onCacheBackupDone(p);
                }
            } catch (err) {
                console.error('[CachePage] polling:', err);
            }
        }, 500);
    }

    function updateCacheBackupUI(p) {
        const logEl = document.getElementById('cache-log');
        if (logEl && p.log) {
            logEl.innerHTML = p.log.map(l => {
                const t = new Date(l.ts).toLocaleTimeString();
                let cls = 'log-line';
                if (l.msg.includes('✅')) cls += ' ok';
                else if (l.msg.includes('❌')) cls += ' err';
                else if (l.msg.includes('💾') || l.msg.includes('🔐')) cls += ' info';
                return `<div class="${cls}"><span class="ts">[${t}]</span>${escapeHtml(l.msg)}</div>`;
            }).join('');
            logEl.scrollTop = logEl.scrollHeight;
            const logSection = document.getElementById('cache-log-section');
            if (logSection) logSection.style.display = 'block';
        }

        const lastMsg = p.log && p.log.length > 0 ? p.log[p.log.length - 1].msg : '';
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = lastMsg.substring(0, 80);

        const fileMatch = lastMsg.match(/\[(\d+)\/(\d+)\]/);
        if (fileMatch) {
            const cur = parseInt(fileMatch[1], 10), total = parseInt(fileMatch[2], 10);
            const pct = Math.round(cur / total * 100);
            const pctEl = document.getElementById('progress-percent');
            const fillEl = document.getElementById('progress-fill');
            const subEl = document.getElementById('progress-substatus');
            if (pctEl) pctEl.textContent = pct + '%';
            if (fillEl) fillEl.style.width = pct + '%';
            if (subEl) subEl.textContent = `${cur} / ${total} files`;
        }
        const pctMatch = lastMsg.match(/(\d+)%/);
        if (pctMatch && !fileMatch) {
            const fillEl = document.getElementById('progress-fill');
            if (fillEl) fillEl.style.width = pctMatch[1] + '%';
        }
    }

    function onCacheBackupDone(p) {
        hideProgress();
        const btnBackup = document.getElementById('btn-cache-backup');
        const btnCancel = document.getElementById('btn-cache-cancel');
        if (btnBackup) btnBackup.disabled = false;
        if (btnCancel) btnCancel.disabled = true;

        if (p.state === 'success') {
            Modal.alert(
                '✅ CACHE BACKUP COMPLETE',
                `Cache backup completed successfully!\n\nLocation: ${p.result}\n\n` +
                `💡 These OST files are tied to your original Outlook profile.\n` +
                `If you need to open them on another PC, use scanpst.exe to convert.`
            );
            setStatus('✓ Cache backup complete');
        } else {
            Modal.alert('❌ CACHE BACKUP FAILED', String(p.result || 'Unknown error'));
            setStatus('❌ Cache backup failed');
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
    return { init, mount, unmount, bindEvents, scanCacheFiles };
})();