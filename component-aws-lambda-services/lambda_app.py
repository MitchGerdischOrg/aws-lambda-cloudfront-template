"""LambdaApp: packages a folder of Python code as a Lambda function and exposes it through a function URL."""

from typing import TypedDict

import pulumi
import pulumi_aws as aws

_DEFAULT_HANDLER = "handler.handler"
_DEFAULT_RUNTIME = "python3.13"
_DEFAULT_MEMORY_SIZE = 128  # MiB
_DEFAULT_TIMEOUT = 10  # seconds
_LOG_RETENTION_DAYS = 7


class LambdaAppArgs(TypedDict):
    code_path: pulumi.Input[str]
    """The path to the directory containing the function code. The directory is zipped and uploaded as-is. Required."""

    handler: pulumi.Input[str] | None
    """The function entry point in 'module.function' form. Defaults to 'handler.handler'."""

    runtime: pulumi.Input[str] | None
    """The Lambda runtime, e.g. 'python3.13'. Defaults to 'python3.13'."""

    memory_size: pulumi.Input[int] | None
    """The amount of memory (in MiB) for the function, e.g. 128, 256, 512. Defaults to 128."""

    timeout: pulumi.Input[int] | None
    """The function timeout in seconds. Defaults to 10."""

    environment_variables: pulumi.Input[dict[str, pulumi.Input[str]]] | None
    """Environment variables to set for the function."""


class LambdaApp(pulumi.ComponentResource):
    function_name: pulumi.Output[str]
    """The name of the Lambda function that was created."""

    function_url: pulumi.Output[str]
    """The function URL (https://<id>.lambda-url.<region>.on.aws/) at which the function's HTTP endpoint is available."""

    function_url_domain: pulumi.Output[str]
    """The host name of the function URL, for use as a CDN origin domain."""

    def __init__(
        self,
        name: str,
        args: LambdaAppArgs,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("lambda-services:index:LambdaApp", name, {}, opts)

        child_opts = pulumi.ResourceOptions(parent=self)
        tags = {"Owner": f"{pulumi.get_project()}-{pulumi.get_stack()}"}

        def arg(key: str, default=None):
            value = args.get(key)
            return default if value is None else value

        # Execution role: lets the function write its logs to CloudWatch.
        role = aws.iam.Role(
            f"{name}-role",
            assume_role_policy=aws.iam.get_policy_document_output(
                statements=[
                    aws.iam.GetPolicyDocumentStatementArgs(
                        actions=["sts:AssumeRole"],
                        principals=[
                            aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                                type="Service",
                                identifiers=["lambda.amazonaws.com"],
                            )
                        ],
                    )
                ]
            ).json,
            tags=tags,
            opts=child_opts,
        )
        role_policy = aws.iam.RolePolicyAttachment(
            f"{name}-role-policy",
            role=role.name,
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            opts=child_opts,
        )

        # Explicit log group so retention is set and it is deleted with the stack.
        log_group = aws.cloudwatch.LogGroup(
            f"{name}-logs",
            retention_in_days=_LOG_RETENTION_DAYS,
            tags=tags,
            opts=child_opts,
        )

        environment = None
        environment_variables = args.get("environment_variables")
        if environment_variables is not None:
            environment = aws.lambda_.FunctionEnvironmentArgs(
                variables=environment_variables
            )

        function = aws.lambda_.Function(
            f"{name}-function",
            role=role.arn,
            runtime=arg("runtime", _DEFAULT_RUNTIME),
            handler=arg("handler", _DEFAULT_HANDLER),
            memory_size=arg("memory_size", _DEFAULT_MEMORY_SIZE),
            timeout=arg("timeout", _DEFAULT_TIMEOUT),
            # The component provider runs in the program's directory, so a relative
            # code_path resolves against the calling program.
            code=pulumi.Output.from_input(args["code_path"]).apply(
                pulumi.FileArchive
            ),
            logging_config=aws.lambda_.FunctionLoggingConfigArgs(
                log_format="Text",
                log_group=log_group.name,
            ),
            environment=environment,
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self, depends_on=[role_policy]),
        )

        # Public HTTPS endpoint for the function. Public (auth NONE) function URLs need both
        # InvokeFunctionUrl and InvokeFunction (via function URL) permissions for anonymous callers.
        function_url = aws.lambda_.FunctionUrl(
            f"{name}-url",
            function_name=function.name,
            authorization_type="NONE",
            opts=child_opts,
        )
        aws.lambda_.Permission(
            f"{name}-url-invoke-url-permission",
            function=function.name,
            action="lambda:InvokeFunctionUrl",
            principal="*",
            function_url_auth_type="NONE",
            opts=child_opts,
        )
        aws.lambda_.Permission(
            f"{name}-url-invoke-permission",
            function=function.name,
            action="lambda:InvokeFunction",
            principal="*",
            invoked_via_function_url=True,
            opts=child_opts,
        )

        self.function_name = function.name
        self.function_url = function_url.function_url
        # https://<id>.lambda-url.<region>.on.aws/ -> <id>.lambda-url.<region>.on.aws
        self.function_url_domain = function_url.function_url.apply(
            lambda url: url.removeprefix("https://").rstrip("/")
        )

        self.register_outputs(
            {
                "function_name": self.function_name,
                "function_url": self.function_url,
                "function_url_domain": self.function_url_domain,
            }
        )
