import { el } from './dom.js';

const timers = new Map();

export const toast = {
  show(id, message, { sticky = false, ms = 3000, kind = 'info' } = {}) {
    this.hide(id);
    document.getElementById('toast-root').append(el('div', { class: `toast ${kind}`, id: `toast-${id}` }, message));
    if (!sticky) timers.set(id, setTimeout(() => this.hide(id), ms));
  },
  hide(id) {
    clearTimeout(timers.get(id));
    timers.delete(id);
    document.getElementById(`toast-${id}`)?.remove();
  },
};
