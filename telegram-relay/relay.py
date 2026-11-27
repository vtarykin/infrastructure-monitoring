import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


RELAY_HOST = os.getenv("RELAY_HOST", "127.0.0.1")
RELAY_PORT = int(os.getenv("RELAY_PORT", "18082"))
TELEGRAM_API = "https://api.telegram.org"
MAX_BODY_SIZE = 10 * 1024 * 1024

BOT_API_PATH = re.compile(
    r"^/bot[0-9]+:[A-Za-z0-9_-]+/[A-Za-z][A-Za-z0-9_]*$"
)


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "TelegramRelay/1.0"
    sys_version = ""

    def log_message(self, format, *args):
        # Never log request paths: Telegram bot tokens are part of the URL.
        pass

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        parsed_url = urlsplit(self.path)

        if not BOT_API_PATH.fullmatch(parsed_url.path):
            self.send_error(404)
            return

        body = None

        if self.command == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return

            if length < 0 or length > MAX_BODY_SIZE:
                self.send_error(413)
                return

            body = self.rfile.read(length)

        request = Request(
            f"{TELEGRAM_API}{self.path}",
            data=body,
            method=self.command,
            headers={
                "Content-Type": self.headers.get(
                    "Content-Type", "application/json"
                )
            },
        )

        try:
            with urlopen(request, timeout=20) as response:
                self.send_response(response.status)
                self.send_header(
                    "Content-Type",
                    response.headers.get("Content-Type", "application/json"),
                )
                self.end_headers()
                self.wfile.write(response.read())

        except HTTPError as error:
            self.send_response(error.code)
            self.send_header(
                "Content-Type",
                error.headers.get("Content-Type", "application/json"),
            )
            self.end_headers()
            self.wfile.write(error.read())

        except (URLError, TimeoutError):
            self.send_error(502, "Telegram connection failed")


class RelayServer(ThreadingHTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    server = RelayServer((RELAY_HOST, RELAY_PORT), RelayHandler)
    server.serve_forever()
