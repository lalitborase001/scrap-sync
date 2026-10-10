"""AnalyzeImageFunction: e-waste image -> Bedrock (Claude 3 Haiku vision) -> DynamoDB.

Triggered two ways:
  1. S3 ObjectCreated on uploads/  -> event["Records"]
  2. API Gateway POST /analyze     -> JSON body {"image_base64", "content_type"}
"""
import base64
import json
import mimetypes
import os
import re
import time
import uuid
from decimal import Decimal
from urllib.parse import unquote_plus

import boto3

# Clients live outside the handler so warm invocations reuse them.
s3 = boto3.client("s3")
# TODO: the Lambda's region must have Claude 3 Haiku enabled (Bedrock console -> Model access).
bedrock = boto3.client("bedrock-runtime")
table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

BUCKET_NAME = os.environ["BUCKET_NAME"]
MODEL_ID = os.environ["MODEL_ID"]  # set in template.yaml (BedrockModelId parameter)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PROMPT = (
    "Identify the e-waste in this image and estimate its scrap value in INR. "
    "Return only a JSON object with 'items' and 'estimated_value'"
)
# TODO: replace "*" with your Amplify domain once deployed.
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


def save_lot(image_key, items, value, owner="s3-upload"):
    """Write the lot; this INSERT is what triggers SendAlertFunction via the stream."""
    lot = {
        "LotId": str(uuid.uuid4()),
        "image_key": image_key,
        # DynamoDB rejects Python floats, so convert to Decimal.
        "items": json.loads(json.dumps(items), parse_float=Decimal),
        "estimated_value": Decimal(str(round(value, 2))),
        "owner": owner,
        "created_at": int(time.time()),
    }
    table.put_item(Item=lot)
    return lot


def handle_s3(event):
    lots = []
    for rec in event["Records"]:
        bucket = rec["s3"]["bucket"]["name"]
        key = unquote_plus(rec["s3"]["object"]["key"])
        obj = s3.get_object(Bucket=bucket, Key=key)
        media_type = obj.get("ContentType")
        if media_type not in ALLOWED_TYPES:
            media_type = mimetypes.guess_type(key)[0]
        if media_type not in ALLOWED_TYPES:
            print(f"Skipping unsupported file: {key}")
            continue
        items, value = analyze(obj["Body"].read(), media_type)
        lots.append(save_lot(key, items, value)["LotId"])
    return {"lots": lots}


def handle_api(event):
    payload = json.loads(event.get("body") or "{}")
    media_type = payload.get("content_type")
    if media_type not in ALLOWED_TYPES:
        return {"statusCode": 400, "headers": HEADERS,
                "body": json.dumps({"error": "content_type must be jpeg, png, gif or webp"})}

    image_bytes = base64.b64decode(payload["image_base64"])
    # Stored under api/ so it does NOT re-trigger the uploads/ S3 notification.
    key = f"api/{uuid.uuid4()}.{media_type.split('/')[1]}"
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=image_bytes, ContentType=media_type)

    items, value = analyze(image_bytes, media_type)
    # Cognito user id (sub) comes from the authorizer claims.
    owner = event.get("requestContext", {}).get("authorizer", {}).get("claims", {}).get("sub", "unknown")
    lot = save_lot(key, items, value, owner)
    return {
        "statusCode": 200,
        "headers": HEADERS,
        "body": json.dumps({"lot_id": lot["LotId"], "items": items, "estimated_value": value}),
    }


def lambda_handler(event, context):
    try:
        if "Records" in event:  # S3 trigger
            return handle_s3(event)
        return handle_api(event)  # API Gateway trigger
    except Exception as exc:  # surface failures to the caller / CloudWatch
        print(f"Error: {exc}")
        if "Records" in event:
            raise  # let Lambda retry S3 async invocations
        return {"statusCode": 500, "headers": HEADERS, "body": json.dumps({"error": "analysis failed"})}