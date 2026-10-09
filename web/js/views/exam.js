import { el } from '../dom.js';

export async function render(container) {
  container.replaceChildren(el('section', { class: 'card' }, el('h2', {}, 'Coming soon'), el('a', { class: 'btn link', href: '#/' }, 'Home')));
}
