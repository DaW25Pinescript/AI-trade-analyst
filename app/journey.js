/**
 * Journey Entry Point — Trade Ideation Journey v1
 *
 * Initializes the app shell, router, and renders the initial route.
 */

import { renderAppShell } from './components/AppShell.js';
import { route, notFound, startRouter, navigate } from './lib/router.js';
import { renderDashboardPage } from './pages/DashboardPage.js';
import { renderJourneyPage } from './pages/JourneyPage.js';
import { renderJournalPage } from './pages/JournalPage.js';
import { renderReviewPage } from './pages/ReviewPage.js';

function init() {
  const root = document.getElementById('journey-root');
  if (!root) {
    console.error('[journey] #journey-root element not found.');
    return;
  }

  // Render app shell and get main content area
  const currentRoute = _getCurrentRoute();
  const main = renderAppShell(root, { currentRoute });

  // Register routes
  route('/dashboard', ({ container }) => {
    _setActiveNav('dashboard');
    renderDashboardPage(container);
  });

  route('/journey/:asset', ({ params, container }) => {
    _setActiveNav('journey');
    renderJourneyPage(container, params.asset);
  });

  route('/journal', ({ container }) => {
    _setActiveNav('journal');
    renderJournalPage(container);
  });

  route('/review', ({ container }) => {
    _setActiveNav('review');
    renderReviewPage(container);
  });

  notFound(({ container }) => {
    container.innerHTML = '<div class="not-found"><h2>Page not found</h2><a href="#/dashboard">Return to Dashboard</a></div>';
  });

  // Start router
  startRouter(main);
}

function _getCurrentRoute() {
  const hash = window.location.hash.slice(2) || 'dashboard';
  if (hash.startsWith('journey')) return 'journey';
  return hash;
}

function _setActiveNav(routeName) {
  document.querySelectorAll('.app-nav__link').forEach(link => {
    link.classList.toggle('app-nav__link--active', link.dataset.route === routeName);
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
