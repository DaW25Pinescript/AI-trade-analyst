/**
 * Router — Hash-based navigation for the Trade Ideation Journey
 *
 * Routes:
 * - #/dashboard → Triage board landing
 * - #/journey/:asset → Staged ideation flow
 * - #/journal → Saved ideas and results
 * - #/review → Review/pattern analysis
 */

/** @type {Map<string, Function>} */
const _routes = new Map();

/** @type {Function|null} */
let _notFoundHandler = null;

/**
 * Register a route handler.
 * @param {string} pattern - Route pattern (e.g. '/dashboard', '/journey/:asset')
 * @param {Function} handler - Called with { params, container }
 */
export function route(pattern, handler) {
  _routes.set(pattern, handler);
}

/**
 * Register a 404 handler.
 * @param {Function} handler
 */
export function notFound(handler) {
  _notFoundHandler = handler;
}

/**
 * Navigate to a route.
 * @param {string} path
 */
export function navigate(path) {
  window.location.hash = path;
}

/**
 * Start the router. Listens to hashchange events.
 * @param {HTMLElement} container - The main content container
 */
export function startRouter(container) {
  function handleRoute() {
    const hash = window.location.hash.slice(1) || '/dashboard';
    const { handler, params } = _matchRoute(hash);

    if (handler) {
      handler({ params, container });
    } else if (_notFoundHandler) {
      _notFoundHandler({ params: {}, container });
    }
  }

  window.addEventListener('hashchange', handleRoute);
  handleRoute(); // initial load
}

function _matchRoute(path) {
  for (const [pattern, handler] of _routes) {
    const params = _extractParams(pattern, path);
    if (params !== null) {
      return { handler, params };
    }
  }
  return { handler: null, params: {} };
}

function _extractParams(pattern, path) {
  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = path.split('/').filter(Boolean);

  if (patternParts.length !== pathParts.length) return null;

  const params = {};
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) {
      params[patternParts[i].slice(1)] = pathParts[i];
    } else if (patternParts[i] !== pathParts[i]) {
      return null;
    }
  }
  return params;
}
