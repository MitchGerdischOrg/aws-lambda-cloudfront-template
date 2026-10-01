"""Entry point that hosts the deployment-settings component provider."""

from pulumi.provider.experimental import component_provider_host

from stack_deployment_settings import StackDeploymentSettings

if __name__ == "__main__":
    component_provider_host(
        name="deployment-settings",
        components=[StackDeploymentSettings],
    )
