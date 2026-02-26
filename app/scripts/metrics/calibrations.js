// Calibration helper functions.

const CLOSED_OUTCOMES = new Set(['WIN', 'LOSS', 'BREAKEVEN', 'SCRATCH']);

export function buildCalibrationInputs(tickets = [], aars = []) {
  const ticketById = new Map(tickets.map((t) => [t.ticketId, t]));

  return aars
    .filter((aar) => CLOSED_OUTCOMES.has(aar?.outcomeEnum))
    .map((aar) => ({
      ticketId: aar.ticketId,
      confluenceScore: ticketById.get(aar.ticketId)?.checklist?.confluenceScore ?? null,
      revisedConfidence: aar.revisedConfidence ?? null,
      outcomeEnum: aar.outcomeEnum,
      rAchieved: aar.rAchieved ?? null,
    }));
}
