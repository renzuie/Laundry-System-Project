"""
LABADA LINK - receipt printer helper (Windows AND Raspberry Pi).

The web page sends each receipt as a picture; this program prints it on the
thermal printer and cuts the paper.  Run it once and leave it open.

    python print_helper.py            (Windows)
    python3 print_helper.py           (Raspberry Pi)

Needs:  pip install python-escpos pillow        (Windows also: pywin32)
Settings live in config.json (same folder).
"""
import base64, io, json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = {
    "port": 5000,
    "allowed_origins": ["https://labada-link.cvsu.workers.dev", "http://localhost", "http://127.0.0.1"],
    "paper_dots": 384,          # 58 mm printer = 384, 80 mm printer = 576
    "cut": "feed_partial",      # feed_partial | partial | full | none
    "feed_lines": 4,            # blank lines before cutting (partial / full only)
    "printer": {"type": "windows", "name": "Caysn58-2"},
}
try:
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        CFG.update(json.load(f))
except FileNotFoundError:
    print("config.json not found - using defaults")

CUT_BYTES = {
    "feed_partial": b"\x1d\x56\x42\x00",   # feeds to the blade by itself, then partial cut
    "partial":      b"\x1d\x56\x01",
    "full":         b"\x1d\x56\x00",
}
MAX_BODY = 12 * 1024 * 1024
LOCK = threading.Lock()                     # one print job at a time


def open_printer():
    p = CFG["printer"]
    t = p.get("type", "windows")
    if t == "windows":
        from escpos.printer import Win32Raw
        return Win32Raw(p["name"])
    if t == "usb":
        from escpos.printer import Usb
        return Usb(int(p["vid"], 16), int(p["pid"], 16))
    if t == "file":
        from escpos.printer import File
        return File(p["dev"])
    if t == "preview":                       # no printer: saves pictures in ./preview
        return None
    raise ValueError("unknown printer type: %s" % t)


def prepare(png_bytes):
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    img = bg.convert("L")
    w = int(CFG["paper_dots"])
    if img.width != w:
        img = img.resize((w, max(1, round(img.height * w / img.width))), Image.LANCZOS)
    return img.convert("1")                  # Floyd-Steinberg dither


def print_images(images):
    prepared = [prepare(b) for b in images]
    if CFG["printer"].get("type") == "preview":
        folder = os.path.join(HERE, "preview")
        os.makedirs(folder, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for i, im in enumerate(prepared, 1):
            im.save(os.path.join(folder, "%s-%d.png" % (stamp, i)))
        return
    p = open_printer()
    try:
        for im in prepared:
            p._raw(b"\x1b\x40")              # reset
            p.image(im)
            mode = CFG["cut"]
            if mode in ("partial", "full"):
                p.text("\n" * int(CFG["feed_lines"]))
            if mode in CUT_BYTES:
                p._raw(CUT_BYTES[mode])
            elif mode == "none":
                p.text("\n" * int(CFG["feed_lines"]))
    finally:
        p.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "LabadaPrinter/1"

    def log_message(self, fmt, *args):
        print("%s  %s" % (time.strftime("%H:%M:%S"), fmt % args))

    def _allowed(self):
        origin = self.headers.get("Origin")
        return origin is None or origin in CFG["allowed_origins"], origin

    def _send(self, code, obj, origin=None):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        ok, origin = self._allowed()
        if not ok:
            return self._send(403, {"ok": False, "error": "origin not allowed"})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin or "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        ok, origin = self._allowed()
        if not ok:
            return self._send(403, {"ok": False, "error": "origin not allowed"})
        if self.path.split("?")[0] == "/ping":
            return self._send(200, {"ok": True, "dots": int(CFG["paper_dots"]),
                                    "printer": CFG["printer"].get("type")}, origin)
        self._send(404, {"ok": False, "error": "not found"}, origin)

    def do_POST(self):
        ok, origin = self._allowed()
        if not ok:
            return self._send(403, {"ok": False, "error": "origin not allowed"})
        if self.path.split("?")[0] != "/print":
            return self._send(404, {"ok": False, "error": "not found"}, origin)
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"ok": False, "error": "bad size"}, origin)
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            images = [base64.b64decode(s.split(",", 1)[-1]) for s in data["images"]]
            if not images or len(images) > 20:
                return self._send(400, {"ok": False, "error": "no images"}, origin)
            with LOCK:
                print_images(images)
            self._send(200, {"ok": True, "printed": len(images)}, origin)
        except Exception as e:                       # printer off, wrong name, bad data...
            print("PRINT ERROR:", repr(e))
            self._send(500, {"ok": False, "error": str(e)}, origin)


def main():
    port = int(CFG["port"])
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)   # this computer only
    print("LABADA LINK printer helper running on http://localhost:%d" % port)
    print("Printer:", CFG["printer"], "| cut:", CFG["cut"], "| paper dots:", CFG["paper_dots"])
    print("Leave this window open. Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
