"""Local sales-agent page. Run with: python app.py."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent import compare_briefs, confirm_meeting, continue_call, draft_outbound

HOST, PORT = "127.0.0.1", 8787
PAGE = Path(__file__).with_name("index.html")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Never log user content or upstream exceptions.

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, status, data):
        self.send(status, json.dumps(data, ensure_ascii=False).encode())

    def local_request(self):
        return self.headers.get("Host") in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

    def do_GET(self):
        if not self.local_request():
            return self.json_response(403, {"error": "Local requests only."})
        if self.path != "/":
            return self.json_response(404, {"error": "Not found."})
        self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        if not self.local_request() or self.headers.get("Origin") not in {
            None, f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"
        }:
            return self.json_response(403, {"error": "Local requests only."})
        if self.headers.get_content_type() != "application/json":
            return self.json_response(415, {"error": "JSON required."})
        if self.path not in {"/api/brief", "/api/reply", "/api/outbound", "/api/meeting"}:
            return self.json_response(404, {"error": "Not found."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16000:
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
            lead = data.get("lead_id", "Alex Rivera")
            language = data.get("language", "auto")
            message = data.get("message", "")
            if any(not isinstance(v, str) for v in (lead, language, message)):
                raise ValueError()
            if not lead.strip() or len(lead) > 120 or len(language) > 80 or len(message) > 8000:
                raise ValueError()
            if self.path == "/api/reply" and not message.strip():
                raise ValueError()
            if self.path == "/api/meeting":
                from datetime import datetime
                meeting_at = data.get("meeting_at", "")
                attendees = data.get("attendees", "the finance director")
                if not isinstance(meeting_at, str) or not isinstance(attendees, str) or not attendees.strip() or len(attendees) > 200:
                    raise ValueError()
                datetime.strptime(meeting_at, "%Y-%m-%dT%H:%M")
        except (ValueError, TypeError):
            return self.json_response(400, {"error": "Provide a lead name and a valid message (up to 8,000 characters)."})
        try:
            if self.path == "/api/brief":
                result = compare_briefs(lead)
            elif self.path == "/api/meeting":
                result = confirm_meeting(lead, meeting_at, attendees)
            elif self.path == "/api/outbound":
                result = draft_outbound(lead, language)
            else:
                result = continue_call(lead, message, language)
            self.json_response(200, result)
        except Exception:
            # SDK exceptions can contain credentials. Never echo them to the page.
            self.json_response(502, {"error": "Service request failed. Check local .env settings and Hindsight/Groq availability, then retry."})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Sales Agent: http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
