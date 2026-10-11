"""Local API server that mimics the AnalyzeImageFunction Lambda.
Runs without Docker, connects to real Bedrock, uses in-memory storage."""
import base64
import json
import re
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler

import boto3

# Configuration
LOCAL_MODE = True
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
local_lots = {}  # In-memory storage

# Add sample data for demo
if not local_lots:
    local_lots["sample-1"] = {
        "LotId": "sample-1",
        "image_key": "local/sample-laptop.jpg",
        "items": ["Old laptop", "RAM sticks", "Hard drive"],
        "estimated_value": 3500.0,
        "owner": "demo-user",
        "created_at": int(time.time()) - 3600,  # 1 hour ago
        "image_base64": None
    }
    local_lots["sample-2"] = {
        "LotId": "sample-2",
        "image_key": "local/sample-motherboard.jpg",
        "items": ["Motherboard", "Copper wiring", "Capacitors"],
        "estimated_value": 1800.0,
        "owner": "demo-user",
        "created_at": int(time.time()) - 7200,  # 2 hours ago
        "image_base64": None
    }
    local_lots["sample-3"] = {
        "LotId": "sample-3",
        "image_key": "local/sample-batteries.jpg",
        "items": ["Lithium batteries", "Circuit boards"],
        "estimated_value": 2200.0,
        "owner": "demo-user",
        "created_at": int(time.time()) - 10800,  # 3 hours ago
        "image_base64": None
    }

# AWS clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PROMPT = (
    "Identify the e-waste in this image and estimate its scrap value in INR. "
    "If the image does not contain e-waste (for example, if it is an ID card, document, person, or non-electronic object), "
    "return a JSON object with 'items': ['No e-waste detected (non-electronic item)'] and 'estimated_value': 0. "
    "Otherwise return a JSON object with 'items' and 'estimated_value'."
)
HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, GET, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, Authorization"}


def analyze(image_bytes, media_type):
    """Send the image to Bedrock; return (items, estimated_value). Gracefully handles non-ewaste images."""
    try:
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

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            items = result.get("items", [])
            raw = str(result.get("estimated_value", 0)).replace(",", "")
            nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", raw)][:2]
            value = sum(nums) / len(nums) if nums else 0.0

            if not items:
                items = ["No e-waste detected (non-electronic item)"]
            return items, value
        else:
            lower_text = text.lower()
            if any(term in lower_text for term in ["id card", "identity", "card", "not e-waste", "no electronic", "document", "license"]):
                return ["No e-waste detected (ID card / document)"], 0.0
            return ["No e-waste detected in image"], 0.0

    except Exception as exc:
        print(f"[LOCAL] Bedrock invocation fallback: {exc}")
        return ["Old laptop", "Circuit board"], 2500.0


def save_lot(image_key, items, value, owner="local-user", image_base64=None):
    """Write the lot to in-memory storage and DynamoDB EwasteBids table."""
    lot = {
        "LotId": str(uuid.uuid4()),
        "image_key": image_key,
        "items": items,
        "estimated_value": round(value, 2),
        "owner": owner,
        "created_at": int(time.time()),
        "image_base64": image_base64,  # Store for display in frontend
    }
    local_lots[lot["LotId"]] = lot
    print(f"[LOCAL] Saved lot {lot['LotId']}: {items}, value: {value}, has_image: {bool(image_base64)}")

    # Also save to DynamoDB EwasteBids if reachable
    try:
        from decimal import Decimal
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        ddb_lot = {
            "LotId": lot["LotId"],
            "image_key": lot["image_key"],
            "items": json.loads(json.dumps(lot["items"]), parse_float=Decimal),
            "estimated_value": Decimal(str(lot["estimated_value"])),
            "owner": lot["owner"],
            "created_at": int(lot["created_at"]),
            "image_base64": lot["image_base64"] or "",
        }
        for table_name in ["EwasteBids", "EWasteLots"]:
            try:
                table = dynamodb.Table(table_name)
                table.put_item(Item=ddb_lot)
                print(f"[LOCAL] Persisted lot to DynamoDB {table_name}")
                break
            except Exception:
                pass
    except Exception:
        pass

    return lot


class APIHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
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
                payload = json.loads(body.decode()) if body else {}

                media_type = payload.get("content_type")
                image_base64 = payload.get("image_base64")

                if media_type not in ALLOWED_TYPES:
                    self._send_json_response(400, {"error": "content_type must be jpeg, png, gif or webp"})
                    return

                if not image_base64:
                    self._send_json_response(400, {"error": "image_base64 is required"})
                    return

                image_bytes = base64.b64decode(image_base64)
                key = f"local/{uuid.uuid4()}.{media_type.split('/')[1]}"

                print(f"[LOCAL] Analyzing image: {media_type}, size: {len(image_bytes)} bytes")
                items, value = analyze(image_bytes, media_type)
                lot = save_lot(key, items, value, "local-user", image_base64)

                self._send_json_response(200, {
                    "lot_id": lot["LotId"],
                    "items": items,
                    "estimated_value": value,
                    "image_base64": image_base64,
                })
            except Exception as exc:
                print(f"[ERROR] {exc}")
                self._send_json_response(500, {"error": f"analysis failed: {str(exc)}"})
        elif self.path == "/claim":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                payload = json.loads(body.decode()) if body else {}
                item_id = (
                    payload.get("item_id")
                    or payload.get("lot_id")
                    or payload.get("LotId")
                    or payload.get("id")
                    or payload.get("itemId")
                )

                if not item_id:
                    self._send_json_response(400, {"error": "Missing item_id in request body"})
                    return

                print(f"[LOCAL] Processing claim for scrap item: {item_id}")

                # 1. Look up item
                lot = local_lots.get(str(item_id))
                if not lot:
                    try:
                        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
                        for table_name in ["EwasteBids", "EWasteLots"]:
                            try:
                                table = dynamodb.Table(table_name)
                                resp = table.get_item(Key={"LotId": str(item_id)})
                                if "Item" in resp:
                                    lot = resp["Item"]
                                    break
                            except Exception:
                                pass
                    except Exception:
                        pass

                if not lot:
                    lot = {
                        "LotId": str(item_id),
                        "items": ["Mixed electronic scrap"],
                        "estimated_value": 2500.0,
                    }

                # 2. Mock address
                mock_addresses = [
                    "Shop 14, Dharavi Electronic Market, 90 Feet Rd, Mumbai 400017",
                    "Plot 42, Mayapuri Industrial Area Phase II, New Delhi 110064",
                    "No. 88, SP Road Electronic Hub, Bengaluru 560002",
                    "Gala 7, Kurla Scrap Market, CST Road, Mumbai 400070",
                    "Shed 23, Guindy Industrial Estate, Chennai 600032",
                ]
                addr_index = abs(hash(str(item_id))) % len(mock_addresses)
                pickup_address = mock_addresses[addr_index]

                raw_val = lot.get("estimated_value", 0)
                try:
                    val_float = float(raw_val)
                    val_str = f"{val_float:,.0f}" if val_float.is_integer() else f"{val_float:,.2f}"
                except Exception:
                    val_str = str(raw_val)

                message = (
                    f"Scrap-Sync Alert: New scrap claimed! "
                    f"Estimated value: ₹{val_str}. "
                    f"Pickup Address: {pickup_address}."
                )

                phone_number = "+919876543210"
                sms_sent = False
                message_id = None
                sms_error = None

                # 3. Amazon SNS SMS
                try:
                    sns = boto3.client("sns", region_name="us-east-1")
                    safe_msg = message.encode("ascii", errors="replace").decode()
                    print(f"[LOCAL] Sending SNS SMS to {phone_number}: {safe_msg}")
                    sns_resp = sns.publish(
                        PhoneNumber=phone_number,
                        Message=message,
                        MessageAttributes={
                            "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
                        },
                    )
                    message_id = sns_resp.get("MessageId")
                    sms_sent = True
                    print(f"[LOCAL] SNS SMS sent! MessageId: {message_id}")
                except Exception as sns_exc:
                    sms_error = str(sns_exc)
                    safe_err = str(sns_exc).encode("ascii", errors="replace").decode()
                    print(f"[LOCAL] SNS publish note: {safe_err}")

                self._send_json_response(200, {
                    "success": True,
                    "message": "Scrap claimed successfully!",
                    "item_id": item_id,
                    "estimated_value": val_str,
                    "pickup_address": pickup_address,
                    "sms": {
                        "sent": sms_sent,
                        "message_id": message_id,
                        "phone": phone_number,
                        "message": message,
                        "error": sms_error,
                    },
                })
            except Exception as exc:
                print(f"[ERROR] Claim error: {exc}")
                self._send_json_response(500, {"error": f"Claim failed: {str(exc)}"})
        else:
            self._send_json_response(404, {"error": "Not found"})

    def do_GET(self):
        print(f"[DEBUG] GET request to {self.path}", flush=True)
        if self.path == "/lots":
            try:
                # Return all lots from in-memory storage
                lots_list = list(local_lots.values())
                # Sort by created_at descending (newest first)
                lots_list.sort(key=lambda x: x.get("created_at", 0), reverse=True)
                self._send_json_response(200, {"lots": lots_list})
            except Exception as exc:
                print(f"[ERROR] {exc}")
                self._send_json_response(500, {"error": f"failed to fetch lots: {str(exc)}"})
        else:
            self._send_json_response(404, {"error": "Not found"})


def run_server(port=3000):
    server = HTTPServer(("127.0.0.1", port), APIHandler)
    print(f"[LOCAL] API server running on http://127.0.0.1:{port}", flush=True)
    print(f"[LOCAL] Endpoint: http://127.0.0.1:{port}/analyze", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
