export function bindShortcuts({ goTo, buildAndShow }) {
  document.addEventListener('keydown', (event) => {
    if (event.ctrlKey && event.key === 'Enter') {
      event.preventDefault();
      buildAndShow();
    }
    if (event.altKey && ['1','2','3','4','5','6'].includes(event.key)) {
      event.preventDefault();
      goTo(Number(event.key) - 1);
    }
  });
}
