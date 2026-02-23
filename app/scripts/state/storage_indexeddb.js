// IndexedDB persistence adapter (planned).
// Current implementation intentionally forwards to local-storage adapter
// so the API surface is stable while persistence is upgraded.

import { loadLocalState, saveLocalState } from './storage_local.js';

export async function loadStateIndexedDb() {
  return loadLocalState();
}

export async function saveStateIndexedDb(state) {
  return saveLocalState(state);
}
