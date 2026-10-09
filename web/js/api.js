export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(url, options = {}) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (e) {
    throw new ApiError(`Cannot reach the server (${e.message})`, 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* non-JSON error body */ }
    throw new ApiError(`${res.status}: ${detail}`, res.status);
  }
  return res.json();
}

const enc = encodeURIComponent;
export const listBanks = () => request('/api/banks');
export const getBank = (id) => request(`/api/banks/${enc(id)}`);
export const getProgress = (id) => request(`/api/banks/${enc(id)}/progress`);
export const putProgress = (id, doc) => request(`/api/banks/${enc(id)}/progress`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(doc),
});
export const imageUrl = (bankId, src) => `/banks/${enc(bankId)}/${src}`;
