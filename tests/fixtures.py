"""Generated test inputs: an edge-case export (nasty.xml), a 1,500-issue export (large.xml) and a 1x1 logo."""
import base64
import struct
import zlib
from pathlib import Path
from xml.sax.saxutils import escape


def _b64(s: bytes | str) -> str:
    return base64.b64encode(s if isinstance(s, bytes) else s.encode("utf-8")).decode()


def _rr(req: bytes | str, resp: bytes | str) -> str:
    return (f'<requestresponse><request method="GET" base64="true"><![CDATA[{_b64(req)}]]></request>'
            f'<response base64="true"><![CDATA[{_b64(resp)}]]></response>'
            f'<responseRedirected>false</responseRedirected></requestresponse>')


def _issue(serial, typ, name, host, path, sev, conf, detail="", ev="", host_el=True) -> str:
    h = f'<host ip="198.51.100.7">{escape(host)}</host>' if host_el else ""
    return f"""<issue><serialNumber>{serial}</serialNumber><type>{typ}</type><name>{escape(name)}</name>{h}
<path><![CDATA[{path}]]></path><location><![CDATA[{path}]]></location><severity>{sev}</severity><confidence>{conf}</confidence>
<issueBackground><![CDATA[<p>Background.</p>]]></issueBackground><remediationBackground><![CDATA[<p>Fix it.</p>]]></remediationBackground>
{f'<issueDetail><![CDATA[{detail}]]></issueDetail>' if detail else ''}{ev}</issue>"""


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


PNG = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
       + _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + _chunk(b"IEND", b""))


def nasty_xml() -> str:
    """Unicode, brackets, script in names, severity aliases, binary and huge bodies, a missing host."""
    h = "https://bücher.example"
    issues = [
        _issue(1, 1, "Cross-site scripting [DOM-based]", h, "/a?x=[/link]", "high", "certain",
               "Sink: <code>[/link] location.hash</code>",
               _rr("GET /a HTTP/1.1\r\nHost: b\r\n\r\n", "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<p>ok</p>")),
        _issue(2, 2, "Name with <script>alert('n')</script> & ampersand", h, "/b c\"d'e", "HIGH", "Firm"),
        _issue(3, 3, "Unicode issue — 日本語 ✓", h, "/日本", "Medium", "Tentative"),
        _issue(4, 4, "Informational with alias severity", h, "/c", "info", "firm"),
        _issue(5, 5, "Binary response body", h, "/logo.png", "Low", "Certain", "",
               _rr("GET /logo.png HTTP/1.1\r\nHost: b\r\n\r\n",
                   b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n\r\n" + PNG * 50)),
        _issue(6, 6, "Huge response", "https://big.example", "/big", "Low", "Firm", "",
               _rr("GET /big HTTP/1.1\r\nHost: big\r\n\r\n",
                   "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\n" + "A" * 300_000)),
        _issue(7, 7, "Missing host element", "", "/nohost", "Medium", "Certain", host_el=False),
        _issue(8, 8, "False positive marked in Burp", h, "/fp", "False positive", "Certain"),
    ]
    return ('<?xml version="1.0"?>\n<issues burpVersion="2025.10 [beta]" exportTime="now">\n'
            + "\n".join(issues) + "\n</issues>\n")


def large_xml(count: int = 1500) -> str:
    """`count` instances across 40 issue types and 12 hosts, each with a request and a ~4 KB response."""
    sevs = ["High", "Medium", "Low", "Information"]
    body = "<div>lorem ipsum dolor sit amet</div>\n" * 120
    issues = []
    for n in range(count):
        req = f"GET /p/{n}?q=test HTTP/1.1\r\nHost: app{n % 12}.example.com\r\nCookie: s={n}\r\n\r\n"
        resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + body
        issues.append(_issue(10000 + n, 100 + n % 40, f"Issue type {n % 40}", f"https://app{n % 12}.example.com",
                             f"/p/{n}?q=test", sevs[n % 4], "Firm", f"Detail for instance {n}.", _rr(req, resp)))
    return '<?xml version="1.0"?>\n<issues burpVersion="2025.10">\n' + "\n".join(issues) + "\n</issues>\n"


def write_all(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / "logo.png").write_bytes(PNG)
    (out / "nasty.xml").write_text(nasty_xml(), encoding="utf-8")
    (out / "large.xml").write_text(large_xml(), encoding="utf-8")
    return out
