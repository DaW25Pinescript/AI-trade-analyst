// Calibration helper functions.

export function buildCalibrationInputs(closedTickets = [], aars = []) {
  const aarByTicket = new Map(aars.map((aar) => [aar.ticketId, aar]));

  return closedTickets.map((ticket) => {
    const aar = aarByTicket.get(ticket.ticketId);
    return {
      ticketId: ticket.ticketId,
      confluenceScore: ticket.confluenceScore ?? null,
      revisedConfidence: aar?.revisedConfidence ?? null,
      resultR: ticket.resultR ?? null,
    };
  });
}
