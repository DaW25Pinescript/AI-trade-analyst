// IndexedDB persistence adapter (planned).
// Current implementation intentionally forwards to local-storage adapter
// so the API surface is stable while persistence is upgraded.

import { loadState, saveState } from './storage_local.js';

export async function loadStateIndexedDb() {
  return loadState();
}

export async function saveStateIndexedDb(state) {
  return saveState(state);
}
