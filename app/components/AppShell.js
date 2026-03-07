/**
 * AppShell — Top-level layout wrapper
 *
 * Provides the app-level navigation bar and content area.
 * Routes are handled by hash-based navigation (#/dashboard, #/journey/:asset, etc.)
 */

/**
 * Renders the AppShell into the given container.
 * @param {HTMLElement} container
 * @param {Object} options
 * @param {string} options.currentRoute
 */
export function renderAppShell(container, { currentRoute = 'dashboard' } = {}) {
  container.innerHTML = '';
  container.className = 'app-shell';

  // Navigation bar
  const nav = document.createElement('nav');
  nav.className = 'app-nav';
  nav.innerHTML = `
    <div class="app-nav__brand">
      <span class="app-nav__logo">AI</span>
      <span class="app-nav__title">Trade Analyst</span>
    </div>
    <div class="app-nav__links">
      <a href="#/dashboard" class="app-nav__link ${currentRoute === 'dashboard' ? 'app-nav__link--active' : ''}" data-route="dashboard">Dashboard</a>
      <a href="#/journal" class="app-nav__link ${currentRoute === 'journal' ? 'app-nav__link--active' : ''}" data-route="journal">Journal</a>
      <a href="#/review" class="app-nav__link ${currentRoute === 'review' ? 'app-nav__link--active' : ''}" data-route="review">Review</a>
    </div>
    <div class="app-nav__meta">
      <span class="app-nav__status badge badge--ai-prefill">v1 Journey</span>
    </div>
  `;
  container.appendChild(nav);

  // Main content area
  const main = document.createElement('main');
  main.className = 'app-main';
  main.id = 'app-main';
  container.appendChild(main);

  return main;
}
