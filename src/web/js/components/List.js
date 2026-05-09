/**
 * List Component — UNS Backup v3.1
 * Renders items with templates adapted by type
 * Types: account | pst | cache | rar
 */
const List = (function() {
    'use strict';

    function esc(str) {
        return String(str || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    const TEMPLATES = {
        account(item, idx) {
            const initial = (item.smtp || '?').charAt(0).toUpperCase();
            const colorStyle = (item.smtp || '').startsWith('info') ? 'background: linear-gradient(135deg, #ff3838, #b91c1c);' : '';
            return `<div class="account-item ${item.selected ? 'selected' : ''}" data-idx="${idx}">
                <div class="acc-icon" style="${colorStyle}">${initial}</div>
                <div class="acc-info">
                    <div class="acc-email">${esc(item.smtp)}</div>
                    <div class="acc-meta">${esc(item.type || 'IMAP')} · ${esc(item.display_name || '')}</div>
                </div>
            </div>`;
        },
        pst(item, idx) {
            return `<div class="pst-item ${item.selected ? 'selected' : ''}" data-idx="${idx}">
                <div class="pst-icon">📦</div>
                <div class="pst-info">
                    <div class="pst-name">${esc(item.filename)}</div>
                    <div class="pst-meta">${esc(item.account || '—')} · ${esc(item.created)}</div>
                </div>
                <div class="pst-size">${item.size_mb} MB</div>
            </div>`;
        },
        cache(item, idx) {
            const ext = (item.extension || '').replace('.', '').toUpperCase();
            const accountLine = item.account_smtp ? `<div class="cache-account">📩 ${esc(item.account_smtp)}</div>` : '';
            return `<div class="cache-item ${item.selected ? 'selected' : ''}" data-idx="${idx}">
                <div class="cache-icon">${item.extension === '.ost' ? '🔄' : '📦'}</div>
                <div class="cache-info">
                    <div class="cache-name">${esc(item.filename)}<span class="cache-type ${ext.toLowerCase()}">${ext}</span></div>
                    <div class="cache-meta">📂 ${esc(item.path)}</div>
                    ${accountLine}
                    <div class="cache-meta">📅 ${esc(item.modified)}</div>
                </div>
                <div class="cache-size">${item.size_mb} MB</div>
            </div>`;
        },
        rar(item, idx) {
            return `<div class="rar-item ${item.selected ? 'selected' : ''}" data-idx="${idx}">
                <div class="rar-icon">📦</div>
                <div class="rar-info">
                    <div class="rar-name">${esc(item.filename)}</div>
                    <div class="rar-meta">${esc(item.path)}</div>
                </div>
                <div class="rar-size">${item.size_mb} MB</div>
            </div>`;
        },
    };

    function render(container, options) {
        const { items = [], type = 'account', onSelect = null, emptyMessage = 'No items', emptyIcon = '📩' } = options || {};
        container.innerHTML = '';

        if (!items || items.length === 0) {
            container.innerHTML = `<div class="empty-state"><div style="font-size:48px;">${emptyIcon}</div><p>${emptyMessage}</p></div>`;
            return container;
        }

        const template = TEMPLATES[type] || TEMPLATES.account;
        const frag = document.createDocumentFragment();

        items.forEach((item, idx) => {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = template(item, idx);
            const el = wrapper.firstElementChild;
            el.addEventListener('click', () => {
                if (typeof onSelect === 'function') onSelect(idx, item, el);
            });
            frag.appendChild(el);
        });

        container.appendChild(frag);
        return container;
    }

    function update(container, updates) {
        if (!container || !updates.items) return;
        const els = container.querySelectorAll('[data-idx]');
        updates.items.forEach((item, idx) => {
            if (els[idx]) els[idx].classList.toggle('selected', !!item.selected);
        });
    }

    return { render, update };
}());
