/** Holds the loaded bank + progress; debounced, retrying saves of the whole progress document. */
import * as api from './api.js';
import { SAVE_DEBOUNCE_MS, SAVE_RETRY_MAX_MS, SAVE_RETRY_MIN_MS } from './config.js';
import { emptyProgress } from './progress.js';
import { toast } from './toast.js';

export const store = {
  bankId: null, bank: null, byNumber: new Map(), progress: null,
  dirty: false, saving: false, timer: null, retryDelay: SAVE_RETRY_MIN_MS,
};

export async function loadBank(bankId) {
  const [bank, progress] = await Promise.all([api.getBank(bankId), api.getProgress(bankId)]);
  store.bankId = bankId;
  store.bank = bank;
  store.byNumber = new Map(bank.questions.map((q) => [q.number, q]));
  store.progress = { ...emptyProgress(bankId), ...progress, bank_id: bankId };
  store.dirty = false;
  localStorage.setItem('selectedBank', bankId);
}

export function update(reducer) {
  store.progress = reducer(store.progress);
  store.dirty = true;
  clearTimeout(store.timer);
  store.timer = setTimeout(flush, SAVE_DEBOUNCE_MS);
  return store.progress;
}

export async function flush() {
  clearTimeout(store.timer);
  store.timer = null;
  if (!store.dirty || store.saving || !store.bankId) return;
  store.saving = true;
  const snapshot = store.progress;
  try {
    const res = await api.putProgress(store.bankId, snapshot);
    if (store.progress === snapshot) {
      store.dirty = false;
      store.progress = { ...snapshot, updated_at: res.updated_at };
    }
    store.retryDelay = SAVE_RETRY_MIN_MS;
    toast.hide('save');
  } catch (err) {
    toast.show('save', `Progress not saved — retrying… (${err.message})`, { sticky: true, kind: 'error' });
    store.timer = setTimeout(flush, store.retryDelay);
    store.retryDelay = Math.min(store.retryDelay * 2, SAVE_RETRY_MAX_MS);
  } finally {
    store.saving = false;
    if (store.dirty && store.timer == null) store.timer = setTimeout(flush, SAVE_DEBOUNCE_MS);
  }
}

window.addEventListener('beforeunload', (e) => {
  if (store.dirty) { e.preventDefault(); e.returnValue = ''; }
});
