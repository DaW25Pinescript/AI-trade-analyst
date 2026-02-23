export const state = {
  currentStep: 0,
  currentBias: '',
  ticketID: '',
  uploads: { htf: null, mid: null, ltf: null, exec: null },
  imgSrcs: { htf: '', mid: '', ltf: '', exec: '' },
  ptcState: {
    htfState: '', htfLocation: '', ltfAlignment: '', liquidityContext: '',
    volRisk: '', execQuality: '', conviction: '', edgeTag: ''
  }
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
