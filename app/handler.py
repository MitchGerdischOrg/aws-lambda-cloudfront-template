"""Sample app: a Lambda function URL handler that serves a small HTML page and a JSON health check."""

import json
import os
from datetime import datetime, timezone

_PAGE = """<!DOCTYPE html>
<html>
  <head><title>Hello from Lambda</title></head>
  <body>
    <h1>Hello from Lambda behind CloudFront</h1>
    <p>This function was packaged and deployed by Pulumi.</p>
    <p>Served at {time} by {function}.</p>
  </body>
</html>
"""


def handler(event, context):
    # Function URLs use the API Gateway HTTP API (payload format 2.0) event shape.
    path = event.get("rawPath", "/")

    if path == "/health":
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "ok"}),
        }

    if path != "/":
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "text/plain"},
            "body": "Not found",
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": _PAGE.format(
            time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            function=os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "lambda"),
        ),
    }
