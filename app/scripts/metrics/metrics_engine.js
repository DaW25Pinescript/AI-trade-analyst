// Metrics engine entrypoint.
// Keep this file as the stable public API for dashboard/report metrics.

import { buildCalibrationInputs } from './calibrations.js';

export function computeMetrics(tickets = [], aars = []) {
  const closed = tickets.filter((ticket) => ticket?.status === 'closed');
  const wins = closed.filter((ticket) => (ticket?.resultR ?? 0) > 0).length;
  const winRate = closed.length ? wins / closed.length : 0;
  const expectancy = closed.length
    ? closed.reduce((sum, ticket) => sum + (ticket?.resultR ?? 0), 0) / closed.length
    : 0;

  return {
    tradeCount: closed.length,
    winRate,
    expectancy,
    calibration: buildCalibrationInputs(closed, aars),
  };
}
