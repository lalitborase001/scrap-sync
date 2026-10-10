"""SendAlertFunction: DynamoDB Stream INSERT -> SMS to a recycler via SNS."""
import os

import boto3
from boto3.dynamodb.types import TypeDeserializer

sns = boto3.client("sns")
deserializer = TypeDeserializer()

# TODO: set via the AlertPhoneNumber parameter in template.yaml (E.164, e.g. +919876543210).
PHONE_NUMBER = os.environ["ALERT_PHONE_NUMBER"]


def lambda_handler(event, context):
    sent = 0
    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":  # also filtered in template.yaml
            continue

        # Stream records use DynamoDB JSON ({"S": "..."}); convert to plain Python.
        lot = {k: deserializer.deserialize(v) for k, v in record["dynamodb"]["NewImage"].items()}

        value = float(lot.get("estimated_value", 0))
        names = ", ".join(str(i) for i in lot.get("items", [])[:3]) or "mixed e-waste"
        # "Rs" instead of the rupee sign keeps the SMS in GSM-7 (cheaper, fewer segments).
        message = f"New e-waste lot {str(lot['LotId'])[:8]}: {names}. Est. scrap value Rs {value:,.0f}. Open the Hub to bid."

        sns.publish(
            PhoneNumber=PHONE_NUMBER,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
            },
        )
        sent += 1

    return {"sent": sent}