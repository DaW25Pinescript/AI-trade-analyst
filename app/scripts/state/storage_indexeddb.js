/**
 * IndexedDB persistence adapter — Phase 4 performance upgrade.
 *
 * Replaces the localStorage-only stub with a real IndexedDB implementation:
 *   - `trades` object store: persistent per-entry trade journal
 *   - Indexed by `createdAt` (time-range queries) and `asset` (per-instrument filter)
 *   - Cursor-based pagination so large histories don't block the main thread
 *
 * The current-session state (form fields, uploads) still lives in localStorage
 * via storage_local.js. IndexedDB is used exclusively for the persistent trade
 * journal that feeds the analytics dashboard.
 *
 * API surface (all async):
 *   openTradeDB()                        -> IDBDatabase
 *   saveTradeEntry(ticket, aar)          -> void       -- upserts by ticketId
 *   loadTradeHistoryPage(cursor, limit)  -> { entries, nextCursor }
 *   loadAllTradeHistory()                -> entry[]    -- backward compat
 *   deleteTradeEntry(ticketId)           -> void
 *   clearTradeHistory()                  -> void
 *   getTradeCount()                      -> number
 */

import { loadLocalState, saveLocalState } from './storage_local.js';

// -- Database constants -------------------------------------------------------
const DB_NAME    = 'ai_trade_analyst_v3';
const DB_VERSION = 1;
const STORE      = 'trades';

// -- DB open / upgrade --------------------------------------------------------

/**
 * Open (and if necessary upgrade) the IndexedDB database.
 * Returns a Promise<IDBDatabase>.
 */
export function openTradeDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (event) => {
      const db = event.target.result;

      if (!db.objectStoreNames.contains(STORE)) {
        // Primary key: ticketId (unique per trade).
        const store = db.createObjectStore(STORE, { keyPath: 'ticketId' });

        // Index 1: createdAt -- for time-range queries and chronological iteration.
        store.createIndex('createdAt', 'createdAt', { unique: false });

        // Index 2: asset -- extracted from ticketId prefix for per-instrument filtering.
        store.createIndex('asset', 'asset', { unique: false });
      }
    };

    req.onsuccess = (event) => resolve(event.target.result);
    req.onerror   = (event) => reject(event.target.error);
  });
}

// -- Write helpers ------------------------------------------------------------

/**
 * Upsert a trade entry (ticket + aar pair) into IndexedDB.
 * The `asset` field is derived from the ticketId prefix (e.g. "XAUUSD_260305_1030" -> "XAUUSD").
 */
export async function saveTradeEntry(ticket, aar) {
  if (!ticket || !ticket.ticketId) return;

  const db    = await openTradeDB();
  const entry = {
    ticketId:  ticket.ticketId,
    createdAt: ticket.createdAt || new Date().toISOString(),
    asset:     _assetFromTicketId(ticket.ticketId),
    ticket,
    aar:       aar || null,
  };

  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const req   = store.put(entry);
    req.onsuccess = () => resolve();
    req.onerror   = (e) => reject(e.target.error);
  });
}

/**
 * Delete a single trade entry by ticketId.
 */
export async function deleteTradeEntry(ticketId) {
  const db = await openTradeDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const req   = store.delete(ticketId);
    req.onsuccess = () => resolve();
    req.onerror   = (e) => reject(e.target.error);
  });
}

/**
 * Remove all entries from the trades store.
 */
export async function clearTradeHistory() {
  const db = await openTradeDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const req   = store.clear();
    req.onsuccess = () => resolve();
    req.onerror   = (e) => reject(e.target.error);
  });
}

// -- Read helpers -------------------------------------------------------------

/**
 * Return the total number of entries in the trade store.
 */
export async function getTradeCount() {
  const db = await openTradeDB();
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readonly');
    const store = tx.objectStore(STORE);
    const req   = store.count();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

/**
 * Load a page of trade history, ordered by createdAt ascending.
 *
 * @param {string|null} afterCursor - createdAt ISO string from previous page's
 *   last entry; pass null to start from the beginning.
 * @param {number} [limit=50] - Maximum entries to return.
 * @returns {Promise<{ entries: object[], nextCursor: string|null }>}
 *   nextCursor is the createdAt of the last returned entry, or null when
 *   the end of the store has been reached.
 */
export async function loadTradeHistoryPage(afterCursor = null, limit = 50) {
  const db = await openTradeDB();

  return new Promise((resolve, reject) => {
    const tx      = db.transaction(STORE, 'readonly');
    const index   = tx.objectStore(STORE).index('createdAt');

    // Build a key range: if we have a cursor, open a range strictly after it.
    const range = afterCursor
      ? IDBKeyRange.lowerBound(afterCursor, /* exclusive= */ true)
      : null;

    const entries = [];
    const req = index.openCursor(range, 'next');

    req.onsuccess = (event) => {
      const cursor = event.target.result;
      if (!cursor || entries.length >= limit) {
        const nextCursor = entries.length === limit
          ? entries[entries.length - 1].createdAt
          : null;
        resolve({ entries, nextCursor });
        return;
      }
      entries.push(cursor.value);
      cursor.continue();
    };

    req.onerror = (e) => reject(e.target.error);
  });
}

/**
 * Load the full trade history (all entries), ordered by createdAt ascending.
 * Suitable for small datasets; prefer loadTradeHistoryPage for large journals.
 */
export async function loadAllTradeHistory() {
  const db = await openTradeDB();

  return new Promise((resolve, reject) => {
    const tx    = db.transaction(STORE, 'readonly');
    const index = tx.objectStore(STORE).index('createdAt');
    const req   = index.getAll();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

// -- Current-session state (unchanged from Phase 1-3) ------------------------

/**
 * Load the current session state from localStorage.
 * (Trade journal history lives in IndexedDB; single-session state stays in localStorage.)
 */
export async function loadStateIndexedDb() {
  return loadLocalState();
}

/**
 * Save the current session state to localStorage.
 */
export async function saveStateIndexedDb(state) {
  return saveLocalState(state);
}

// -- Private helpers ----------------------------------------------------------

/**
 * Extract the instrument symbol from a ticketId like "XAUUSD_260305_1030".
 * Falls back to 'UNKNOWN' if the format is unexpected.
 */
function _assetFromTicketId(ticketId) {
  if (!ticketId) return 'UNKNOWN';
  const parts = ticketId.split('_');
  return parts.length > 0 ? parts[0] : 'UNKNOWN';
}
