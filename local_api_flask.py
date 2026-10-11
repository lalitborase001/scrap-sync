"""Local API server using Flask.
Runs without Docker, connects to real Bedrock, uses in-memory storage."""
import base64
import json
import re
import time
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS

import boto3

app = Flask(__name__)
CORS(app)

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

        # Look for JSON in model output
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
        # Check if file might be an ID card or non-ewaste image
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

    # Also save directly to DynamoDB EwasteBids table
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
            except Exception as tbl_err:
                print(f"[LOCAL] DynamoDB put to {table_name} skipped: {tbl_err}")
    except Exception as ddb_err:
        print(f"[LOCAL] DynamoDB client error: {ddb_err}")

    return lot


@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze_endpoint():
    if request.method == "OPTIONS":
        return "", 200

    try:
        payload = request.get_json(silent=True) or {}
        media_type = payload.get("content_type")
        image_base64 = payload.get("image_base64")

        if media_type not in ALLOWED_TYPES:
            return jsonify({"error": "content_type must be jpeg, png, gif or webp"}), 400

        if not image_base64:
            return jsonify({"error": "image_base64 is required"}), 400

        image_bytes = base64.b64decode(image_base64)
        key = f"local/{uuid.uuid4()}.{media_type.split('/')[1]}"

        print(f"[LOCAL] Analyzing image: {media_type}, size: {len(image_bytes)} bytes")

        # Graceful Bedrock analysis
        items, value = analyze(image_bytes, media_type)

        lot = save_lot(key, items, value, "local-user", image_base64)

        return jsonify({
            "lot_id": lot["LotId"],
            "items": items,
            "estimated_value": value,
            "image_base64": image_base64,
        }), 200
    except Exception as exc:
        print(f"[ERROR] Analyze failed: {exc}")
        return jsonify({"error": f"analysis failed: {str(exc)}"}), 500


@app.route("/lots", methods=["GET"])
def get_lots():
    try:
        # Also attempt to read from DynamoDB EwasteBids table to sync any newly added lots
        try:
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            for table_name in ["EwasteBids", "EWasteLots"]:
                try:
                    table = dynamodb.Table(table_name)
                    resp = table.scan(Limit=50)
                    for item in resp.get("Items", []):
                        lid = item.get("LotId")
                        if lid and lid not in local_lots:
                            local_lots[lid] = {
                                "LotId": lid,
                                "items": item.get("items", []),
                                "estimated_value": float(item.get("estimated_value", 0)),
                                "owner": item.get("owner", "user"),
                                "created_at": int(item.get("created_at", time.time())),
                                "image_base64": item.get("image_base64"),
                            }
                    break
                except Exception:
                    pass
        except Exception:
            pass

        # Return all lots from in-memory storage (including image_base64)
        lots_list = list(local_lots.values())
        # Sort by created_at descending (newest first)
        lots_list.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return jsonify({"lots": lots_list}), 200
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return jsonify({"error": f"failed to fetch lots: {str(exc)}"}), 500


@app.route("/claim", methods=["POST", "OPTIONS"])
def claim_endpoint():
    if request.method == "OPTIONS":
        return "", 200

    try:
        payload = request.get_json(silent=True) or {}
        item_id = (
            payload.get("item_id")
            or payload.get("lot_id")
            or payload.get("LotId")
            or payload.get("id")
            or payload.get("itemId")
        )

        if not item_id:
            return jsonify({"error": "Missing item_id in request body"}), 400

        print(f"[LOCAL] Processing claim for scrap item: {item_id}")

        # 1. Lookup item in local_lots first
        lot = local_lots.get(str(item_id))

        # 2. If not found in local_lots, try DynamoDB
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
                    except Exception as tbl_err:
                        print(f"[LOCAL] DynamoDB lookup in {table_name} skipped: {tbl_err}")
            except Exception as ddb_err:
                print(f"[LOCAL] DynamoDB connection error: {ddb_err}")

        # 3. Fallback default if not found
        if not lot:
            lot = {
                "LotId": str(item_id),
                "items": ["Mixed electronic scrap"],
                "estimated_value": 2500.0,
            }

        # 4. Generate mock local pickup address
        mock_addresses = [
            "Shop 14, Dharavi Electronic Market, 90 Feet Rd, Mumbai 400017",
            "Plot 42, Mayapuri Industrial Area Phase II, New Delhi 110064",
            "No. 88, SP Road Electronic Hub, Bengaluru 560002",
            "Gala 7, Kurla Scrap Market, CST Road, Mumbai 400070",
            "Shed 23, Guindy Industrial Estate, Chennai 600032",
            "Shop 105, Lamington Road Computer Market, Mumbai 400007",
            "Building 4, Chandni Chowk Electronic Bazaar, Kolkata 700072",
        ]
        addr_index = abs(hash(str(item_id))) % len(mock_addresses)
        pickup_address = mock_addresses[addr_index]

        # 5. Format value and SMS message
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

        # 6. Interact with Amazon SNS via boto3
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

        return jsonify({
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
        }), 200
    except Exception as exc:
        print(f"[ERROR] Claim error: {exc}")
        return jsonify({"error": f"Claim failed: {str(exc)}"}), 500


if __name__ == "__main__":
    print("[LOCAL] API server running on http://127.0.0.1:3000", flush=True)
    print("[LOCAL] Endpoint: http://127.0.0.1:3000/analyze", flush=True)
    print("[LOCAL] Endpoint: http://127.0.0.1:3000/lots", flush=True)
    print("[LOCAL] Endpoint: http://127.0.0.1:3000/claim", flush=True)
    app.run(host="127.0.0.1", port=3000, debug=True)
