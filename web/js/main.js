import * as api from './api.js';
import { el } from './dom.js';
import { loadBank, store } from './store.js';
import * as home from './views/home.js';
import * as examSetup from './views/examSetup.js';
import * as exam from './views/exam.js';
import * as examResult from './views/examResult.js';
import * as practiceSetup from './views/practiceSetup.js';
import * as practice from './views/practice.js';
import * as review from './views/review.js';

// Longest prefixes first so 'exam/result/<id>' is not captured by 'exam'.
const routes = [
  ['exam/result', examResult], ['exam/setup', examSetup], ['exam', exam],
  ['practice/setup', practiceSetup], ['practice', practice], ['review', review], ['', home],
];
let cleanup = null;

function match(hash) {
  const path = hash.replace(/^#\/?/, '').replace(/\/+$/, '');
  for (const [prefix, view] of routes) {
    const hit = prefix === '' ? path === '' : path === prefix || path.startsWith(prefix + '/');
    if (hit) {
      const rest = path.slice(prefix.length).replace(/^\//, '');
      return { view, params: rest ? rest.split('/').map(decodeURIComponent) : [] };
    }
  }
  return { view: home, params: [] };
}

async function ensureBank() {
  if (store.bank) return;
  const banks = await api.listBanks();
  if (!banks.length) throw new Error('No question banks found. Run: uv run parse-pdf <file.pdf> --id <bank-id> --title "<title>"');
  const saved = localStorage.getItem('selectedBank');
  await loadBank(banks.some((b) => b.id === saved) ? saved : banks[0].id);
}

function renderError(container, err) {
  container.replaceChildren(el('section', { class: 'card error' },
    el('h2', {}, 'Something went wrong'),
    el('p', {}, err.message || String(err)),
    el('p', { class: 'muted' }, 'Is the server running? Start it with: uv run serve'),
    el('button', { class: 'btn', onClick: () => navigate() }, 'Retry')));
}

export async function navigate() {
  const container = document.getElementById('app');
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  container.replaceChildren(el('p', { class: 'muted' }, 'Loading…'));
  const { view, params } = match(location.hash);
  try {
    await ensureBank();
    document.getElementById('bank-label').textContent = store.bank.bank.title;
    container.replaceChildren();
    cleanup = (await view.render(container, params)) || null;
  } catch (err) {
    console.error(err);
    renderError(container, err);
  }
}

window.addEventListener('hashchange', navigate);
navigate();
