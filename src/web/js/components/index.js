/**
 * components/index.js — UNS Backup v3.1
 * Re-exports all UI components for easy import from pages
 */
const Components = (function() {
    return {
        Button: typeof Button !== 'undefined' ? Button : null,
        Card: typeof Card !== 'undefined' ? Card : null,
        Modal: typeof Modal !== 'undefined' ? Modal : null,
        Toast: typeof Toast !== 'undefined' ? Toast : null,
        List: typeof List !== 'undefined' ? List : null,
    };
}());

if (typeof window !== 'undefined') {
    window.Components = Components;
    window.Button = Button;
    window.Card = Card;
    window.Modal = Modal;
    window.Toast = Toast;
    window.List = List;
}
