# dashboard_server.py
# ============================================================
#  AI Trade Analyst — Fancy Live Dashboard Server
#  • Finds your real "docs" folder no matter where the .bat is
#  • Finds generate_dashboard.py the same way
#  • On every page load: regenerates dashboard.html from ALL Progress/SPEC files
#  • Recursive + completely skips "archive" folder
#  • Opens the beautiful interactive dashboard (not the old simple list)
# ============================================================

import argparse
import os
import http.server
import socketserver
import subprocess
import sys

def locate_docs_folder():
    """Walk UP until we find the real 'docs' folder."""
    current = os.path.abspath(os.getcwd())
    for _ in range(10):
        candidate = os.path.join(current, "docs")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None

def locate_generator_script():
    """Walk UP until we find generate_dashboard.py."""
    current = os.path.abspath(os.getcwd())
    for _ in range(10):
        candidate = os.path.join(current, "generate_dashboard.py")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


# ====================== SERVER ======================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Trade Analyst Fancy Dashboard")
    parser.add_argument("--port", type=int, default=9090)
    args = parser.parse_args()

    # Auto-find everything
    docs_root = locate_docs_folder()
    generator_path = locate_generator_script()

    if docs_root is None:
        print("❌ ERROR: Could not find a 'docs' folder anywhere above here.")
        exit(1)
    if generator_path is None:
        print("❌ ERROR: Could not find generate_dashboard.py anywhere above here.")
        exit(1)

    print(f"🔍 Found docs folder: {docs_root}")
    print(f"🔍 Found generator: {generator_path}")

    # Serve from the docs folder (so /dashboard.html works)
    os.chdir(docs_root)

    class DashboardHandler(http.server.SimpleHTTPRequestHandler):
        root_dir = docs_root
        generator_path = generator_path

        def do_GET(self):
            if self.path in ("/", "/index.html", "/dashboard.html"):
                # LIVE REGENERATE every time you open/refresh the page
                output_html = os.path.join(self.root_dir, "dashboard.html")
                print("🔄 Regenerating fancy dashboard from latest MD files...")

                try:
                    subprocess.run(
                        [sys.executable, self.generator_path,
                         "--folder", self.root_dir,
                         "--output", output_html],
                        cwd=os.path.dirname(self.generator_path),
                        check=True,
                        capture_output=True,
                        text=True
                    )
                    print("✅ Dashboard regenerated successfully")
                except subprocess.CalledProcessError as e:
                    print(f"⚠️ Generator failed: {e.stderr.strip()}")
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"<h1 style='color:red;text-align:center;margin-top:50px;'>No Progress.md file found (or parse error)</h1>")
                    return

                # Serve the freshly generated fancy dashboard
                self.path = "/dashboard.html"

            # Serve any other file (e.g. if you ever add images)
            super().do_GET()

    with socketserver.TCPServer(("", args.port), DashboardHandler) as httpd:
        print(f"✅ FANCY DASHBOARD LIVE at http://localhost:{args.port}")
        print("   • Opens automatically")
        print("   • Refresh = instant update from your MD files")
        print("   • Archive folder is skipped")
        print("   Press Ctrl+C to stop.\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped.")