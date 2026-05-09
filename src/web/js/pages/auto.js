/**
 * auto.js - Auto/Scheduler Page Module
 * UNS Backup App v3.1
 * Pattern: IIFE with init/mount/unmount + Api/State/Polling/Modal/Toast
 */
const AutoPage = (() => {
    'use strict';

    let container = null;
    let config = {};
    let pollingInterval = null;

    // ─── Init ─────────────────────────────────────────────────
    function init(el) {
        container = el;
        bindEvents();
    }

    function mount() {
        loadScheduleInfo();
    }

    function unmount() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    // ─── Bind Events ───────────────────────────────────────────
    function bindEvents() {
        // Frequency radios
        document.querySelectorAll('input[name="auto-freq"]').forEach(r => {
            r.addEventListener('change', onFreqChange);
        });

        // Buttons
        document.getElementById('btn-save-schedule')?.addEventListener('click', saveSchedule);
        document.getElementById('btn-test-schedule')?.addEventListener('click', testScheduleNow);
        document.getElementById('btn-remove-schedule')?.addEventListener('click', removeSchedule);
        document.getElementById('btn-auto-folder')?.addEventListener('click', chooseAutoFolder);

        // Enabled toggle
        document.getElementById('auto-enabled')?.addEventListener('change', (e) => {
            persistConfig({ schedule_enabled: e.target.checked });
        });
    }

    // ─── Load Schedule ────────────────────────────────────────
    async function loadScheduleInfo() {
        setStatus('🔍 Loading schedule info...');
        try {
            const r = await Api.get_schedule_info();
            config = r || {};

            // Update status banner
            const banner = document.getElementById('auto-status-banner');
            const detail = document.getElementById('auto-status-detail');
            if (banner && detail) {
                if (config.active) {
                    banner.classList.remove('inactive');
                    banner.classList.add('active');
                    banner.querySelector('strong').textContent = '✅ AUTO BACKUP ACTIVE';
                    if (config.info) {
                        detail.innerHTML = `Next: ${escapeHtml(config.info.next_run || '?')}<br>Last: ${escapeHtml(config.info.last_run || 'Never')}`;
                    }
                } else {
                    banner.classList.remove('active');
                    banner.classList.add('inactive');
                    banner.querySelector('strong').textContent = '⏸️ AUTO BACKUP DISABLED';
                    detail.textContent = '';
                }
            }

            // Fill form with config values (from app.js loadConfig pattern)
            const enabledEl = document.getElementById('auto-enabled');
            if (enabledEl) enabledEl.checked = config.schedule_enabled || false;

            const freq = config.schedule_frequency || 'weekly';
            const freqEl = document.querySelector(`input[name="auto-freq"][value="${freq}"]`);
            if (freqEl) freqEl.checked = true;

            const day = config.schedule_day_of_week || 'MON';
            const dayEl = document.querySelector(`input[name="auto-day"][value="${day}"]`);
            if (dayEl) dayEl.checked = true;

            const time = (config.schedule_time || '02:00').split(':');
            const hourEl = document.getElementById('auto-hour');
            const minEl = document.getElementById('auto-minute');
            if (hourEl) hourEl.value = parseInt(time[0], 10);
            if (minEl) minEl.value = parseInt(time[1] || '0', 10);

            const saveToEl = document.getElementById('auto-savepath');
            if (saveToEl) saveToEl.value = config.schedule_save_to || '';

            const scope = config.schedule_scope || 'uns_only';
            const scopeEl = document.querySelector(`input[name="auto-scope"][value="${scope}"]`);
            if (scopeEl) scopeEl.checked = true;

            const keepEl = document.getElementById('keep-last');
            if (keepEl) keepEl.value = config.schedule_keep_last !== undefined ? config.schedule_keep_last : 4;

            const customDaysEl = document.getElementById('custom-days');
            if (customDaysEl) customDaysEl.value = config.schedule_custom_days || 7;

            onFreqChange();
            setStatus('✓ Schedule loaded');
        } catch (err) {
            console.error('[AutoPage] loadScheduleInfo:', err);
            Toast.show('Failed to load schedule: ' + err.message, 'error');
            setStatus('❌ Load failed');
        }
    }

    function onFreqChange() {
        const f = document.querySelector('input[name="auto-freq"]:checked')?.value || 'weekly';
        const dayRow = document.getElementById('day-row');
        const customRow = document.getElementById('custom-row');
        if (dayRow) dayRow.style.display = (f === 'weekly' || f === 'biweekly') ? 'flex' : 'none';
        if (customRow) customRow.style.display = f === 'custom' ? 'flex' : 'none';
    }

    // ─── Save Schedule ─────────────────────────────────────────
    async function saveSchedule() {
        if (!document.getElementById('auto-enabled')?.checked) {
            Toast.show('Enable auto backup first', 'warning');
            return;
        }

        const params = {
            frequency: document.querySelector('input[name="auto-freq"]:checked')?.value || 'weekly',
            day_of_week: document.querySelector('input[name="auto-day"]:checked')?.value || 'MON',
            time: `${String(document.getElementById('auto-hour')?.value || '2').padStart(2, '0')}:${String(document.getElementById('auto-minute')?.value || '0').padStart(2, '0')}`,
            custom_days: parseInt(document.getElementById('custom-days')?.value || '7', 10),
            save_to: document.getElementById('auto-savepath')?.value || '',
            scope: document.querySelector('input[name="auto-scope"]:checked')?.value || 'uns_only',
            keep_last: parseInt(document.getElementById('keep-last')?.value || '4', 10),
        };

        try {
            const r = await Api.save_schedule(params);
            if (r.success) {
                Modal.alert('✅ SCHEDULE SAVED', `Auto backup will run at ${params.time}.`);
                loadScheduleInfo();
            } else {
                Toast.show('Save failed: ' + (r.error || 'Unknown'), 'error');
            }
        } catch (err) {
            console.error('[AutoPage] saveSchedule:', err);
            Toast.show('Save error: ' + err.message, 'error');
        }
    }

    async function removeSchedule() {
        const ok = await Modal.confirm('REMOVE SCHEDULE', 'Delete the scheduled task?');
        if (!ok) return;
        try {
            const r = await Api.call('remove_schedule');
            if (r.success) {
                Toast.show('Removed', 'success');
                loadScheduleInfo();
            } else {
                Toast.show('Remove failed', 'error');
            }
        } catch (err) {
            console.error('[AutoPage] removeSchedule:', err);
            Toast.show('Remove error: ' + err.message, 'error');
        }
    }

    async function testScheduleNow() {
        try {
            const r = await Api.test_schedule_now();
            if (r.success) Toast.show('Test executed', 'success');
            else Toast.show('Test failed: ' + (r.error || ''), 'error');
        } catch (err) {
            console.error('[AutoPage] testScheduleNow:', err);
            Toast.show('Test error: ' + err.message, 'error');
        }
    }

    // ─── Folder Selection ──────────────────────────────────────
    async function chooseAutoFolder() {
        const f = await Api.select_folder();
        if (f) {
            const el = document.getElementById('auto-savepath');
            if (el) el.value = f;
        }
    }

    // ─── Helpers ──────────────────────────────────────────────
    function setStatus(msg) {
        const el = document.getElementById('sb-status');
        if (el) el.textContent = '● ' + msg;
    }

    function persistConfig(updates) {
        Api.update_config(updates).catch(err => console.error('[AutoPage] persistConfig:', err));
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // ─── Public API ────────────────────────────────────────────
    return { init, mount, unmount, bindEvents, loadScheduleInfo };
})();