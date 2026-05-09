/**
 * Toast Component — UNS Backup v3.1
 * Method: Toast.show(message, type, duration)
 * Position: top-right, auto-dismiss with progress bar
 */
const Toast = (function() {
    'use strict';

    const ICONS = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️',
    };

    const DEFAULT_DURATION = 3500;

    function show(message, type, duration) {
        type = type || 'info';
        duration = duration || DEFAULT_DURATION;

        let container = document.getElementById('uns-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'uns-toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `uns-toast uns-toast--${type}`;
        const icon = ICONS[type] || ICONS.info;
        const progressId = `toast-progress-${Date.now()}-${Math.random().toString(36).slice(2)}`;

        toast.innerHTML = `
            <span class="uns-toast__icon">${icon}</span>
            <span class="uns-toast__message">${escapeHtml(message)}</span>
            <button class="uns-toast__close" aria-label="Close">✕</button>
            <div class="uns-toast__progress" id="${progressId}"></div>
        `;

        toast.querySelector('.uns-toast__close').addEventListener('click', () => dismiss(toast));
        container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('visible'));

        setTimeout(() => dismiss(toast), duration);

        const progressBar = document.getElementById(progressId);
        if (progressBar) {
            progressBar.style.transition = `width ${duration}ms linear`;
            requestAnimationFrame(() => { progressBar.style.width = '0%'; });
        }

        return toast;
    }

    function dismiss(toast) {
        if (!toast || !toast.parentNode) return;
        toast.classList.remove('visible');
        setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 400);
    }

    function escapeHtml(str) {
        return String(str || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    return { show, dismiss };
}());
