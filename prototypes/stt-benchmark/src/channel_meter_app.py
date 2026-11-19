from __future__ import annotations

import argparse
import json
import signal
import subprocess
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .paths import PROJECT_ROOT


WEB_ROOT = PROJECT_ROOT / "web" / "channel-meter"
METER_EXE = PROJECT_ROOT / "native" / "wasapi-raw-meter" / "WasapiRawMeter.exe"


class RawMeterService:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.process: subprocess.Popen[str] | None = None
        self.latest: dict = {
            "ok": True,
            "running": False,
            "raw": True,
            "device": "Wireless Mic Rx",
            "channels": 0,
            "sample_rate": 0,
            "levels": [],
            "correlations": [],
            "error": None,
        }

    def start(self) -> None:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return
            if not METER_EXE.is_file():
                raise FileNotFoundError(
                    "RAW-meter ontbreekt. Voer scripts\\build-wasapi-meter.ps1 uit."
                )
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                [str(METER_EXE), "--device", "Wireless Mic Rx"],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
            self.latest.update({"running": True, "error": None})
            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()

    def stop(self) -> None:
        with self.lock:
            process = self.process
            self.process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        with self.lock:
            self.latest["running"] = False
            self.latest["levels"] = []
            self.latest["correlations"] = []

    def _read_stdout(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        try:
            for line in process.stdout:
                try:
                    incoming = json.loads(line)
                except json.JSONDecodeError:
                    continue
                with self.lock:
                    self.latest.update(incoming)
                    self.latest["running"] = True
                    self.latest["error"] = None
        finally:
            self._mark_stopped(process)

    def _read_stderr(self) -> None:
        process = self.process
        if process is None or process.stderr is None:
            return
        messages = []
        for line in process.stderr:
            message = line.strip()
            if message:
                messages.append(message)
        if process.poll() not in (None, 0) and messages:
            with self.lock:
                self.latest["error"] = messages[-1]

    def _mark_stopped(self, process: subprocess.Popen[str]) -> None:
        with self.lock:
            if self.process is process and process.poll() is not None:
                self.latest["running"] = False
                if process.returncode not in (0, None) and not self.latest.get("error"):
                    self.latest["error"] = f"RAW-meter stopte met code {process.returncode}."

    def status(self) -> dict:
        with self.lock:
            result = dict(self.latest)
            result["levels"] = [dict(item) for item in self.latest.get("levels", [])]
            result["correlations"] = [
                dict(item) for item in self.latest.get("correlations", [])
            ]
            return result


class ChannelMeterHandler(BaseHTTPRequestHandler):
    service: RawMeterService

    def log_message(self, format: str, *args) -> None:
        return

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            body = json.dumps({"ok": True, "purpose": "four-channel-meter"}).encode()
            self._send(body, "application/json; charset=utf-8")
            return
        if path == "/api/status":
            body = json.dumps(self.service.status(), ensure_ascii=False).encode("utf-8")
            self._send(body, "application/json; charset=utf-8")
            return

        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
        }
        selected = static_files.get(path)
        if selected is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename, content_type = selected
        self._send((WEB_ROOT / filename).read_bytes(), content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/start":
                self.service.start()
            elif path == "/api/stop":
                self.service.stop()
            else:
                self._send(
                    json.dumps({"ok": False, "error": "Onbekende route"}).encode(),
                    "application/json; charset=utf-8",
                    HTTPStatus.NOT_FOUND,
                )
                return
            self._send(b'{"ok":true}', "application/json; charset=utf-8")
        except Exception as exc:
            body = json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(body, "application/json; charset=utf-8", 500)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Webmeter die vier browser-microfoonkanalen afzonderlijk toont."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not WEB_ROOT.is_dir():
        raise RuntimeError(f"Webbestanden ontbreken: {WEB_ROOT}")

    service = RawMeterService()
    ChannelMeterHandler.service = service
    server = ThreadingHTTPServer((args.host, args.port), ChannelMeterHandler)
    address = f"http://{args.host}:{args.port}"
    signal.signal(signal.SIGINT, lambda *_: server.shutdown())
    print("DJI-vierkanaalsmeter gestart", flush=True)
    print(f"Open: {address}", flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    finally:
        service.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
