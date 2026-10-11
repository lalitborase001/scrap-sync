"""ClaimScrapFunction: Handle scrap item claims and trigger automated SNS SMS with pickup address."""
import json
import logging
import os
from decimal import Decimal

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration from environment variables
TABLE_NAME = os.environ.get("TABLE_NAME", "EwasteBids")
PHONE_NUMBER = os.environ.get("ALERT_PHONE_NUMBER", "+919876543210")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

# Initialize AWS clients using active temporary sandbox credentials from the environment
dynamodb = boto3.resource("dynamodb", region_name=REGION)
sns = boto3.client("sns", region_name=REGION)

# CORS headers for API Gateway responses
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST,GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}

# Mock local pickup addresses for hackathon demo
MOCK_ADDRESSES = [
    "Shop 14, Dharavi Electronic Market, 90 Feet Rd, Mumbai 400017",
    "Plot 42, Mayapuri Industrial Area Phase II, New Delhi 110064",
    "No. 88, SP Road Electronic Hub, Bengaluru 560002",
    "Gala 7, Kurla Scrap Market, CST Road, Mumbai 400070",
    "Shed 23, Guindy Industrial Estate, Chennai 600032",
    "Shop 105, Lamington Road Computer Market, Mumbai 400007",
    "Building 4, Chandni Chowk Electronic Bazaar, Kolkata 700072",
]

# Fallback sample lots for local testing/demo
SAMPLE_LOTS = {
    "sample-1": {
        "LotId": "sample-1",
        "items": ["Old laptop", "RAM sticks", "Hard drive"],
        "estimated_value": 3500.0,
    },
    "sample-2": {
        "LotId": "sample-2",
        "items": ["Motherboard", "Copper wiring", "Capacitors"],
        "estimated_value": 1800.0,
    },
    "sample-3": {
        "LotId": "sample-3",
        "items": ["Lithium batteries", "Circuit boards"],
        "estimated_value": 2200.0,
    },
}


def decimal_to_python(obj):
    """Recursively convert DynamoDB Decimal instances to float/int."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, list):
        return [decimal_to_python(i) for i in obj]
    if isinstance(obj, dict):
        return {k: decimal_to_python(v) for k, v in obj.items()}
    return obj


def get_item_from_dynamodb(item_id):
    """Look up scrap item in DynamoDB (EwasteBids or EWasteLots), falling back to sample lots."""
    tables_to_try = [TABLE_NAME]
    if "EWasteLots" not in tables_to_try:
        tables_to_try.append("EWasteLots")
    if "EwasteBids" not in tables_to_try:
        tables_to_try.append("EwasteBids")

    for tbl_name in tables_to_try:
        try:
            table = dynamodb.Table(tbl_name)
            # Try LotId primary key
            resp = table.get_item(Key={"LotId": str(item_id)})
            if "Item" in resp:
                logger.info(f"Found item {item_id} in DynamoDB table {tbl_name}")
                return decimal_to_python(resp["Item"])
            # Try id primary key
            resp = table.get_item(Key={"id": str(item_id)})
            if "Item" in resp:
                logger.info(f"Found item {item_id} (key 'id') in DynamoDB table {tbl_name}")
                return decimal_to_python(resp["Item"])
        except Exception as exc:
            logger.warning(f"DynamoDB lookup in {tbl_name} failed: {exc}")

    # Fallback to sample data for demo/mock items
    if str(item_id) in SAMPLE_LOTS:
        logger.info(f"Using sample lot data for {item_id}")
        return SAMPLE_LOTS[str(item_id)]

    logger.info(f"Item {item_id} not found in DynamoDB or sample list; using generic default")
    return {
        "LotId": str(item_id),
        "items": ["Mixed electronic scrap"],
        "estimated_value": 2500.0,
    }


def generate_mock_address(item_id):
    """Generate a deterministic mock local pickup address based on the item ID."""
    idx = abs(hash(str(item_id))) % len(MOCK_ADDRESSES)
    return MOCK_ADDRESSES[idx]


def handle_claim(event):
    """Process scrap claim request and trigger SNS SMS."""
    # Parse body
    body = event.get("body") or "{}"
    if isinstance(body, str):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = body

    item_id = (
        payload.get("item_id")
        or payload.get("lot_id")
        or payload.get("LotId")
        or payload.get("id")
        or payload.get("itemId")
    )

    if not item_id:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Missing item_id in request payload"}),
        }

    logger.info(f"Processing claim for scrap item: {item_id}")

    # 1. Look up item details in DynamoDB table (EwasteBids / EWasteLots)
    item = get_item_from_dynamodb(item_id)

    # 2. Generate mock local pickup address
    pickup_address = generate_mock_address(item_id)

    # 3. Format value and SMS message
    raw_val = item.get("estimated_value", 0)
    try:
        val_float = float(raw_val)
        val_str = f"{val_float:,.0f}" if val_float.is_integer() else f"{val_float:,.2f}"
    except (ValueError, TypeError):
        val_str = str(raw_val)

    message = (
        f"Scrap-Sync Alert: New scrap claimed! "
        f"Estimated value: ₹{val_str}. "
        f"Pickup Address: {pickup_address}."
    )

    # 4. Send SMS to verified phone number using Amazon SNS
    sms_sent = False
    message_id = None
    sms_error = None

    try:
        safe_msg = message.encode("ascii", errors="replace").decode()
        logger.info(f"Publishing SMS to {PHONE_NUMBER} via SNS: {safe_msg}")
        sns_response = sns.publish(
            PhoneNumber=PHONE_NUMBER,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional",
                }
            },
        )
        message_id = sns_response.get("MessageId")
        sms_sent = True
        logger.info(f"SNS SMS sent successfully! MessageId: {message_id}")
    except Exception as exc:
        sms_error = str(exc)
        logger.error(f"Failed to publish SNS message: {exc}")

    # Return success response
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(
            {
                "success": True,
                "message": "Scrap claimed successfully!",
                "item_id": item_id,
                "estimated_value": val_str,
                "pickup_address": pickup_address,
                "sms": {
                    "sent": sms_sent,
                    "message_id": message_id,
                    "phone": PHONE_NUMBER,
                    "message": message,
                    "error": sms_error,
                },
            }
        ),
    }


def handle_get_lots():
    """Return available lots (scanned from DynamoDB or fallback sample lots) for sam local start-api."""
    lots = []
    for tbl_name in [TABLE_NAME, "EWasteLots"]:
        try:
            table = dynamodb.Table(tbl_name)
            resp = table.scan(Limit=50)
            items = resp.get("Items", [])
            if items:
                lots = [decimal_to_python(i) for i in items]
                break
        except Exception as exc:
            logger.warning(f"Scan on {tbl_name} failed: {exc}")

    if not lots:
        lots = list(SAMPLE_LOTS.values())

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({"lots": lots}),
    }


def lambda_handler(event, context):
    """Main Lambda entry point."""
    logger.info(f"Received event: {json.dumps(event) if isinstance(event, dict) else str(event)}")

    # Handle OPTIONS preflight request
    http_method = event.get("httpMethod", "POST").upper()
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }

    path = event.get("path", "/claim")
    if http_method == "GET" and (path == "/lots" or "lots" in path):
        return handle_get_lots()

    try:
        return handle_claim(event)
    except Exception as exc:
        logger.error(f"Unhandled error in lambda_handler: {exc}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Failed to claim scrap: {str(exc)}"}),
        }
