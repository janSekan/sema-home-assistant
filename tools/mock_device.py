"""Read-only loopback simulator for the PROPOSED SEMA API, not device firmware."""

import argparse
import hmac
import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Public fixture credential. Never use it for a real SEMA device.
DEMO_TOKEN = "sema-demo-token-not-for-production"


def make_server(port=8124, pump_offline=False, extended=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Do not log request headers or credentials.
            pass

        def send_json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            supplied = self.headers.get("Authorization", "").encode()
            expected = ("Bearer " + DEMO_TOKEN).encode()
            if not hmac.compare_digest(supplied, expected):
                self.send_json(401, {"detail": "Invalid demo token"})
                return
            route = urlsplit(self.path).path
            names = {
                "/device-api/v1/info": "info.json",
                "/device-api/v1/state": "state_pump_unavailable.json"
                if pump_offline
                else "state.json",
            }
            name = names.get(route)
            if name is None:
                self.send_json(404, {"detail": "Unknown mock endpoint"})
                return
            data = json.loads((ROOT / "fixtures" / name).read_text())
            if extended:
                data = json.loads(
                    (
                        ROOT
                        / "fixtures"
                        / (
                            "info_extended.json"
                            if route.endswith("/info")
                            else "state_extended.json"
                        )
                    ).read_text()
                )
                if pump_offline and route.endswith("/state"):
                    data["pump_available"] = False
                    for group in ("temperatures", "states", "modes"):
                        data[group] = dict.fromkeys(data[group])
                    data["power_percent"] = None
            if route.endswith("/state"):
                now = datetime.now(UTC).isoformat(timespec="seconds")
                data["generated_at"] = now
                if data["observed_at"] is not None:
                    data["observed_at"] = now
                if extended:
                    data["configuration"]["observed_at"] = now
            self.send_json(200, data)

        def reject_write(self):
            self.send_json(
                405, {"detail": "Read-only simulator; no control operations"}
            )

        do_POST = reject_write
        do_PUT = reject_write
        do_PATCH = reject_write
        do_DELETE = reject_write

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--pump-offline", action="store_true")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Simulate read-only revision 2 configuration and modes",
    )
    args = parser.parse_args()
    server = make_server(args.port, args.pump_offline, args.extended)
    print(
        f"SEMA mock only: http://127.0.0.1:{server.server_port}; no real pump",
        flush=True,
    )
    print(
        "Use the PUBLIC DEMO token from README.md; never reuse it in production.",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
