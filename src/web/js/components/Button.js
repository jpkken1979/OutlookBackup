/**
 * Button Component — UNS Backup v3.1
 * IIFE pattern, consumes tokens from styles.css
 */
const Button = (function() {
    'use strict';

    const DEFAULTS = {
        variant: 'primary',   // primary | secondary | danger | ghost | success | warning
        size: 'md',           // sm | md | lg
        loading: false,
        disabled: false,
        icon: null,
        onclick: null,
        type: 'button',
        className: '',
        id: '',
    };

    function create(props) {
        const cfg = Object.assign({}, DEFAULTS, props || {});
        const btn = document.createElement('button');
        const classes = ['uns-btn', `uns-btn--${cfg.variant}`, `uns-btn--${cfg.size}`];
        if (cfg.className) classes.push(cfg.className);
        if (cfg.loading) classes.push('uns-btn--loading');
        if (cfg.disabled || cfg.loading) btn.disabled = true;
        btn.className = classes.join(' ');
        if (cfg.id) btn.id = cfg.id;
        btn.type = cfg.type;
        btn.innerHTML = buildContent(cfg);
        if (typeof cfg.onclick === 'function') {
            btn.addEventListener('click', (e) => {
                if (!cfg.disabled && !cfg.loading) cfg.onclick(e);
            });
        }
        return btn;
    }

    function buildContent(cfg) {
        let html = '';
        if (cfg.icon) html += `<span class="uns-btn__icon">${cfg.icon}</span>`;
        if (cfg.loading) html += `<span class="uns-btn__spinner"></span>`;
        if (cfg.text) html += `<span class="uns-btn__text">${cfg.text}</span>`;
        return html || '&nbsp;';
    }

    function mount(container, props) {
        const btn = create(props);
        container.appendChild(btn);
        return btn;
    }

    function update(btn, updates) {
        if (!btn || !btn.classList.contains('uns-btn')) return;
        if ('loading' in updates) {
            btn.classList.toggle('uns-btn--loading', updates.loading);
            btn.disabled = updates.disabled || updates.loading;
            const existingSpinner = btn.querySelector('.uns-btn__spinner');
            if (updates.loading && !existingSpinner) {
                const icon = btn.querySelector('.uns-btn__icon');
                const span = document.createElement('span');
                span.className = 'uns-btn__spinner';
                if (icon) btn.insertBefore(span, icon.nextSibling);
                else btn.prepend(span);
            } else if (!updates.loading && existingSpinner) {
                existingSpinner.remove();
            }
        }
        if ('disabled' in updates && !updates.loading) btn.disabled = updates.disabled;
        if ('text' in updates) {
            let textEl = btn.querySelector('.uns-btn__text');
            if (!textEl) { textEl = document.createElement('span'); textEl.className = 'uns-btn__text'; btn.appendChild(textEl); }
            textEl.textContent = updates.text;
        }
        if ('icon' in updates) {
            let iconEl = btn.querySelector('.uns-btn__icon');
            if (!iconEl) { iconEl = document.createElement('span'); iconEl.className = 'uns-btn__icon'; btn.prepend(iconEl); }
            iconEl.innerHTML = updates.icon;
        }
        if ('variant' in updates) {
            btn.className = btn.className.replace(/uns-btn--\w+/g, '').split(' ').filter(Boolean).concat([`uns-btn--${updates.variant}`, 'uns-btn']).join(' ');
        }
    }

    return { create, mount, update };
}());
