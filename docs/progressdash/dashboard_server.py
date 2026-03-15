#!/usr/bin/env python3
"""
Live Dashboard Server
Watches your progress/spec markdown files and serves a live-updating dashboard.

How it works (analogy: like a security camera feed):
  - The server watches your markdown files for changes
  - When a file changes, it re-parses and regenerates the dashboard
  - Your browser auto-refreshes to show the latest state
  - No manual regeneration needed — just edit your files and watch the dashboard update

Usage:
    python dashboard_server.py --progress path/to/Progress.md --specs path/to/specs/
    python dashboard_server.py --folder path/to/docs/    # auto-discover files recursively

    Then open http://localhost:9090 in your browser.

Options:
    --port PORT      Server port (default: 9090)
    --progress PATH  Path to progress markdown file
    --specs PATH     Paths to spec files or directories
    --folder PATH    Auto-discover files under folder (curated recursive scan)
    --watch          Enable file watching (default: on)
    --no-watch       Disable file watching (serve static)
"""

import os
import sys
import json
import time
import hashlib
import argparse
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

# Add parent dir to path so we can import the generator
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# Try to import the generator — look in same dir or parent
try:
    from generate_dashboard import (
        parse_progress_file,
        parse_spec_file,
        generate_html,
        ProjectDashboard,
    )
except ImportError:
    # Try parent directory
    sys.path.insert(0, str(SCRIPT_DIR.parent))
    from generate_dashboard import (
        parse_progress_file,
        parse_spec_file,
        generate_html,
        ProjectDashboard,
    )


EXCLUDED_DIR_NAMES = {
    '.git',
    '__pycache__',
    'node_modules',
    '.venv',
    'venv',
    'dist',
    'build',
    'archive',
    '.archive',
}
PROGRESS_PATTERNS = ('*Progress*.md', '*progress*.md')
SPEC_PATTERNS = ('*SPEC*.md', '*spec*.md')
PREFERRED_PROGRESS_FILENAMES = {
    'ai_tradeanalyst_progress.md',
    'ai_trade_analyst_progress.md',
}


def _is_excluded_path(path: Path) -> bool:
    return any(part.lower() in EXCLUDED_DIR_NAMES for part in path.parts)


def _discover_recursive(root: Path, patterns) -> list[Path]:
    matches = []
    for pattern in patterns:
        for p in root.rglob(pattern):
            if p.is_file() and not _is_excluded_path(p):
                matches.append(p)
    return sorted(set(matches), key=lambda p: str(p).lower())


def _pick_progress_file(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    preferred = [p for p in candidates if p.name.lower() in PREFERRED_PROGRESS_FILENAMES]
    if preferred:
        return sorted(preferred, key=lambda p: str(p).lower())[0]
    return sorted(candidates, key=lambda p: str(p).lower())[0]


def _resolve_specs(inputs) -> list[str]:
    resolved: list[Path] = []
    for item in inputs or []:
        p = Path(item)
        if p.is_dir():
            resolved.extend(_discover_recursive(p, SPEC_PATTERNS))
        elif p.exists() and p.is_file():
            resolved.append(p)
    return [str(p) for p in sorted(set(resolved), key=lambda p: str(p).lower())]


def _auto_discover_from_folder(folder: Path) -> tuple[str | None, list[str], dict]:
    progress_candidates = _discover_recursive(folder, PROGRESS_PATTERNS)
    spec_candidates = _discover_recursive(folder, SPEC_PATTERNS)
    progress = _pick_progress_file(progress_candidates)
    summary = {
        'folder': str(folder),
        'progress_candidates': [str(p) for p in progress_candidates],
        'selected_progress': str(progress) if progress else None,
        'spec_candidates': [str(p) for p in spec_candidates],
        'excluded_dir_names': sorted(EXCLUDED_DIR_NAMES),
    }
    return (str(progress) if progress else None, [str(p) for p in spec_candidates], summary)


class DashboardState:
    """Holds current dashboard state and watches for file changes."""

    def __init__(self, progress_path, spec_inputs=None):
        self.progress_path = progress_path
        self.spec_inputs = spec_inputs or []
        self.spec_paths = _resolve_specs(self.spec_inputs)
        self.html_cache = ''
        self.last_hashes = {}
        self.last_generated = None
        self.lock = threading.Lock()
        self.regenerate()

    def _file_hash(self, path):
        """Get hash of file contents for change detection."""
        try:
            with open(path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def _refresh_spec_paths(self):
        self.spec_paths = _resolve_specs(self.spec_inputs)

    def check_for_changes(self):
        """Check if any watched files have changed. Returns True if regeneration needed."""
        self._refresh_spec_paths()
        current_hashes = {}
        current_hashes[self.progress_path] = self._file_hash(self.progress_path)
        for sp in self.spec_paths:
            current_hashes[sp] = self._file_hash(sp)

        if current_hashes != self.last_hashes:
            self.last_hashes = current_hashes
            return True
        return False

    def regenerate(self):
        """Re-parse files and regenerate the dashboard HTML."""
        with self.lock:
            try:
                self._refresh_spec_paths()
                dashboard = parse_progress_file(self.progress_path)
                for sp in self.spec_paths:
                    spec = parse_spec_file(str(sp))
                    if spec:
                        dashboard.specs.append(spec)

                self.html_cache = generate_html(dashboard)
                self.last_generated = datetime.now()
                self.last_hashes = {self.progress_path: self._file_hash(self.progress_path)}
                for sp in self.spec_paths:
                    self.last_hashes[sp] = self._file_hash(sp)

                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] Dashboard regenerated "
                    f"({len(dashboard.phases)} phases, {len(dashboard.specs)} specs)"
                )
                return True
            except Exception as e:
                print(f'[ERROR] Failed to regenerate: {e}')
                return False

    def get_html(self):
        """Get current dashboard HTML (thread-safe)."""
        with self.lock:
            return self.html_cache

    def get_api_data(self):
        """Get current dashboard data as JSON for live updates."""
        with self.lock:
            try:
                self._refresh_spec_paths()
                dashboard = parse_progress_file(self.progress_path)
                for sp in self.spec_paths:
                    spec = parse_spec_file(str(sp))
                    if spec:
                        dashboard.specs.append(spec)

                from dataclasses import asdict
                total_phases = len(dashboard.phases)
                completed = sum(1 for p in dashboard.phases if p.status == 'complete')

                return json.dumps({
                    'repo': dashboard.repo,
                    'last_updated': dashboard.last_updated,
                    'current_phase': dashboard.current_phase,
                    'next_actions': dashboard.next_actions,
                    'completion_pct': round(completed / total_phases * 100) if total_phases else 0,
                    'completed_phases': completed,
                    'total_phases': total_phases,
                    'phases': [asdict(p) for p in dashboard.phases],
                    'specs': [{**asdict(s), 'acceptance_criteria': [asdict(ac) for ac in s.acceptance_criteria]} for s in dashboard.specs],
                    'tech_debt': [asdict(d) for d in dashboard.tech_debt],
                    'test_milestones': [asdict(t) for t in dashboard.test_milestones],
                    'timestamp': datetime.now().isoformat(),
                })
            except Exception as e:
                return json.dumps({'error': str(e)})


# File watcher thread
def watch_files(state, interval=2):
    """Background thread that watches files for changes and triggers regeneration."""
    print(f'[WATCHER] Monitoring files every {interval}s...')
    while True:
        time.sleep(interval)
        if state.check_for_changes():
            print('[WATCHER] File change detected — regenerating...')
            state.regenerate()


# HTTP Handler
def make_handler(state):
    class DashboardHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/index.html':
                html = state.get_html()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))

            elif self.path == '/api/dashboard':
                data = state.get_api_data()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data.encode('utf-8'))

            elif self.path == '/api/health':
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'ok',
                    'last_generated': state.last_generated.isoformat() if state.last_generated else None,
                    'watching': [state.progress_path] + state.spec_paths,
                }).encode('utf-8'))

            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            # Suppress noisy request logs, only show errors
            if args and '404' in str(args[0]):
                super().log_message(format, *args)

    return DashboardHandler


def main():
    parser = argparse.ArgumentParser(description='Live Dashboard Server')
    parser.add_argument('--progress', '-p', help='Path to progress markdown file')
    parser.add_argument('--specs', '-s', nargs='*', help='Paths to spec files or directory')
    parser.add_argument('--folder', '-f', help='Auto-discover files in folder')
    parser.add_argument('--port', type=int, default=9090, help='Server port (default: 9090)')
    parser.add_argument('--no-watch', action='store_true', help='Disable file watching')
    args = parser.parse_args()

    discovery_summary = None

    # Auto-discovery
    if args.folder:
        folder = Path(args.folder)
        args.progress, args.specs, discovery_summary = _auto_discover_from_folder(folder)
        if not args.progress:
            print('ERROR: No progress file found in folder or subfolders')
            sys.exit(1)
        print(f'Auto-discovered progress: {args.progress}')
        print(f'Auto-discovered specs ({len(args.specs)}):')
        for sp in args.specs:
            print(f'  - {sp}')

    if not args.progress:
        print('ERROR: Please provide --progress or --folder')
        sys.exit(1)

    # Initialize state
    state = DashboardState(args.progress, args.specs or [])

    # Start file watcher
    if not args.no_watch:
        watcher = threading.Thread(target=watch_files, args=(state,), daemon=True)
        watcher.start()

    # Start HTTP server
    handler = make_handler(state)
    server = HTTPServer(('0.0.0.0', args.port), handler)

    print(f"\n{'='*60}")
    print('  Project Dashboard Server')
    print(f'  Open: http://localhost:{args.port}')
    print(f'  API:  http://localhost:{args.port}/api/dashboard')
    print(f'  Watching: {args.progress}')
    for sp in state.spec_paths:
        print(f'           {sp}')
    if discovery_summary:
        print(f"  Discovery root: {discovery_summary['folder']}")
        print(f"  Excluding dirs: {', '.join(discovery_summary['excluded_dir_names'])}")
    print(f"  File watching: {'ON' if not args.no_watch else 'OFF'}")
    print(f"{'='*60}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()
