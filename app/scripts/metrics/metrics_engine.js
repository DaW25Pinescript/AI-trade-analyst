// Metrics engine entrypoint.
// Keep this file as the stable public API for dashboard/report metrics.

import { buildCalibrationInputs } from './calibrations.js';

const NON_PSYCH_TAGS = new Set(['CALM', 'DISCIPLINED']);
const CLOSED_OUTCOMES = new Set(['WIN', 'LOSS', 'BREAKEVEN', 'SCRATCH']);

function deriveSessionFromTimestamp(timestamp) {
  if (!timestamp) return 'Unknown';
  const hour = new Date(timestamp).getUTCHours();
  if (Number.isNaN(hour)) return 'Unknown';
  if (hour >= 0 && hour < 6) return 'Asia';
  if (hour >= 6 && hour < 10) return 'London Open';
  if (hour >= 10 && hour < 13) return 'London Mid';
  if (hour >= 13 && hour < 16) return 'NY Open';
  if (hour >= 16 && hour < 20) return 'NY PM';
  return 'Off Hours';
}

function average(nums) {
  return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : 0;
}

export function parseBackupEntries(rawEntries = []) {
  return rawEntries
    .map((entry) => ({ ticket: entry?.ticket || null, aar: entry?.aar || null }))
    .filter((entry) => entry.ticket && entry.aar);
}

export function computeMetrics(tickets = [], aars = []) {
  const combined = tickets.map((ticket, i) => ({ ticket, aar: aars[i] })).filter((x) => x.ticket && x.aar);
  const closed = combined.filter(({ aar }) => CLOSED_OUTCOMES.has(aar?.outcomeEnum));
  const closedR = closed.map(({ aar }) => Number(aar?.rAchieved ?? 0));
  const wins = closed.filter(({ aar }) => Number(aar?.rAchieved ?? 0) > 0).length;
  const winRate = closed.length ? wins / closed.length : 0;
  const expectancy = average(closedR);

  const uniqueDays = new Set(
    combined
      .map(({ ticket }) => (ticket?.createdAt || '').slice(0, 10))
      .filter(Boolean)
  );

  const leakageTrades = combined.filter(({ aar }) => {
    const tag = aar?.psychologicalTag || 'CALM';
    const r = Number(aar?.rAchieved ?? 0);
    return !NON_PSYCH_TAGS.has(tag) && r < 0;
  });

  const setupCounts = {};
  const sessionCounts = {};
  combined.forEach(({ ticket }) => {
    const setup = ticket?.checklist?.edgeTag || 'Other';
    const session = deriveSessionFromTimestamp(ticket?.createdAt);
    setupCounts[setup] = (setupCounts[setup] || 0) + 1;
    sessionCounts[session] = (sessionCounts[session] || 0) + 1;
  });
  const topSetups = Object.entries(setupCounts).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k]) => k);
  const topSessions = Object.entries(sessionCounts).sort((a, b) => b[1] - a[1]).slice(0, 4).map(([k]) => k);
  const heatmap = topSetups.map((setup) =>
    topSessions.map((session) => {
      const count = combined.filter(({ ticket }) => {
        const ticketSetup = ticket?.checklist?.edgeTag || 'Other';
        const ticketSession = deriveSessionFromTimestamp(ticket?.createdAt);
        return ticketSetup === setup && ticketSession === session;
      }).length;
      return { setup, session, count };
    })
  );

  return {
    tradeCount: combined.length,
    closedCount: closed.length,
    winRate,
    avgR: expectancy,
    expectancy,
    avgTradesPerDay: uniqueDays.size ? combined.length / uniqueDays.size : 0,
    psychologicalLeakR: average(leakageTrades.map(({ aar }) => Math.abs(Number(aar?.rAchieved ?? 0)))),
    heatmap,
    heatmapSetups: topSetups,
    heatmapSessions: topSessions,
    calibration: buildCalibrationInputs(
      combined.map(({ ticket }) => ticket),
      combined.map(({ aar }) => aar)
    ),
  };
}
