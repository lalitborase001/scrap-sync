from http.server import HTTPServer, BaseHTTPRequestHandler

class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

server = HTTPServer(("127.0.0.1", 3001), TestHandler)
print("Test server running on http://127.0.0.1:3001")
server.serve_forever()
