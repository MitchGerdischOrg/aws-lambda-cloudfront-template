"""StackDeploymentSettings: configures Pulumi Deployments for a stack via the Pulumi Cloud (pulumiservice) provider.

Repository, branch, repo dir and trigger paths default to values read from the local git checkout
of the calling program. The component provider process runs in the program's directory, so git
commands and Pulumi.yaml reads here see the program's repo, not this package's.
"""

import json
import os
import posixpath
import subprocess
import urllib.request
from typing import TypedDict

import pulumi
import pulumi_pulumiservice as pulumiservice
import yaml

_DEFAULT_VCS_PROVIDER = "github"
_DEFAULT_BRANCH = "main"
# agent_pool_id value that selects Pulumi Cloud hosted runners instead of a customer-managed pool.
PULUMI_PROVIDED_RUNNERS = "pulumi-provided-runners"


def _git(*git_args: str) -> str | None:
    """Runs a git command in the program directory; returns None if git or the repo is unavailable."""
    try:
        result = subprocess.run(
            ["git", *git_args], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _detect_repository() -> str | None:
    """Converts the 'origin' remote URL (https, ssh, or scp-style) to 'owner/repo'."""
    url = _git("remote", "get-url", "origin")
    if not url:
        return None
    parts = url.removesuffix(".git").replace(":", "/").rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else None


def _detect_branch() -> str | None:
    """The checked-out branch, else the remote's default branch (e.g. on a detached HEAD)."""
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        return branch
    remote_head = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return remote_head.removeprefix("origin/") if remote_head else None


def _detect_repo_dir() -> str:
    """The program directory's path relative to the repo root ('' at the root)."""
    return (_git("rev-parse", "--show-prefix") or "").strip("/")


def _detect_trigger_paths(repo_dir: str) -> list[str]:
    """The program folder plus any local-path packages in Pulumi.yaml that live in the same repo."""
    paths = [f"{repo_dir}/**" if repo_dir else "**"]
    try:
        with open("Pulumi.yaml") as f:
            packages = (yaml.safe_load(f) or {}).get("packages") or {}
    except (OSError, yaml.YAMLError):
        return paths
    for source in packages.values():
        # Packages are either a plain source string or a mapping with a 'source' key.
        if isinstance(source, dict):
            source = source.get("source")
        if not isinstance(source, str) or not source.startswith("."):
            continue
        package_dir = posixpath.normpath(posixpath.join(repo_dir, source))
        if not package_dir.startswith(".."):
            paths.append(f"{package_dir}/**")
    return paths


def _pulumi_credentials() -> tuple[str, str] | None:
    """Returns (api_url, access_token) for the current Pulumi Cloud login, or None if unavailable."""
    api_url = os.environ.get("PULUMI_BACKEND_URL")
    token = os.environ.get("PULUMI_ACCESS_TOKEN")
    if not api_url or not token:
        try:
            path = os.path.join(
                os.environ.get("PULUMI_HOME") or os.path.expanduser("~/.pulumi"),
                "credentials.json",
            )
            with open(path) as f:
                creds = json.load(f)
        except (OSError, ValueError):
            creds = {}
        api_url = api_url or creds.get("current")
        token = token or (creds.get("accessTokens") or {}).get(api_url or "")
    if not api_url or not token:
        return None
    return api_url.rstrip("/"), token


def _list_vcs_integrations(organization: str) -> list[dict]:
    """Lists the org's VCS integrations from Pulumi Cloud.

    Tries the Pulumi CLI first (it already has the login and trusted certificates), then falls back
    to calling the API directly with the stored credentials. Raises OSError/ValueError on failure.
    """
    try:
        result = subprocess.run(
            [
                "pulumi",
                "api",
                "ListAllVCSIntegrations",
                "-F",
                f"orgName={organization}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return json.loads(result.stdout).get("integrations") or []
    except (OSError, subprocess.SubprocessError, ValueError):
        pass

    creds = _pulumi_credentials()
    if creds is None:
        raise OSError("no Pulumi Cloud credentials found")
    api_url, token = creds
    request = urllib.request.Request(
        f"{api_url}/api/console/orgs/{organization}/integrations",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.pulumi+8",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response).get("integrations") or []


def _detect_installation_id(
    organization: str, vcs_provider: str, repository: str
) -> str | None:
    """Finds the org's VCS integration whose account matches the repository owner.

    Pulumi Cloud lists the integrations (e.g. one per GitHub account) installed in the org. When the
    org has several of the same provider, the one named after the repository owner is the right one.
    Returns None if the lookup is unavailable or nothing matches, so the service's own resolution
    applies.
    """
    owner = repository.split("/")[0].lower()
    if not owner:
        return None
    try:
        integrations = _list_vcs_integrations(organization)
    except (OSError, ValueError) as e:
        pulumi.log.warn(
            f"Could not list VCS integrations to detect installation_id: {e}"
        )
        return None
    for integration in integrations:
        if (
            integration.get("vcsProvider") == vcs_provider
            and str(integration.get("name", "")).lower() == owner
        ):
            return integration.get("id")
    return None


class StackDeploymentSettingsArgs(TypedDict):
    repository: pulumi.Input[str] | None
    """The repository to deploy from, e.g. 'my-org/my-repo' for GitHub. Defaults to the local git 'origin' remote."""

    organization: pulumi.Input[str] | None
    """The Pulumi organization that owns the stack. Defaults to the organization of the stack running this program."""

    project: pulumi.Input[str] | None
    """The Pulumi project of the stack. Defaults to the project running this program."""

    stack: pulumi.Input[str] | None
    """The name of the stack to configure. Defaults to the stack running this program."""

    vcs_provider: pulumi.Input[str] | None
    """The VCS integration to use: 'github' (default), 'gitlab', 'bitbucket', 'azure_devops' or 'custom'. The integration must already be set up in the Pulumi org."""

    installation_id: pulumi.Input[str] | None
    """The ID of the VCS integration (e.g. the GitHub account) to use. Defaults to the org's integration of the same provider whose account name matches the repository owner; if none matches, Pulumi Cloud picks one."""

    branch: pulumi.Input[str] | None
    """The branch to deploy. Defaults to the locally checked-out branch, else 'main'."""

    repo_dir: pulumi.Input[str] | None
    """The folder within the repository that contains the project's Pulumi.yaml. Defaults to the program's folder in the local git checkout."""

    deploy_commits: pulumi.Input[bool] | None
    """Run `pulumi up` when commits are pushed to the branch. Defaults to false."""

    preview_pull_requests: pulumi.Input[bool] | None
    """Run `pulumi preview` when a pull request is opened against the branch. Defaults to true."""

    paths: pulumi.Input[list[pulumi.Input[str]]] | None
    """Only trigger deployments for changes under these repository paths (glob patterns). Defaults to the repo dir plus any local-path packages in Pulumi.yaml."""

    agent_pool_id: pulumi.Input[str] | None
    """The ID of a customer-managed agent (runner) pool, or 'pulumi-provided-runners' to use Pulumi Cloud hosted runners. Defaults to Pulumi-hosted runners."""

    executor_image: pulumi.Input[str] | None
    """A custom executor image, e.g. 'pulumi/pulumi-python:latest'. Defaults to the Pulumi-provided image."""

    environment_variables: pulumi.Input[dict[str, pulumi.Input[str]]] | None
    """Environment variables to set for the deployment. Wrap sensitive values with pulumi.Output.secret()."""

    pre_run_commands: pulumi.Input[list[pulumi.Input[str]]] | None
    """Shell commands to run before the Pulumi operation executes."""

    cache_dependencies: pulumi.Input[bool] | None
    """Cache the program's dependencies (e.g. pip packages) between deployments. Defaults to true."""


class StackDeploymentSettings(pulumi.ComponentResource):
    stack_name: pulumi.Output[str]
    """The fully qualified name ('org/project/stack') of the stack the settings apply to."""

    def __init__(
        self,
        name: str,
        args: StackDeploymentSettingsArgs,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__(
            "deployment-settings:index:StackDeploymentSettings", name, {}, opts
        )

        child_opts = pulumi.ResourceOptions(parent=self)

        def arg(key: str, default=None):
            value = args.get(key)
            return default if value is None else value

        organization = arg("organization", pulumi.get_organization())
        project = arg("project", pulumi.get_project())
        stack = arg("stack", pulumi.get_stack())

        # Fill anything not provided from the local git checkout of the calling program.
        repository = arg("repository") or _detect_repository()
        if not repository:
            raise ValueError(
                f"{name}: could not determine the repository from git in {os.getcwd()}; "
                "set the 'repository' input."
            )
        vcs_provider = arg("vcs_provider", _DEFAULT_VCS_PROVIDER)

        # With several integrations of one provider (e.g. multiple GitHub accounts), pick the one
        # matching the repository owner. Only possible when the inputs are plain strings.
        installation_id = args.get("installation_id")
        if (
            installation_id is None
            and isinstance(organization, str)
            and isinstance(repository, str)
            and isinstance(vcs_provider, str)
        ):
            installation_id = _detect_installation_id(
                organization, vcs_provider, repository
            )

        branch = arg("branch") or _detect_branch() or _DEFAULT_BRANCH
        repo_dir = arg("repo_dir", _detect_repo_dir())
        paths = arg("paths") or pulumi.Output.from_input(repo_dir).apply(
            _detect_trigger_paths
        )

        # An unset agent pool runs deployments on Pulumi Cloud hosted runners;
        # 'pulumi-provided-runners' selects them explicitly.
        agent_pool_id = pulumi.Output.from_input(args.get("agent_pool_id")).apply(
            lambda pool: None if pool == PULUMI_PROVIDED_RUNNERS else pool
        )

        executor_context = None
        executor_image = args.get("executor_image")
        if executor_image is not None:
            executor_context = pulumiservice.DeploymentSettingsExecutorContextArgs(
                executor_image=executor_image,
            )

        settings = pulumiservice.DeploymentSettings(
            f"{name}-deployment-settings",
            organization=organization,
            project=project,
            stack=stack,
            agent_pool_id=agent_pool_id,
            executor_context=executor_context,
            vcs=pulumiservice.DeploymentSettingsVcsArgs(
                provider=vcs_provider,
                repository=repository,
                installation_id=installation_id,
                deploy_commits=arg("deploy_commits", False),
                preview_pull_requests=arg("preview_pull_requests", True),
                paths=paths,
            ),
            # With a VCS integration, the repo URL and auth come from the integration;
            # only the branch and project folder are needed here.
            source_context=pulumiservice.DeploymentSettingsSourceContextArgs(
                git=pulumiservice.DeploymentSettingsGitSourceArgs(
                    branch=branch,
                    # An empty repo dir means the repo root, which is the service default.
                    repo_dir=pulumi.Output.from_input(repo_dir).apply(
                        lambda d: d or None
                    ),
                )
            ),
            cache_options=pulumiservice.DeploymentSettingsCacheOptionsArgs(
                enable=arg("cache_dependencies", True),
            ),
            operation_context=pulumiservice.DeploymentSettingsOperationContextArgs(
                environment_variables=args.get("environment_variables"),
                pre_run_commands=args.get("pre_run_commands"),
            ),
            opts=child_opts,
        )

        self.stack_name = pulumi.Output.concat(
            settings.organization, "/", settings.project, "/", settings.stack
        )

        self.register_outputs({"stack_name": self.stack_name})
