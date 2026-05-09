/**
 * tools.js - Tools Page Module
 * UNS Backup App v3.1
 * Pattern: IIFE with init/mount/unmount + Api/State/Polling/Modal/Toast
 */
const ToolsPage = (() => {
    'use strict';

    let container = null;
    let rarFiles = [];
    let extractedFiles = [];
    let toolsPolling = null;

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        bindEvents();
    }

    function mount() {
        // Nothing to auto-load on mount
    }

    function unmount() {
        Polling.stop('tools');
        if (toolsPolling) {
            clearInterval(toolsPolling);
            toolsPolling = null;
        }
    }

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        document.getElementById('btn-tools-browse')?.addEventListener('click', chooseToolsFolder);
        document.getElementById('btn-tools-scan')?.addEventListener('click', scanRarFiles);
        document.getElementById('btn-tools-extract')?.addEventListener('click', extractSelectedRar);
        document.getElementById('btn-tools-run')?.addEventListener('click', runSelectedScript);
        document.getElementById('btn-tools-open-folder')?.addEventListener('click', openExtractedFolder);
    }

    // ─── Folder Selection ──────────────────────────────────────
    async function chooseToolsFolder() {
        const f = await Api.select_folder();
        if (f) {
            const el = document.getElementById('tools-rar-folder');
            if (el) el.value = f;
        }
    }

    // ─── Scan RAR ──────────────────────────────────────────────
    async function scanRarFiles() {
        const folder = document.getElementById('tools-rar-folder')?.value;
        if (!folder) {
            Toast.show('Choose a folder first', 'warning');
            return;
        }

        setStatus('🔍 Scanning for RAR files...');
        try {
            const r = await Api.find_rar_files(folder);
            if (!r.success) {
                Toast.show('Scan failed: ' + r.error, 'error');
                setStatus('❌ Scan failed');
                return;
            }
            rarFiles = (r.files || []).map(f => ({ ...f, selected: false }));
            renderRarList();
            const countEl = document.getElementById('tools-stat-rar');
            if (countEl) countEl.textContent = rarFiles.length;
            setStatus(`✓ Found ${rarFiles.length} RAR files`);
        } catch (err) {
            console.error('[ToolsPage] scanRarFiles:', err);
            Toast.show('Scan error: ' + err.message, 'error');
        }
    }

    function renderRarList() {
        const list = document.getElementById('rar-list');
        if (!list) return;

        if (rarFiles.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div style="font-size:48px;">📦</div>
                    <p>No RAR files found</p>
                </div>
            `;
            return;
        }

        list.innerHTML = rarFiles.map((f, i) => `
            <div class="rar-item ${f.selected ? 'selected' : ''}" data-idx="${i}">
                <div class="rar-icon">📦</div>
                <div class="rar-info">
                    <div class="rar-name">${escapeHtml(f.filename)}</div>
                    <div class="rar-meta">${escapeHtml(f.path)}</div>
                </div>
                <div class="rar-size">${f.size_mb || 0} MB</div>
            </div>
        `).join('');

        list.querySelectorAll('.rar-item').forEach(el => {
            el.addEventListener('click', () => {
                const i = parseInt(el.dataset.idx, 10);
                rarFiles[i].selected = !rarFiles[i].selected;
                el.classList.toggle('selected');
            });
        });
    }

    // ─── Extract RAR ───────────────────────────────────────────
    async function extractSelectedRar() {
        const selected = rarFiles.filter(f => f.selected);
        if (selected.length === 0) {
            Toast.show('Select at least one RAR file', 'warning');
            return;
        }

        const ok = await Modal.confirm(
            'EXTRACT RAR',
            `${selected.length} RAR file(s) will be extracted.\nExtracted files will be saved to a temp folder.\n\nProceed?`
        );
        if (!ok) return;

        showProgress();
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = 'RAR展開中...';
        extractedFiles = [];
        let scriptsFound = [];

        try {
            for (const rar of selected) {
                const r = await Api.extract_rar({ rar_path: rar.path });
                if (r.success) {
                    extractedFiles.push(...(r.files_extracted || []));
                    scriptsFound.push(...(r.scripts_found || []));
                }
            }

            hideProgress();
            const extEl = document.getElementById('tools-stat-extracted');
            const scrEl = document.getElementById('tools-stat-scripts');
            if (extEl) extEl.textContent = extractedFiles.length;
            if (scrEl) scrEl.textContent = scriptsFound.length;

            Modal.alert('✅ EXTRACTION COMPLETE',
                `${extractedFiles.length} files extracted.\n${scriptsFound.length} script(s) detected.\n\nClick "OPEN FOLDER" to view files.`);
            setStatus('✓ RAR extraction complete');
        } catch (err) {
            hideProgress();
            console.error('[ToolsPage] extractSelectedRar:', err);
            Toast.show('Extraction error: ' + err.message, 'error');
        }
    }

    // ─── Run Migration Script ──────────────────────────────────
    async function runSelectedScript() {
        const selected = rarFiles.filter(f => f.selected);
        if (selected.length === 0) {
            Toast.show('Select a RAR file first', 'warning');
            return;
        }

        const rar = selected[0];
        const ok = await Modal.confirm('RUN SCRIPT',
            `Extract "${rar.filename}" and run scripts automatically?\n\n⚠️ Make sure you trust the contents!`);
        if (!ok) return;

        showProgress();
        const statusEl = document.getElementById('progress-status');
        if (statusEl) statusEl.textContent = 'Extracting...';

        try {
            const extractR = await Api.extract_rar({ rar_path: rar.path });
            if (!extractR.success) {
                hideProgress();
                Toast.show('Extraction failed: ' + extractR.error, 'error');
                return;
            }

            const scripts = extractR.scripts_found || [];
            if (scripts.length === 0) {
                hideProgress();
                Modal.alert('📦 NO SCRIPTS FOUND',
                    'RAR extracted but no executable scripts found.\n\nOpen folder to view contents.');
                return;
            }

            if (statusEl) statusEl.textContent = 'Running script...';
            const runR = await Api.run_migration({ script_path: scripts[0] });
            hideProgress();

            if (runR.success) {
                Modal.alert('✅ SCRIPT COMPLETE',
                    `Script: ${escapeHtml(scripts[0])}\n\nOutput:\n${escapeHtml(runR.output || 'No output')}`);
            } else {
                Modal.alert('❌ SCRIPT FAILED',
                    `Script: ${escapeHtml(scripts[0])}\n\nError: ${escapeHtml(runR.error || 'Unknown error')}`);
            }
            setStatus(runR.success ? '✓ Script complete' : '❌ Script failed');
        } catch (err) {
            hideProgress();
            console.error('[ToolsPage] runSelectedScript:', err);
            Toast.show('Run error: ' + err.message, 'error');
        }
    }

    async function openExtractedFolder() {
        try {
            await Api.call('open_extracted_folder');
        } catch (err) {
            console.error('[ToolsPage] openExtractedFolder:', err);
            Toast.show('Cannot open folder: ' + err.message, 'error');
        }
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
    return { init, mount, unmount, bindEvents, scanRarFiles };
})();