"""Local API server that mimics the AnalyzeImageFunction Lambda.
Runs without Docker, connects to real Bedrock, uses in-memory storage."""
import base64
import json
import mimetypes
import os
import re
import time
import uuid
from decimal import Decimal
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import boto3

# Configuration
LOCAL_MODE = True
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
local_lots = {}  # In-memory storage

# AWS clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PROMPT = (
    "Identify the e-waste in this image and estimate its scrap value in INR. "
    "Return only a JSON object with 'items' and 'estimated_value'"
)
HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def analyze(image_bytes, media_type):
    """Send the image to Bedrock; return (items, estimated_value)."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    }
    resp = bedrock.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    text = json.loads(resp["body"].read())["content"][0]["text"]

    # The model sometimes wraps JSON in prose or code fences; grab the object.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON in model output: {text[:200]}")
    result = json.loads(match.group(0))

    # Be forgiving: "5,000", "Rs 5000", or a range like "4000-6000" (use midpoint).
    raw = str(result.get("estimated_value", 0)).replace(",", "")
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", raw)][:2]
    value = sum(nums) / len(nums) if nums else 0.0
    return result.get("items", []), value


def save_lot(image_key, items, value, owner="local-user"):
    """Write the lot to in-memory storage."""
    lot = {
        "LotId": str(uuid.uuid4()),
        "image_key": image_key,
        "items": items,
        "estimated_value": round(value, 2),
        "owner": owner,
        "created_at": int(time.time()),
    }
    local_lots[lot["LotId"]] = lot
    print(f"[LOCAL] Saved lot {lot['LotId']}: {items}, value: {value}")
    return lot


class APIHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json_response(self, status_code, data):
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == "/analyze":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode())

                media_type = payload.get("content_type")
                if media_type not in ALLOWED_TYPES:
                    self._send_json_response(400, {"error": "content_type must be jpeg, png, gif or webp"})
                    return

                image_bytes = base64.b64decode(payload["image_base64"])
                key = f"local/{uuid.uuid4()}.{media_type.split('/')[1]}"

                print(f"[LOCAL] Analyzing image: {media_type}, size: {len(image_bytes)} bytes")
                
                # For demo purposes, if the image is too small or invalid, return mock data
                if len(image_bytes) < 100:
                    print("[LOCAL] Image too small, returning mock data")
                    items = ["Old laptop", "Circuit board"]
                    value = 2500.0
                else:
                    items, value = analyze(image_bytes, media_type)
                lot = save_lot(key, items, value, "local-user")

                self._send_json_response(200, {
                    "lot_id": lot["LotId"],
                    "items": items,
                    "estimated_value": value
                })
            except Exception as exc:
                print(f"[ERROR] {exc}")
                self._send_json_response(500, {"error": f"analysis failed: {str(exc)}"})
        else:
            self._send_json_response(404, {"error": "Not found"})


def run_server(port=3000):
    server = HTTPServer(("127.0.0.1", port), APIHandler)
    print(f"[LOCAL] API server running on http://127.0.0.1:{port}", flush=True)
    print(f"[LOCAL] Endpoint: http://127.0.0.1:{port}/analyze", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
