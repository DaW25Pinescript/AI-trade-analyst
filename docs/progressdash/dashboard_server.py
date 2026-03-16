#!/usr/bin/env python3
"""
AI Trade Analyst — Dashboard Server (v2)

Serves a live-regenerated dashboard from a repo/docs folder.
On every page request, re-runs generate_dashboard.py so you always see
the latest state of your Markdown files.
"""

from __future__ import annotations

import argparse
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def locate_docs_folder(start: Path) -> Path | None:
    """Search current dir, script dir, and parents for a docs folder."""
    checked: list[Path] = []
    for base in [start, Path(__file__).resolve().parent]:
        current = base.resolve()
        for _ in range(12):
            if current in checked:
                break
            checked.append(current)
            candidate = current / "docs"
            if candidate.is_dir():
                return candidate
            if current.parent == current:
                break
            current = current.parent
    return None


def locate_generator_script(start: Path) -> Path | None:
    for base in [start, Path(__file__).resolve().parent]:
        current = base.resolve()
        for _ in range(12):
            candidate = current / "generate_dashboard.py"
            if candidate.is_file():
                return candidate
            if current.parent == current:
                break
            current = current.parent
    local = Path(__file__).resolve().parent / "generate_dashboard.py"
    return local if local.is_file() else None


def check_pyyaml() -> bool:
    """Check if PyYAML is available."""
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Trade Analyst Dashboard Server v2")
    parser.add_argument("--port", type=int, default=9090)
    parser.add_argument("--folder", type=str, default="", help="Optional docs folder override")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = Path.cwd()
    docs_root = Path(args.folder).resolve() if args.folder else locate_docs_folder(cwd)
    generator_path = locate_generator_script(cwd)

    if docs_root is None:
        print("[ERROR] Could not find a 'docs' folder.")
        print("        Pass --folder explicitly or run from inside the repo.")
        return 1
    if not docs_root.is_dir():
        print(f"[ERROR] Docs folder is not valid: {docs_root}")
        return 1
    if generator_path is None:
        print("[ERROR] Could not find generate_dashboard.py.")
        print("        Place it next to this script or in the repo root.")
        return 1

    # Check PyYAML
    if not check_pyyaml():
        print("[WARN] PyYAML is not installed. Frontmatter parsing will use a limited fallback.")
        print("       Install with:  pip install pyyaml")
        print()

    os.chdir(docs_root)
    print(f"[INFO] Serving docs folder: {docs_root}")
    print(f"[INFO] Using generator:     {generator_path}")

    class DashboardHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *log_args):
            """Quieter logging — only show errors and dashboard regeneration."""
            if log_args and isinstance(log_args[0], str) and log_args[0].startswith("GET"):
                return  # suppress routine GET logs
            super().log_message(format, *log_args)

        def do_GET(self) -> None:  # noqa: N802
            request_path = urlparse(self.path).path
            if request_path in ("/", "/index.html", "/dashboard.html"):
                output_html = docs_root / "dashboard.html"
                print("[INFO] Regenerating dashboard...")
                try:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(generator_path),
                            "--folder", str(docs_root),
                            "--output", str(output_html),
                        ],
                        cwd=str(generator_path.parent),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout.strip():
                        for line in result.stdout.strip().splitlines():
                            print(f"  {line}")
                except subprocess.CalledProcessError as exc:
                    stderr = exc.stderr.strip() or exc.stdout.strip() or str(exc)
                    print(f"[WARN] Generator failed:\n{stderr}")
                    if output_html.exists():
                        print("[WARN] Serving stale dashboard.html as fallback")
                        self.path = "/dashboard.html"
                        return super().do_GET()
                    self.send_response(500)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    body = (
                        "<!DOCTYPE html><html><head><title>Error</title>"
                        "<style>body{background:#0f1117;color:#e8eaf0;font-family:sans-serif;padding:40px}"
                        "pre{background:#1a1d27;padding:16px;border-radius:8px;overflow:auto;max-width:900px;margin:20px auto}</style></head>"
                        f"<body><h1 style='color:#f87171'>Dashboard generation failed</h1><pre>{stderr}</pre></body></html>"
                    )
                    self.wfile.write(body.encode("utf-8"))
                    return
                self.path = "/dashboard.html"
            return super().do_GET()

    with ReusableTCPServer(("", args.port), DashboardHandler) as httpd:
        print()
        print(f"  Dashboard live at  http://localhost:{args.port}")
        print(f"  Refresh browser  = instant regeneration from Markdown")
        print(f"  Press Ctrl+C to stop.")
        print()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
