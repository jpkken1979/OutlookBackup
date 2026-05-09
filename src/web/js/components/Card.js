/**
 * Card Component — UNS Backup v3.1
 * Handles: stat-card, account-item, pst-item, cache-item
 */
const Card = (function() {
    'use strict';

    const DEFAULTS = {
        type: 'stat',   // stat | account | pst | cache
        selected: false,
        onClick: null,
        className: '',
        id: '',
    };

    function create(props) {
        const cfg = Object.assign({}, DEFAULTS, props || {});
        const el = document.createElement('div');
        const classes = ['uns-card', `uns-card--${cfg.type}`];
        if (cfg.selected) classes.push('selected');
        if (cfg.className) classes.push(cfg.className);
        el.className = classes.join(' ');
        if (cfg.id) el.id = cfg.id;
        if (cfg.onClick) el.style.cursor = 'pointer';
        el.innerHTML = buildContent(cfg);
        el.addEventListener('click', () => {
            if (typeof cfg.onClick === 'function') cfg.onClick(el, cfg);
        });
        return el;
    }

    function buildContent(cfg) {
        if (cfg.content) return cfg.content;
        let html = '';
        if (cfg.icon) html += `<div class="uns-card__icon">${cfg.icon}</div>`;
        if (cfg.label) html += `<div class="uns-card__label">${cfg.label}</div>`;
        if (cfg.value) html += `<div class="uns-card__value">${cfg.value}</div>`;
        if (cfg.meta) html += `<div class="uns-card__meta">${cfg.meta}</div>`;
        if (cfg.size) html += `<div class="uns-card__size">${cfg.size}</div>`;
        return html;
    }

    function mount(container, props) {
        const el = create(props);
        container.appendChild(el);
        return el;
    }

    function toggleSelected(el) {
        if (!el || !el.classList.contains('uns-card')) return;
        el.classList.toggle('selected');
        return el.classList.contains('selected');
    }

    function update(el, updates) {
        if (!el || !el.classList.contains('uns-card')) return;
        if ('selected' in updates) el.classList.toggle('selected', updates.selected);
        if ('content' in updates) el.innerHTML = updates.content;
        if ('className' in updates) {
            el.className = el.className.split(' ').filter(c => !c.startsWith('uns-card--') && c !== 'selected').join(' ');
            el.classList.add(...updates.className.split(' '));
        }
    }

    return { create, mount, toggleSelected, update };
}());
