"""Packages the Python app in ./app as a Lambda function with a function URL,
and fronts the function URL with a CloudFront distribution."""

import pulumi
import pulumi_aws as aws

# Add component package imports here


# Package the sample app as a Lambda function and expose it through a function URL.
app = lambda_services.LambdaApp(
    "app",
    code_path="./app",
    handler="handler.handler",
)

# AWS managed policies: CachingDisabled and AllViewerExceptHostHeader.
# Function URLs reject requests whose Host header is not the function URL host,
# so the viewer's Host header must not be forwarded to the origin.
CACHING_DISABLED_POLICY_ID = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
ALL_VIEWER_EXCEPT_HOST_HEADER_ORIGIN_REQUEST_POLICY_ID = (
    "b689b0a8-53d0-40ab-baf2-68738e2966ac"
)

# CloudFront distribution using the Lambda function URL as a custom origin.
# Function URLs are HTTPS only.
distribution = aws.cloudfront.Distribution(
    "app-cdn",
    enabled=True,
    comment="CloudFront in front of the Lambda app function URL",
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            origin_id="lambda-url",
            domain_name=app.function_url_domain,
            custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                http_port=80,
                https_port=443,
                origin_protocol_policy="https-only",
                origin_ssl_protocols=["TLSv1.2"],
            ),
        )
    ],
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id="lambda-url",
        viewer_protocol_policy="redirect-to-https",
        allowed_methods=[
            "GET",
            "HEAD",
            "OPTIONS",
            "PUT",
            "POST",
            "PATCH",
            "DELETE",
        ],
        cached_methods=["GET", "HEAD"],
        cache_policy_id=CACHING_DISABLED_POLICY_ID,
        origin_request_policy_id=ALL_VIEWER_EXCEPT_HOST_HEADER_ORIGIN_REQUEST_POLICY_ID,
    ),
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none",
        ),
    ),
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=True,
    ),
)

# Pulumi Deployments settings for this stack: preview on PRs (update on push is off by default).
# Anything not set in stack config is worked out by the component:
#   repository     - 'owner/repo'; defaults to the local git 'origin' remote
#   installationId - VCS integration (GitHub account) ID; set when the org has several GitHub integrations
#   branch         - defaults to the checked-out branch
#   repoDir        - defaults to this folder's path in the repo
#   agentPoolId    - required; a runner pool ID, or 'pulumi-provided-runners' for Pulumi Cloud hosted runners
config = pulumi.Config()
deployment = deployment_settings.StackDeploymentSettings(
    "deployment-settings",
    repository=config.get("repository"),
    installation_id=config.get("installationId"),
    branch=config.get("branch"),
    repo_dir=config.get("repoDir"),
    agent_pool_id=config.require("agentPoolId"),
)

pulumi.export("function_url", app.function_url)
pulumi.export(
    "cloudfront_url", pulumi.Output.concat("https://", distribution.domain_name)
)
pulumi.export("deployment_settings_stack", deployment.stack_name)
