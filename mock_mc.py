"""
Mock microcontroller server — simulates an ESP32/ESP8266 HTTP endpoint.

Run this alongside the broker to test without real hardware:
    python mock_mc.py

It serves GET http://localhost:8001/data and returns random sensor values
in the same format the real microcontroller would produce.
"""
import json
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "localhost"
PORT = 8001


class MockMCHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data":
            payload = {
                "light":            random.randint(0, 4095),       # raw ADC
                "soil-moisture":    random.randint(0, 4095),       # raw ADC
                "temp":             round(random.uniform(-40, 80), 1),   # °C
                "ambient-humidity": round(random.uniform(0, 100), 1),    # %
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            print(f"  → served: {payload}")
        else:
            self.send_response(404)
            self.end_headers()

    # Suppress default request log line (we print our own above)
    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), MockMCHandler)
    print(f"Mock MC running at http://{HOST}:{PORT}/data")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
