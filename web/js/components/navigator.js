import { el } from '../dom.js';

export function renderNavigator({ items, current, onJump }) {
  return el('div', { class: 'navigator' }, items.map((it, i) => {
    const cls = ['nav-cell'];
    if (it.picked.length) cls.push('answered');
    if (it.flagged) cls.push('flagged');
    if (i === current) cls.push('current');
    return el('button', { class: cls.join(' '), type: 'button', title: `Question ${i + 1} (#${it.number})`, onClick: () => onJump(i) }, String(i + 1));
  }));
}
