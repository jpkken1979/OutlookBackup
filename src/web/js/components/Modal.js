/**
 * Modal Component — UNS Backup v3.1
 * Static methods: Modal.confirm(), Modal.alert(), Modal.show()
 */
const Modal = (function() {
    'use strict';

    let _instance = null;

    function getInstance() {
        if (!_instance) {
            const overlay = document.createElement('div');
            overlay.id = 'uns-modal-overlay';
            overlay.className = 'uns-modal-overlay';
            overlay.innerHTML = `
                <div class="uns-modal" id="uns-modal">
                    <div class="uns-modal__header" id="uns-modal-header"></div>
                    <div class="uns-modal__body" id="uns-modal-body"></div>
                    <div class="uns-modal__actions" id="uns-modal-actions"></div>
                </div>
            `;
            document.body.appendChild(overlay);
            _instance = overlay;
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay && _instance.dataset.closable === 'true') close();
            });
        }
        return _instance;
    }

    function open(options) {
        const cfg = Object.assign({
            title: '',
            body: '',
            actions: [{text: 'OK', class: 'btn-primary', onClick: close}],
            closable: false,
        }, options || {});

        const el = getInstance();
        el.dataset.closable = String(cfg.closable);
        document.getElementById('uns-modal-header').textContent = cfg.title || '';
        document.getElementById('uns-modal-body').innerHTML = cfg.body || '';

        const actionsEl = document.getElementById('uns-modal-actions');
        actionsEl.innerHTML = '';
        cfg.actions.forEach(action => {
            const btn = document.createElement('button');
            btn.className = `btn ${action.class || 'btn-primary'}`;
            btn.textContent = action.text || 'OK';
            btn.addEventListener('click', () => {
                if (typeof action.onClick === 'function') action.onClick();
                close();
            });
            actionsEl.appendChild(btn);
        });

        el.style.display = 'flex';
        return el;
    }

    function close() {
        if (_instance) _instance.style.display = 'none';
    }

    function show(options) {
        return open(Object.assign({closable: true}, options));
    }

    function alert(title, body, onOk) {
        return open({
            title: title,
            body: body,
            closable: false,
            actions: [{text: 'OK', class: 'btn-primary', onClick: onOk || null}],
        });
    }

    function confirm(title, body, onYes, onNo) {
        return open({
            title: title,
            body: body,
            closable: false,
            actions: [
                {text: 'CANCEL', class: 'btn-secondary', onClick: onNo || null},
                {text: 'OK', class: 'btn-primary', onClick: onYes},
            ],
        });
    }

    function prompt(title, body, defaultValue, onOk) {
        const inputId = 'uns-modal-prompt-input';
        return open({
            title: title,
            body: `${body}<input type="text" id="${inputId}" value="${defaultValue || ''}" style="width:100%;margin-top:12px;padding:8px;background:rgba(0,132,255,0.05);border:1px solid var(--border);border-radius:4px;color:var(--text);font-family:Consolas,monospace;font-size:12px;" />`,
            closable: false,
            actions: [
                {text: 'CANCEL', class: 'btn-secondary', onClick: null},
                {
                    text: 'OK', class: 'btn-primary',
                    onClick: () => { const val = document.getElementById(inputId)?.value; if (typeof onOk === 'function') onOk(val); }
                },
            ],
        });
    }

    return { open, close, show, alert, confirm, prompt };
}());
