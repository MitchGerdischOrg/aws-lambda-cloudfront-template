# component-aws-lambda-services

A Python multi-language Pulumi component package that abstracts the resources needed to run a simple Python HTTP app on AWS Lambda:

- `LambdaApp`: zips a folder of Python code into a Lambda function, with an execution role, a CloudWatch log group (7 day retention), and a public function URL.

It uses `pulumi-aws` directly, and all resources are children of the component.

The function is invoked through its function URL, so the handler receives the [function URL event](https://docs.aws.amazon.com/lambda/latest/dg/urls-invocation.html) (API Gateway HTTP API payload format 2.0) and returns `statusCode`, `headers`, and `body`.

The code folder is uploaded as-is. Third-party dependencies are not installed; vendor them into the folder or use a Lambda layer.

## Usage

### Add the package to `Pulumi.yaml`

```
packages:
  # versioning is optional
  lambda-services: https://GITREPO-PATH/component-aws-lambda-services[@v1.0.0]
```

Run `pulumi install` (or `pulumi package add https://GITREPO-PATH/component-aws-lambda-services[@v1.0.0]` - version is optional) to generate the local SDK.

These commands will also provide the python import code for referencing the component.

### Python

```python
import pulumi
import XXXX_lambda_services as lambda_services

app = lambda_services.LambdaApp(
    "app",
    code_path="./app",
    handler="handler.handler",   # optional, defaults to handler.handler
    runtime="python3.13",        # optional, defaults to python3.13
    memory_size=128,             # optional, defaults to 128 MiB
    timeout=10,                  # optional, defaults to 10 seconds
    environment_variables={"LOG_LEVEL": "info"},  # optional
)

pulumi.export("url", app.function_url)
```

`code_path` is resolved relative to the calling program's folder.

### Fronting with CloudFront

Use `functionUrlDomain` as a custom origin with `origin_protocol_policy="https-only"`. Do not forward the viewer `Host` header to the origin (e.g. use the AWS managed `AllViewerExceptHostHeader` origin request policy rather than `AllViewer`), or the function URL will reject the request.

## Inputs and outputs

| Input | Default | Description |
|-------|---------|-------------|
| `codePath` | (required) | Folder containing the function code. |
| `handler` | `handler.handler` | Entry point in `module.function` form. |
| `runtime` | `python3.13` | Lambda runtime. |
| `memorySize` | `128` | Memory in MiB. |
| `timeout` | `10` | Timeout in seconds. |
| `environmentVariables` | | Env vars for the function. |

| Output | Description |
|--------|-------------|
| `functionName` | Name of the Lambda function. |
| `functionUrl` | The function URL, e.g. `https://<id>.lambda-url.<region>.on.aws/`. |
| `functionUrlDomain` | The function URL host name, for use as a CDN origin. |
