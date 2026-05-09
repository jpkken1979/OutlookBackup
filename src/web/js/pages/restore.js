/**
 * restore.js - Restore Page Module
 * UNS Backup App v3.1
 */
const RestorePage = (() => {
    'use strict';

    let container = null;
    let psts = [];
    let pollingInterval = null;

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        bindEvents();
    }

    function mount() {
        render();
    }

    function unmount() {
        Polling.stop('restore');
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        document.getElementById('btn-restore-browse')?.addEventListener('click', chooseRestoreFolder);
        document.getElementById('btn-restore-search')?.addEventListener('click', searchPSTs);
        document.getElementById('btn-start-import')?.addEventListener('click', startImport);
        document.getElementById('btn-preview-pst')?.addEventListener('click', previewPST);

        // Method cards
        document.querySelectorAll('input[name="import-method"]').forEach(r => {
            r.addEventListener('change', (e) => onMethodChange(e.target.value));
        });
    }

    function render() {
        // The HTML already has the structure
    }

    // ─── Folder & Search ───────────────────────────────────────
    async function chooseRestoreFolder() {
        const f = await Api.select_folder();
        if (f) {
            document.getElementById('restore-folder').value = f;
        }
    }

    async function searchPSTs() {
        const folder = document.getElementById('restore-folder')?.value;
        if (!folder) {
            Toast.show('Choose a folder first', 'warning');
            return;
        }

        setStatus('🔍 Searching for PSTs...');
        try {
            const r = await Api.search_pst_files(folder);
            if (!r.success) {
                Toast.show('Search failed: ' + r.error, 'error');
                setStatus('❌ Search failed');
                return;
            }

            psts = (r.files || []).map(f => ({ ...f, selected: true }));
            renderPSTs();
            setStatus(`✓ Found ${psts.length} PST files`);
        } catch (err) {
            console.error('[RestorePage] searchPSTs:', err);
            Toast.show('Search error: ' + err.message, 'error');
        }
    }

    function renderPSTs() {
        const list = document.getElementById('pst-list');
        if (!list) return;

        if (psts.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:48px;">📂</div>
                    <p>No PSTs found</p>
                </div>
            `;
            return;
        }

        list.innerHTML = psts.map((p, i) => `
            <div class="pst-item ${p.selected ? 'selected' : ''}" data-idx="${i}">
                <div class="pst-icon">📦</div>
                <div class="pst-info">
                    <div class="pst-name">${escapeHtml(p.filename || '')}</div>
                    <div class="pst-meta">${escapeHtml(p.account || '—')} · ${escapeHtml(p.created || '')}</div>
                </div>
                <div class="pst-size">${p.size_mb || 0} MB</div>
            </div>
        `).join('');

        list.querySelectorAll('.pst-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx, 10);
                psts[i].selected = !psts[i].selected;
                el.classList.toggle('selected');
            });
        });
    }

    function onMethodChange(method) {
        document.querySelectorAll('.method-card').forEach(c =>
            c.classList.toggle('selected', c.dataset.method === method)
        );
        const merge = document.querySelector('.method-card[data-method="merge"] .merge-target');
        if (merge) merge.style.display = method === 'merge' ? 'flex' : 'none';

        // Persist to config
        Api.update_config({ default_import_mode: method }).catch(() => {});
    }

    // ─── Import ────────────────────────────────────────────────
    async function startImport() {
        const selected = psts.filter(p => p.selected);
        if (selected.length === 0) {
            Toast.show('Select at least one PST', 'warning');
            return;
        }

        const method = document.querySelector('input[name="import-method"]:checked')?.value || 'separate_folder';
        const target = method === 'merge' ? document.getElementById('target-account')?.value : null;

        if (method === 'merge' && !target) {
            Toast.show('Choose target account for merge', 'warning');
            return;
        }

        const ok = await Modal.confirm(
            'CONFIRM IMPORT',
            `${selected.length} PST file(s) will be imported.\nMethod: ${method}\n\nProceed?`
        );
        if (!ok) return;

        try {
            const r = await Api.start_import({
                files: selected.map(p => p.path),
                mode: method,
                target_smtp: target,
            });

            if (!r.success) {
                Toast.show('Failed: ' + r.error, 'error');
                return;
            }

            document.getElementById('btn-start-import').disabled = true;
            startImportPolling();
        } catch (err) {
            Toast.show('Start import error: ' + err.message, 'error');
        }
    }

    function startImportPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = setInterval(async () => {
            try {
                const p = await Api.get_import_progress();
                updateImportUI(p);
                if (p.state === 'success' || p.state === 'failed') {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                    onImportDone(p);
                }
            } catch (err) {
                console.error('[RestorePage] polling:', err);
            }
        }, 500);
    }

    function updateImportUI(p) {
        const logEl = document.getElementById('import-log');
        if (logEl && p.log) {
            logEl.innerHTML = p.log.map(l => {
                const t = new Date(l.ts).toLocaleTimeString();
                let cls = 'log-line';
                if (l.msg.includes('✅')) cls += ' ok';
                else if (l.msg.includes('❌')) cls += ' err';
                return `<div class="${cls}"><span class="ts">[${t}]</span>${escapeHtml(l.msg)}</div>`;
            }).join('');
            logEl.scrollTop = logEl.scrollHeight;
            const logSection = document.getElementById('import-log-section');
            if (logSection) logSection.style.display = 'block';
        }
    }

    function onImportDone(p) {
        document.getElementById('btn-start-import').disabled = false;
        if (p.state === 'success') {
            const r = p.result || {};
            Modal.alert('✅ IMPORT COMPLETE',
                `${r.ok_count || '?'}/${p.total || '?'} PSTs imported successfully.\nCheck your Outlook.`);
            setStatus('✓ Import complete');
        } else {
            Modal.alert('❌ IMPORT FAILED', String(p.result || 'Unknown error'));
            setStatus('❌ Import failed');
        }
    }

    // ─── Preview ───────────────────────────────────────────────
    async function previewPST() {
        const sel = psts.find(p => p.selected);
        if (!sel) {
            Toast.show('Select a PST first', 'warning');
            return;
        }

        setStatus('🔍 Previewing PST...');
        try {
            const r = await Api.preview_pst(sel.path);
            if (!r.success) {
                Toast.show('Preview failed: ' + r.error, 'error');
                setStatus('❌ Preview failed');
                return;
            }

            const i = r.info || {};
            let body = `${escapeHtml(i.filename || sel.filename)}\n\n`;
            body += `Size: ${i.size_mb || 0} MB\n`;
            body += `Total emails: ${(i.total_emails || 0).toLocaleString()}\n`;
            body += `Folders: ${i.total_folders || 0}\n\n`;
            if (i.folders) {
                body += '📁 Folders:\n';
                i.folders.slice(0, 20).forEach(f => {
                    body += `${'  '.repeat(f.depth || 0)}${escapeHtml(f.name)}: ${(f.count || 0).toLocaleString()}\n`;
                });
            }
            Modal.alert('🔍 PST PREVIEW', body);
            setStatus('✓ Preview ready');
        } catch (err) {
            console.error('[RestorePage] previewPST:', err);
            Toast.show('Preview error: ' + err.message, 'error');
        }
    }

    // ─── Helpers ──────────────────────────────────────────────
    function setStatus(msg) {
        document.getElementById('sb-status').textContent = '● ' + msg;
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ─── Public API ────────────────────────────────────────────
    return { init, mount, unmount, bindEvents, render };
})();