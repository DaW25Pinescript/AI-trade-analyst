#!/usr/bin/env python3
"""Serve a live-regenerated dashboard from a repo/docs folder."""

from __future__ import annotations

import argparse
import http.server
import os
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Trade Analyst Fancy Dashboard")
    parser.add_argument("--port", type=int, default=9090)
    parser.add_argument("--folder", type=str, default="", help="Optional docs folder override")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cwd = Path.cwd()
    docs_root = Path(args.folder).resolve() if args.folder else locate_docs_folder(cwd)
    generator_path = locate_generator_script(cwd)

    if docs_root is None:
        print("[ERROR] Could not find a 'docs' folder. Pass --folder explicitly or run from inside the repo.")
        return 1
    if not docs_root.is_dir():
        print(f"[ERROR] docs folder is not valid: {docs_root}")
        return 1
    if generator_path is None:
        print("[ERROR] Could not find generate_dashboard.py.")
        return 1

    os.chdir(docs_root)
    print(f"[INFO] Serving docs folder: {docs_root}")
    print(f"[INFO] Using generator:   {generator_path}")

    class DashboardHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request_path = urlparse(self.path).path
            if request_path in ("/", "/index.html", "/dashboard.html"):
                output_html = docs_root / "dashboard.html"
                print("[INFO] Regenerating dashboard from latest markdown files...")
                try:
                    result = subprocess.run(
                        [sys.executable, str(generator_path), "--folder", str(docs_root), "--output", str(output_html)],
                        cwd=str(generator_path.parent),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    if result.stdout.strip():
                        print(result.stdout.strip())
                    print("[OK] Dashboard regenerated successfully")
                except subprocess.CalledProcessError as exc:
                    stderr = exc.stderr.strip() or exc.stdout.strip() or str(exc)
                    print(f"[WARN] Generator failed: {stderr}")
                    if output_html.exists():
                        print("[WARN] Serving existing dashboard.html fallback")
                        self.path = "/dashboard.html"
                        return super().do_GET()
                    self.send_response(500)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    self.end_headers()
                    message = (
                        "<h1 style='color:#f87171;text-align:center;margin-top:50px;'>"
                        "Dashboard generation failed</h1>"
                        f"<pre style='max-width:900px;margin:20px auto;padding:16px;background:#111827;color:#e5e7eb;white-space:pre-wrap;'>{stderr}</pre>"
                    )
                    self.wfile.write(message.encode("utf-8"))
                    return
                self.path = "/dashboard.html"
            return super().do_GET()

    with ReusableTCPServer(("", args.port), DashboardHandler) as httpd:
        print(f"[OK] FANCY DASHBOARD LIVE at http://localhost:{args.port}")
        print("   - Refresh = instant update from your MD files")
        print("   - Archive folder is skipped by the generator")
        print("   Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
