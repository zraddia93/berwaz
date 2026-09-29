#!/usr/bin/env python3
"""
Berwaz Admin Server
Lightweight HTTP server for the Berwaz admin panel
Serves static files and provides API endpoints for configuration management
"""

import json
import os
import re
import sys
import unicodedata
import subprocess
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from io import BytesIO

# Configuration
PORT = 8420
CONFIG_FILE = "berwaz-config.json"
FRAMES_DATA_FILE = "frames-data.js"

# Known directors with Arabic names
DIRECTORS_MAPPING = {
    "Abdullah Algallaf": {"nameAr": "عبدالله القلاف"},
    "Abdullah Alkhamees": {"nameAr": "عبدالله الخميس"},
    "Abdullah Majed": {"nameAr": "عبدالله ماجد"},
    "Abdulrahman Elsingergy": {"nameAr": "عبدالرحمن السنجري"},
    "Ali Alkalthami": {"nameAr": "علي الكلثمي"},
    "Bader Nour": {"nameAr": "بدر نور"},
    "Fahad Alammari": {"nameAr": "فهد العماري"},
    "Faisal Alobrah": {"nameAr": "فيصل العبره"},
    "Majed Aleissa": {"nameAr": "ماجد العيسى"},
    "Malek Alhammami": {"nameAr": "مالك الحمامي"},
    "Meshal Aljasser": {"nameAr": "مشعل الجاسر"},
    "Mishary Almazyad": {"nameAr": "مشاري المزيد"},
    "Mohammad Alhamdan": {"nameAr": "محمد الحمدان"},
    "Mohammad Alharthi": {"nameAr": "محمد الحارثي"},
    "Mohammad Almulla": {"nameAr": "محمد الملا"},
    "Mohammad Alsuliman": {"nameAr": "محمد السليمان"},
}


def slugify(name):
    """Convert name to slug format (lowercase with hyphens)"""
    return name.lower().replace(" ", "-")


def extract_frames_from_js(filepath):
    """Extract FRAMES_DATA array from frames-data.js"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Match: const FRAMES_DATA = [...];
        match = re.search(r'const\s+FRAMES_DATA\s*=\s*(\[.*?\]);', content, re.DOTALL)
        if match:
            json_str = match.group(1)
            frames = json.loads(json_str)
            return frames if isinstance(frames, list) else []
    except Exception as e:
        print(f"Warning: Could not extract frames from {filepath}: {e}")

    return []


def build_config_from_migration():
    """Auto-migrate from existing data files to berwaz-config.json"""
    print("Starting config migration...")

    config = {
        "directors": [],
        "frames": [],
        "filterTags": {
            "projects": [
                "Saudi National Day",
                "Saudi Founding Day",
                "Commercial Films",
                "Branding Films"
            ]
        },
        "projectCategories": {}
    }

    # Build directors list
    for director_name, director_info in DIRECTORS_MAPPING.items():
        director = {
            "id": slugify(director_name),
            "name": director_name,
            "nameAr": director_info["nameAr"],
            "bio": f"{director_name} is a Saudi filmmaker and director.",
            "vimeo": "",
            "instagram": "",
            "twitter": ""
        }
        config["directors"].append(director)

    # Extract frames from frames-data.js
    if os.path.exists(FRAMES_DATA_FILE):
        frames = extract_frames_from_js(FRAMES_DATA_FILE)
        config["frames"] = frames
        print(f"Migrated {len(frames)} frames from {FRAMES_DATA_FILE}")

    print(f"Migration complete: {len(config['directors'])} directors, {len(config['frames'])} frames")
    return config


def load_config():
    """Load config from file or create via migration"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None

    # Auto-migrate
    config = build_config_from_migration()
    save_config(config)
    return config


def save_config(config):
    """Save config to file"""
    try:
        # Write to a temp file then atomically replace, so a crash mid-write
        # can never leave a truncated config behind.
        tmp = CONFIG_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CONFIG_FILE)
        print(f"Config saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def slim_for_site(frames):
    """What the website actually loads: full data stays in berwaz-config.json."""
    out = []
    for f in frames:
        g = dict(f)
        px = f.get('pixels')
        if px:
            g['pixels'] = {'temp': px.get('temp'), 'tone': px.get('tone')}
        out.append(g)
    return out


def stamp_data_version():
    """Cache-bust: write frames-data.js?v=<hash> into the pages so browsers refetch new data."""
    import hashlib, re as _re
    try:
        h = hashlib.md5(open(FRAMES_DATA_FILE, 'rb').read()).hexdigest()[:10]
    except Exception:
        return
    for page in ('index.html', 'profile.html', os.path.join('directors', 'index.html')):
        path = os.path.join(".", page)
        if not os.path.exists(path):
            continue
        html = open(path, encoding='utf-8').read()
        new = _re.sub(r'(src=")((?:\.\./)?frames-data\.js)(?:\?v=[0-9a-f]+)?(")', lambda m: m.group(1) + m.group(2) + '?v=' + h + m.group(3), html)
        # same for the cloud files, so config changes are never stuck in a browser cache
        for jsname in ('cloud-config.js', 'berwaz-cloud.js'):
            jp = os.path.join(".", jsname)
            if os.path.exists(jp):
                hj = hashlib.md5(open(jp, 'rb').read()).hexdigest()[:8]
                new = _re.sub(r'(src=")(' + jsname.replace('.', '\\.') + r')(?:\?v=[0-9a-f]+)?(")', lambda m, hj=hj: m.group(1) + m.group(2) + '?v=' + hj + m.group(3), new)
        if new != html:
            open(path, 'w', encoding='utf-8').write(new)


def generate_frames_data_js(frames):
    """Generate frames-data.js from frames list"""
    try:
        # Compact JSON format - frames on single line with proper JS formatting
        frames_json = json.dumps(slim_for_site(frames), separators=(',', ':'), ensure_ascii=False)
        content = f"const FRAMES_DATA = {frames_json};"

        with open(FRAMES_DATA_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Generated {FRAMES_DATA_FILE}")
        stamp_data_version()
        return True
    except Exception as e:
        print(f"Error generating frames-data.js: {e}")
        return False


def update_js_variable(filepath, var_name, new_value_str):
    """
    Update a JavaScript variable declaration in a file.
    Matches 'const VAR_NAME = ...;' and replaces the value.
    Uses bracket/brace counting to find the correct closing delimiter.
    """
    try:
        if not os.path.exists(filepath):
            print(f"Warning: {filepath} does not exist")
            return False

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find the variable declaration
        pattern = r'(const\s+' + re.escape(var_name) + r'\s*=\s*)'
        match = re.search(pattern, content)
        if not match:
            print(f"Warning: Could not find 'const {var_name}' in {filepath}")
            return False

        start = match.end()  # position right after '= '

        # Find the matching end by counting brackets/braces
        depth = 0
        in_string = False
        string_char = None
        i = start
        while i < len(content):
            c = content[i]
            if in_string:
                if c == '\\':
                    i += 2
                    continue
                if c == string_char:
                    in_string = False
            else:
                if c in ('"', "'", '`'):
                    in_string = True
                    string_char = c
                elif c in ('[', '{'):
                    depth += 1
                elif c in (']', '}'):
                    depth -= 1
                    if depth == 0:
                        # Found the end — include the semicolon
                        end = i + 1
                        if end < len(content) and content[end] == ';':
                            end += 1
                        break
            i += 1
        else:
            print(f"Warning: Could not find closing bracket for {var_name}")
            return False

        # Replace
        new_content = content[:match.start()] + f"const {var_name} = {new_value_str};" + content[end:]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"Updated {var_name} in {filepath}")
        return True

    except Exception as e:
        print(f"Error updating {var_name} in {filepath}: {e}")
        return False


def publish_config(config):
    """Regenerate website files from config"""
    print("\nPublishing configuration...")

    success = True

    # 1. Generate frames-data.js
    if not generate_frames_data_js(config.get("frames", [])):
        success = False

    # 2. Update DIRECTORS in index.html (simple format: name + nameAr only)
    directors_simple = [
        {"name": d["name"], "nameAr": d["nameAr"]}
        for d in config.get("directors", [])
    ]
    def js_str(value):
        """Safely encode a string as a JS string literal (handles quotes, newlines, unicode)."""
        return json.dumps(str(value if value is not None else ""), ensure_ascii=False)

    directors_js = "[\n" + ",\n".join(
        f'            {{ name: {js_str(d.get("name"))}, nameAr: {js_str(d.get("nameAr"))} }}'
        for d in config.get("directors", [])
    ) + "\n        ]"
    if not update_js_variable("index.html", "DIRECTORS", directors_js):
        success = False

    # 3. Update DIRECTORS_DATA in directors/index.html (full format)
    directors_full = config.get("directors", [])
    fields = ["id", "name", "nameAr", "bio", "vimeo", "instagram", "twitter"]
    directors_data_js = "[\n" + ",\n".join(
        '            {\n' +
        ",\n".join(f'                {k}: {js_str(d.get(k, ""))}' for k in fields) +
        '\n            }'
        for d in directors_full
    ) + "\n        ]"
    if not update_js_variable("directors/index.html", "DIRECTORS_DATA", directors_data_js):
        success = False

    # 4. Update FILTER_TAGS in index.html
    filter_tags = config.get("filterTags", {})
    projects = filter_tags.get("projects", [])
    filter_js = '{{\n            projects: [{items}]\n        }}'.format(
        items=', '.join(js_str(p) for p in projects)
    )
    if not update_js_variable("index.html", "FILTER_TAGS", filter_js):
        success = False

    # 5. Update PROJECT_CATEGORIES in index.html (project name -> category).
    #    Keys are normalised to NFC: macOS filenames give decomposed Arabic (NFD)
    #    while typed input is precomposed (NFC), and a strict key match misses those.
    project_categories = config.get("projectCategories", {}) or {}
    project_categories = {
        unicodedata.normalize("NFC", str(k)): v
        for k, v in project_categories.items()
    }
    pc_js = json.dumps(project_categories, ensure_ascii=False, indent=12)
    # Re-indent closing brace to match file style
    pc_js = pc_js.replace("\n}", "\n        }") if pc_js != "{}" else "{}"
    if not update_js_variable("index.html", "PROJECT_CATEGORIES", pc_js):
        success = False

    if success:
        print("Publication complete!")
    else:
        print("Publication completed with errors")

    return success


class BerwazAdminHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for Berwaz admin server"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # API endpoint: GET /api/pipeline/status
        if path == "/api/pipeline/status":
            cfg = load_config() or {"frames": []}
            fr = cfg.get("frames", [])
            gifs = 0
            for d, _, files in os.walk("content"):
                gifs += sum(1 for x in files if x.lower().endswith(".gif"))
            status = {
                "frames": len(fr),
                "gifsOnDisk": gifs,
                "newOnDisk": max(0, gifs - len(fr)),
                "missingPrompt": sum(1 for f in fr if not (f.get("prompt") or "").strip()),
                "missingPixels": sum(1 for f in fr if not f.get("pixels")),
                "missingCraft": sum(1 for f in fr if not f.get("craft")),
                "missingArabic": sum(1 for f in fr if not f.get("sourceAr")),
                "hasApiKey": bool(os.environ.get("ANTHROPIC_API_KEY")),
                "pendingFiles": {
                    "describe_filled": os.path.exists(os.path.join("pipeline", "describe_filled.jsonl")),
                    "classify_filled": os.path.exists(os.path.join("pipeline", "classify_filled.jsonl")),
                },
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        # API endpoint: GET /api/config
        if path == "/api/config":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            config = load_config()
            if config:
                response = json.dumps(config, ensure_ascii=False)
                self.wfile.write(response.encode('utf-8'))
            else:
                self.wfile.write(b'{"error": "Could not load config"}')

        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        # API endpoint: POST /api/config
        if path == "/api/config":
            try:
                new_config = json.loads(body)
                if save_config(new_config):
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(b'{"status": "saved"}')
                else:
                    self.send_response(500)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Could not save config"}')
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(f'{{"error": "Invalid JSON: {str(e)}"}}'.encode('utf-8'))

        # API endpoint: POST /api/pipeline/<scan|pixels|prepare|merge|describe|classify|all>
        elif path.startswith("/api/pipeline/"):
            cmd = path.rsplit("/", 1)[-1]
            allowed = {"scan", "pixels", "prepare", "merge", "describe", "classify", "all", "status"}
            if cmd not in allowed:
                self.send_response(400); self.send_header("Content-type", "application/json"); self.end_headers()
                self.wfile.write(b'{"error": "unknown pipeline command"}'); return
            try:
                proc = subprocess.run([sys.executable, "berwaz-pipeline.py", cmd], capture_output=True, text=True, timeout=3600)
                out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
                self.send_response(200 if proc.returncode == 0 else 500)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": proc.returncode == 0, "output": out[-20000:]}).encode("utf-8"))
            except Exception as e:
                self.send_response(500); self.send_header("Content-type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "output": str(e)}).encode("utf-8"))

        # API endpoint: POST /api/publish
        elif path == "/api/publish":
            try:
                config = load_config()
                if config and publish_config(config):
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(b'{"status": "published"}')
                else:
                    self.send_response(500)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Could not publish"}')
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(f'{{"error": "{str(e)}"}}'.encode('utf-8'))

        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')

    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-type")
        self.end_headers()

    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[{self.client_address[0]}] {format % args}")


def main():
    """Start the admin server"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")

    print("=" * 60)
    print("Berwaz Admin Server")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Working directory: {os.getcwd()}")

    # Ensure config exists
    config = load_config()
    if config:
        print(f"Config loaded: {len(config.get('directors', []))} directors, {len(config.get('frames', []))} frames")
    else:
        print("Error: Could not initialize config")
        sys.exit(1)

    # Start server
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, BerwazAdminHandler)

    url = f"http://localhost:{PORT}/admin.html"
    print(f"\nServer running at http://localhost:{PORT}")
    print(f"Admin panel: {url}")
    print("Press Ctrl+C to stop\n")

    # Auto-open browser
    try:
        webbrowser.open(url)
        print("Opening browser...")
    except Exception as e:
        print(f"Could not auto-open browser: {e}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        httpd.shutdown()
        print("Server stopped")


if __name__ == "__main__":
    main()
