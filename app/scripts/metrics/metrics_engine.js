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

function toIsoDate(value) {
  const d = new Date(value || '');
  return Number.isNaN(d.getTime()) ? null : d;
}

function periodKey(date, kind) {
  const year = date.getUTCFullYear();
  if (kind === 'monthly') {
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
  }
  const quarter = Math.floor(date.getUTCMonth() / 3) + 1;
  return `${year}-Q${quarter}`;
}

function buildPeriodBreakdown(closed, kind) {
  const buckets = new Map();
  closed.forEach((entry) => {
    const created = toIsoDate(entry.ticket?.createdAt);
    if (!created) return;
    const key = periodKey(created, kind);
    const r = Number(entry.aar?.rAchieved ?? 0);
    const bucket = buckets.get(key) || { period: key, trades: 0, wins: 0, netR: 0 };
    bucket.trades += 1;
    bucket.wins += r > 0 ? 1 : 0;
    bucket.netR += r;
    buckets.set(key, bucket);
  });

  return [...buckets.values()]
    .sort((a, b) => a.period.localeCompare(b.period))
    .map((bucket) => ({
      ...bucket,
      winRate: bucket.trades ? bucket.wins / bucket.trades : 0,
      avgR: bucket.trades ? bucket.netR / bucket.trades : 0,
    }));
}

function buildEquityCurve(closed) {
  let cumulativeR = 0;
  return [...closed]
    .sort((a, b) => {
      const left = toIsoDate(a.ticket?.createdAt)?.getTime() ?? 0;
      const right = toIsoDate(b.ticket?.createdAt)?.getTime() ?? 0;
      return left - right;
    })
    .map((entry) => {
      const r = Number(entry.aar?.rAchieved ?? 0);
      cumulativeR += r;
      return {
        ticketId: entry.ticket?.ticketId || 'UNKNOWN',
        timestamp: entry.ticket?.createdAt || null,
        r,
        cumulativeR,
      };
    });
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
    equityCurve: buildEquityCurve(closed),
    monthlyBreakdown: buildPeriodBreakdown(closed, 'monthly'),
    quarterlyBreakdown: buildPeriodBreakdown(closed, 'quarterly'),
    calibration: buildCalibrationInputs(
      combined.map(({ ticket }) => ticket),
      combined.map(({ aar }) => aar)
    ),
  };
}
