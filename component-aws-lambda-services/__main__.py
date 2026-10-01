"""Entry point that hosts the lambda-services component provider."""

from pulumi.provider.experimental import component_provider_host

from lambda_app import LambdaApp

if __name__ == "__main__":
    component_provider_host(
        name="lambda-services",
        components=[LambdaApp],
    )
