const KEY = 'ai_trade_analyst_v3_state';

export function saveLocalState(state) {
  localStorage.setItem(KEY, JSON.stringify(state));
}

export function loadLocalState() {
  const raw = localStorage.getItem(KEY);
  return raw ? JSON.parse(raw) : null;
}
