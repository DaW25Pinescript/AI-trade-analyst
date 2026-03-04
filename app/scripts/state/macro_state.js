export const macroState = {
  context: null,
  eventBatch: null,
  sourceHealth: {},
  observability: {
    lastUpdated: null,
    feederStatus: 'unknown',
    warningCount: 0
  }
};

function buildObservability(payload) {
  const warnings = Array.isArray(payload?.warnings) ? payload.warnings : [];
  return {
    lastUpdated: payload?.generated_at ?? null,
    feederStatus: payload?.status ?? 'unknown',
    warningCount: warnings.length
  };
}

export function hydrateMacroState(payload) {
  macroState.context = payload?.macro_context ?? null;
  macroState.eventBatch = {
    contractVersion: payload?.contract_version ?? '1.0.0',
    generatedAt: payload?.generated_at ?? null,
    events: Array.isArray(payload?.events) ? payload.events : []
  };
  macroState.sourceHealth = payload?.source_health ?? {};
  macroState.observability = buildObservability(payload);
  return macroState;
}

export async function loadMacroSnapshot(url = './data/macro_snapshot.json') {
  const response = await fetch(url, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Failed to load macro snapshot (${response.status})`);
  }
  const payload = await response.json();
  return hydrateMacroState(payload);
}
