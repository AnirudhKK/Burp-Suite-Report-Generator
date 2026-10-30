"""Local web UI: pick settings in the browser and see the report update live.

Runs a small stdlib HTTP server bound to 127.0.0.1. API calls must carry a
per-run token and a localhost Host header, so other websites open in the same
browser cannot drive it.
"""
from __future__ import annotations

import json
import re
import secrets
from collections import OrderedDict
import tempfile
import threading
import webbrowser
from collections import Counter
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .config import FINDING_FIELDS, SECTIONS, ReportConfig
from .docx_export import DOCX_AVAILABLE, DOCX_MISSING, render_docx
from .parser import CONFIDENCES, SEVERITIES, ScanReport, parse_burp_bytes, parse_burp_xml
from .pdf import available_engine, html_to_pdf
from .render import list_templates, render_html, resolve_template

WEBUI_DIR = Path(__file__).parent / "webui"
SAMPLE_XML = Path(__file__).resolve().parent / "samples" / "sample_burp_export.xml"
MAX_UPLOAD = 256 * 1024 * 1024
MAX_PREVIEWS = 6
PDF_SLOTS = threading.BoundedSemaphore(2)   # cap concurrent headless-browser renders

# Previews run in a sandboxed frame with an opaque origin; this CSP is a second fence.
PREVIEW_CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
               "font-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
_SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S | re.I)

ACCENTS = [
    ("Template default", ""), ("Navy", "#1f3a5f"), ("Royal purple", "#5b3cc4"), ("Teal", "#0f766e"),
    ("Crimson", "#b91c1c"), ("Forest", "#166534"), ("Ocean", "#0369a1"), ("Charcoal", "#222222"),
]
FONTS = [
    ("Template default", ""),
    ("Inter (modern sans)", '"Inter", "Segoe UI", system-ui, Arial, sans-serif'),
    ("Source Sans 3 (formal sans)", '"Source Sans 3", "Segoe UI", system-ui, Arial, sans-serif'),
    ("IBM Plex Sans (technical sans)", '"IBM Plex Sans", "Helvetica Neue", Arial, sans-serif'),
    ("Source Serif 4 (formal serif)", '"Source Serif 4", Georgia, "Times New Roman", serif'),
    ("Segoe UI / system", '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif'),
    ("Calibri", "Calibri, Carlito, Arial, sans-serif"),
    ("Georgia (serif)", 'Georgia, "Times New Roman", serif'),
]

# Injected into preview pages only, so the editor can keep the scroll position across re-renders.
SCROLL_BRIDGE = """<script>
addEventListener('scroll',function(){parent.postMessage({burpScroll:scrollY},'*')},{passive:true});
addEventListener('message',function(e){if(e.data&&typeof e.data.burpRestore==='number')scrollTo(0,e.data.burpRestore)});
</script>"""


class State:
    def __init__(self) -> None:
        self.scan: ScanReport | None = None
        self.profile: dict | None = None
        self.lock = threading.Lock()
        self.previews: OrderedDict[str, bytes] = OrderedDict()

    def store_preview(self, html: str) -> str:
        pid = secrets.token_urlsafe(12)
        with self.lock:
            self.previews[pid] = html.encode()
            while len(self.previews) > MAX_PREVIEWS:
                self.previews.popitem(last=False)
        return pid


def scan_summary(scan: ScanReport | None) -> dict | None:
    if scan is None:
        return None
    sev = Counter(i.severity for i in scan.issues)
    conf = Counter(i.confidence for i in scan.issues)
    hosts = Counter(i.host for i in scan.issues)
    order = {s: n for n, s in enumerate(SEVERITIES)}
    types: dict[str, dict] = {}
    for i in scan.issues:
        t = types.setdefault(i.name, {"name": i.name, "severity": i.severity, "count": 0})
        t["count"] += 1
        if order.get(i.severity, 9) < order.get(t["severity"], 9):
            t["severity"] = i.severity
    return {
        "name": scan.source.name,
        "burp_version": scan.burp_version,
        "export_time": scan.export_time,
        "total": len(scan.issues),
        "severity_counts": {s: sev[s] for s in SEVERITIES},
        "confidence_counts": {c: conf[c] for c in CONFIDENCES},
        "hosts": [{"host": h, "count": n} for h, n in sorted(hosts.items())],
        "issue_types": sorted(types.values(), key=lambda t: (order.get(t["severity"], 9), t["name"])),
    }


def safe_filename(*parts: str) -> str:
    stem = "_".join(p for p in parts if p) or "burp_report"
    stem = re.sub(r"[^\w.-]+", "_", stem).strip("_.")[:80]
    return stem or "burp_report"


def content_disposition(kind: str, filename: str) -> str:
    """RFC 6266 header with an ASCII fallback, so non-Latin names don't break the response."""
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("_") or "report"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def make_handler(state: State, token: str, port_ref: list[int]):
    index_html = (WEBUI_DIR / "index.html").read_text(encoding="utf-8").replace("__API_TOKEN__", token)

    class Handler(BaseHTTPRequestHandler):
        server_version = "BurpReportUI/1.0"

        def log_message(self, fmt, *args):  # keep the console quiet
            pass

        # ---------------------------------------------------- plumbing
        def _host_ok(self) -> bool:
            port = port_ref[0]
            return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def _error(self, msg: str, code: int = 400) -> None:
            self._json({"error": msg}, code)

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_UPLOAD:
                raise ValueError("Upload too large")
            return self.rfile.read(n)

        def _config(self, payload: dict) -> ReportConfig:
            cfg = ReportConfig.from_dict(payload.get("config") or {})
            resolve_template(cfg.template)
            return cfg

        # ---------------------------------------------------- routes
        def do_GET(self):
            if not self._host_ok():
                return self._error("Forbidden host", 403)
            url = urlparse(self.path)
            path = url.path
            if path.startswith("/preview/"):
                if not secrets.compare_digest(parse_qs(url.query).get("t", [""])[0], token):
                    return self._error("Forbidden", 403)
                with state.lock:
                    body = state.previews.get(path[len("/preview/"):])
                if body is None:
                    return self._send(410, b"<p>Preview expired - change any setting to refresh.</p>", "text/html")
                return self._send(200, body, "text/html; charset=utf-8",
                                  {"Content-Security-Policy": PREVIEW_CSP, "Referrer-Policy": "no-referrer"})
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path in ("/", "/index.html"):
                return self._send(200, index_html.encode(), "text/html; charset=utf-8",
                                  {"Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                   "script-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src data:; "
                                   "frame-src blob: 'self'; object-src 'none'; base-uri 'none'",
                                   "Referrer-Policy": "no-referrer"})
            return self._error("Not found", 404)

        def do_POST(self):
            if not self._host_ok() or not secrets.compare_digest(self.headers.get("X-Token", ""), token):
                return self._error("Forbidden", 403)
            route = urlparse(self.path).path
            try:
                body = self._body()
                if route == "/api/upload":
                    name = Path(unquote(self.headers.get("X-Filename", "report.xml"))).name
                    scan = parse_burp_bytes(body, name)
                    with state.lock:
                        state.scan = scan
                    return self._json(scan_summary(scan))
                if route == "/api/sample":
                    if not SAMPLE_XML.exists():
                        return self._error("Sample file not found")
                    scan = parse_burp_xml(SAMPLE_XML)
                    with state.lock:
                        state.scan = scan
                    return self._json(scan_summary(scan))

                payload = json.loads(body or b"{}")
                if route == "/api/meta":
                    return self._json({
                        "templates": [{"key": t.key, "name": t.name, "description": t.description} for t in list_templates()],
                        "sections": SECTIONS, "fields": FINDING_FIELDS,
                        "severities": SEVERITIES, "confidences": CONFIDENCES,
                        "accents": ACCENTS, "fonts": FONTS,
                        "defaults": asdict(ReportConfig()),
                        "pdf_engine": available_engine(),
                        "docx_available": DOCX_AVAILABLE, "docx_missing": DOCX_MISSING,
                        "sample_available": SAMPLE_XML.exists(),
                        "scan": scan_summary(state.scan),
                        "profile": state.profile,
                    })
                if route == "/api/template":
                    info = resolve_template(str(payload.get("path", "")).strip().strip('"'))
                    return self._json({"path": str(info.resolve())})

                scan = state.scan
                if scan is None:
                    return self._error("Load a Burp XML export first")
                cfg = self._config(payload)

                if route == "/api/preview":
                    html = render_html(scan, cfg, "html")
                    html = html.replace("</body>", SCROLL_BRIDGE + "</body>", 1)
                    return self._json({"url": f"/preview/{state.store_preview(html)}?t={token}"})
                if route == "/api/thumbs":
                    # Thumbnails only show the first screen, so skip the heavy parts and all scripts.
                    cfg.interactive_html = False
                    cfg.fields["evidence"] = False
                    cfg.sections["findings"] = False
                    cfg.sections["cover"] = True
                    out = {}
                    for t in list_templates():
                        cfg.template = t.key
                        out[t.key] = _SCRIPT_RE.sub("", render_html(scan, cfg, "html"))
                    return self._json(out)
                if route in ("/api/export", "/api/pdf-preview"):
                    fmt = "pdf" if route == "/api/pdf-preview" else payload.get("format", "html")
                    fname = safe_filename(cfg.client, cfg.title) + "." + fmt
                    if fmt == "html":
                        data, ctype = render_html(scan, cfg, "html").encode(), "text/html; charset=utf-8"
                    elif fmt == "pdf":
                        with PDF_SLOTS, tempfile.TemporaryDirectory() as tmp:
                            out = Path(tmp) / "report.pdf"
                            html_to_pdf(render_html(scan, cfg, "pdf"), out)
                            data = out.read_bytes()
                        ctype = "application/pdf"
                    elif fmt == "docx":
                        data = render_docx(scan, cfg)
                        ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    else:
                        return self._error("Unknown format")
                    disp = "inline" if route == "/api/pdf-preview" else "attachment"
                    return self._send(200, data, ctype, {"Content-Disposition": content_disposition(disp, fname)})
                return self._error("Not found", 404)
            except ConnectionError:
                return None  # browser went away (e.g. a superseded preview request)
            except (ValueError, TypeError, KeyError, FileNotFoundError, RuntimeError, json.JSONDecodeError) as exc:
                return self._error(str(exc))
            except Exception as exc:  # template errors etc. – report rather than drop the connection
                return self._error(f"{type(exc).__name__}: {exc}", 500)

    return Handler


def serve(xml: str | Path | None = None, profile: ReportConfig | None = None,
          port: int = 0, open_browser: bool = True) -> None:
    state = State()
    if xml:
        state.scan = parse_burp_xml(xml)
    if profile is not None:
        state.profile = asdict(profile)
    token = secrets.token_urlsafe(24)
    port_ref = [0]
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state, token, port_ref))
    port_ref[0] = server.server_address[1]
    url = f"http://127.0.0.1:{port_ref[0]}/"
    print(f"Burp Suite Report Generator UI running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
