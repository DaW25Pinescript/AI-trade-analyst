export const state = {
  currentStep: 0,
  currentBias: '',
  ticketID: '',
  // Lens-aware screenshot slots:
  //   htf        — 4H/1H clean price chart (HTF bias)
  //   m15        — 15M clean price chart (market structure)
  //   m5         — 5M clean price chart (entry context)
  //   m15overlay — 15M ICT overlay (optional, secondary evidence)
  //   m15structure — 15M market structure overlay
  //   m15trendline — 15M trendline overlay
  //   customoverlay — custom indicator overlay (any timeframe)
  uploads: { htf: null, m15: null, m5: null, m15overlay: null, m15structure: null, m15trendline: null, customoverlay: null },
  imgSrcs: { htf: '', m15: '', m5: '', m15overlay: '', m15structure: '', m15trendline: '', customoverlay: '' },
  overlayEnabled: false,
  ptcState: {
    htfState: '', htfLocation: '', ltfAlignment: '', liquidityContext: '',
    volRisk: '', execQuality: '', conviction: '', edgeTag: ''
  },
  aarState: {
    firstTouch: null,
    wouldHaveWon: null,
    killSwitch: null,
    photoDataUrl: ''
  },
  // G8: tracks the parent ticket ID when this is a revision
  revisedFromId: null
};

export function generateTicketID() {
  const asset = (document.getElementById('asset').value || 'XXXXXX').toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,6);
  const now = new Date();
  const y = now.getFullYear().toString().slice(2);
  const mo = String(now.getMonth()+1).padStart(2,'0');
  const d = String(now.getDate()).padStart(2,'0');
  const h = String(now.getHours()).padStart(2,'0');
  const mi = String(now.getMinutes()).padStart(2,'0');
  state.ticketID = `${asset}_${y}${mo}${d}_${h}${mi}`;
  document.getElementById('ticketIdHeader').textContent = state.ticketID;
  return state.ticketID;
}
