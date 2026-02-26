/**
 * promptGenerator.js — Analyst Prompt Template Generator
 *
 * Produces structured prompts that guarantee each analyst AI call returns
 * a JSON object matching the analystOutputs shape required by the Senate Arbiter.
 */

/**
 * generateAnalystPromptTemplate
 *
 * @param {string} agentRole  One of: "TechnicalAnalyst", "MacroContextAnalyst", "RiskAnalyst"
 * @param {Object} context    Chart and market context passed to the analyst
 * @param {string} context.instrument     e.g. "XAUUSD"
 * @param {string[]} context.timeframes   e.g. ["H4", "H1", "M15", "M5"]
 * @param {string[]} context.screenshots  Screenshot identifiers/labels attached
 * @param {string} [context.regime]       Market regime
 * @param {string} [context.session]      Trading session
 * @param {string} [context.news]         News context
 * @returns {string}  Full structured prompt string
 */
export function generateAnalystPromptTemplate(agentRole, context) {
  const {
    instrument   = '[INSTRUMENT NOT SET]',
    timeframes   = [],
    screenshots  = [],
    regime       = 'Not specified',
    session      = 'Not specified',
    news         = 'None known'
  } = context || {};

  const tfList = timeframes.length > 0
    ? timeframes.map(tf => `  • ${tf}`).join('\n')
    : '  • (not specified)';

  const screenshotList = screenshots.length > 0
    ? screenshots.map((s, i) => `  ${i + 1}. ${s}`).join('\n')
    : '  (none listed — use charts provided in this message)';

  const roleDescriptions = {
    TechnicalAnalyst: `You are the **Technical Analyst** on this senate panel.
Your mandate: read price structure, market structure shifts (BOS/MSS), key demand/supply zones,
liquidity pools, and entry-level confirmation signals across all provided timeframes.
You must identify the highest-probability directional bias from raw price action only.
No macro considerations. No fundamental views. Structure and price — that is your lens.`,

    MacroContextAnalyst: `You are the **Macro Context Analyst** on this senate panel.
Your mandate: assess the broader macro and intermarket context that governs directional bias.
Consider: correlations, risk-on/risk-off sentiment, news calendar impact, session context,
and any fundamental tailwinds or headwinds to the technical setup.
You do NOT call entries — you declare whether the macro environment supports, opposes,
or is neutral to a trade in the stated direction.`,

    RiskAnalyst: `You are the **Risk Analyst** on this senate panel.
Your mandate: evaluate the risk parameters of any proposed trade.
Consider: R:R viability, invalidation clarity, volatility regime suitability,
setup quality, and any conditions that would make this trade inadvisable.
Your primary output is a clear direction vote AND a set of specific no-trade conditions.
You are the last line of defence before capital is committed.`
  };

  const roleDesc = roleDescriptions[agentRole] ||
    `You are a **${agentRole}** analyst on this senate panel. Apply your domain expertise to the trade opportunity below.`;

  const outputShape = `{
  "agentId": "${agentRole}",
  "direction": "Long" | "Short" | "Wait",
  "claims": [
    "String — each claim is one specific, falsifiable assertion",
    "e.g. 'H4 structure is bullish — series of HH/HL intact'",
    "Minimum 3 claims, maximum 8"
  ],
  "evidenceTags": [
    "String — timeframe/level/screenshot reference for each piece of evidence",
    "e.g. 'H4-demand-zone-1.0820', 'M15-BOS-confirmed', 'D1-HTF-bullish-close'",
    "Minimum 2 tags, maximum 10"
  ],
  "keyLevels": {
    "poi": <Number|null>,         // Entry point of interest (price)
    "invalidation": <Number|null>, // Stop / invalidation level (price)
    "targets": [<Number>, ...]    // Take profit targets in order (array, may be empty)
  },
  "primaryScenario": "String — the main trade thesis in 1-3 sentences. Must name the setup type (pullback/breakout/reversal/sweep/FVG/OrderBlock etc.)",
  "alternativeScenario": "String — the opposing scenario or conditional: describe exactly what conditions would flip your bias or create an entry in the opposite direction",
  "confidence": <Number 0-100>,   // Your confidence in the directional call
  "uncertaintyReason": "String — the single biggest uncertainty or risk to your call",
  "noTradeConditions": [
    "String — specific, observable conditions that would make you NOT take this trade",
    "e.g. 'If volatility is abnormal at time of entry', 'If news event fires before trigger'"
  ]
}`;

  return `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SENATE ANALYST BRIEF — ${agentRole.toUpperCase()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

${roleDesc}

─── MARKET CONTEXT ─────────────────────────
Instrument:   ${instrument}
Session:      ${session}
Regime:       ${regime}
News / Events: ${news}

─── TIMEFRAMES IN SCOPE ────────────────────
${tfList}

─── CHART SCREENSHOTS PROVIDED ─────────────
${screenshotList}
(All screenshots are attached to this message)

─── YOUR MANDATE ───────────────────────────
Analyse the instrument using the charts provided.
Produce ONE directional verdict: Long, Short, or Wait.

You MUST return a valid JSON object. Every field is required.
Missing or null fields (except poi, invalidation, targets which may be null/empty)
will cause a PROCEDURAL FAIL that voids your input from the senate deliberation.

─── REQUIRED OUTPUT FORMAT ─────────────────
Return ONLY the following JSON object. No prose before or after.
All string fields must be non-empty. Replace placeholder text with your actual analysis.

${outputShape}

─── RULES OF ENGAGEMENT ────────────────────
1. Your directional vote must be one exact string: "Long", "Short", or "Wait"
2. claims[] must contain specific, observable, falsifiable assertions — not opinions
3. evidenceTags[] must reference actual timeframe/level data from the charts provided
4. keyLevels.poi and keyLevels.invalidation should be precise price levels where available
5. alternativeScenario must describe the opposing case — do not leave it as a placeholder
6. noTradeConditions must be concrete and observable — not vague ("if market moves")
7. confidence is your internal score (0–100) for your directional call only
8. uncertaintyReason is the single biggest risk to your thesis — be specific

─── REMINDER ───────────────────────────────
You are ONE voice in a three-analyst senate.
Your output is fed into a deterministic deliberation engine.
Precision and completeness of your JSON is non-negotiable.
Vague or missing fields → PROCEDURAL FAIL → your analysis is excluded.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`;
}
