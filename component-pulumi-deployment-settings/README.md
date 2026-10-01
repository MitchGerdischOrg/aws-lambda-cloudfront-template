# component-pulumi-deployment-settings

A Python multi-language Pulumi component package that configures [Pulumi Deployments](https://www.pulumi.com/docs/pulumi-cloud/deployments/) settings for a stack using the [Pulumi Cloud (pulumiservice) provider](https://www.pulumi.com/registry/packages/pulumiservice/).

- `StackDeploymentSettings`: creates a `pulumiservice.DeploymentSettings` resource that wires a stack to a repository through a Pulumi Cloud VCS integration (GitHub by default), with PR previews, optional push-to-deploy, a customer-managed runner pool, environment variables, pre-run commands, and dependency caching (on by default).

## Prerequisites

- The VCS integration (e.g. the Pulumi GitHub App) is installed in your Pulumi org and has access to the repository.
- The stack being configured already exists (`pulumi stack init`).
- Wherever `pulumi up` is run for the program using this component, Pulumi Cloud credentials are available (e.g. `pulumi login` or `PULUMI_ACCESS_TOKEN`). The pulumiservice provider uses them.

## Usage

### Add the package to `Pulumi.yaml`

```
packages:
  # versioning is optional
  deployment-settings: https://GITREPO-PATH/component-pulumi-deployment-settings[@v1.0.0]
```

Run `pulumi install` (or `pulumi package add https://GITREPO-PATH/component-pulumi-deployment-settings[@v1.0.0]` - version is optional) to generate the local SDK.

These commands will also provide the python import code for referencing the component.

### Python

With no inputs at all, the component configures the stack running the program, deploying from the program's own git checkout on Pulumi Cloud hosted runners:

```python
import pulumi
import XXXX_deployment_settings as deployment_settings

settings = deployment_settings.StackDeploymentSettings(
    "deployment-settings",
    # Everything below is optional.
    repository="my-github-org/aws-ecs-cloudfront-project",
    branch="main",
    repo_dir="aws-ecs-cloudfront-py",
    agent_pool_id="<runner-pool-id>",            # customer-managed runners, or "pulumi-provided-runners"
    deploy_commits=True,                         # run `pulumi up` on pushes (off by default)
)

pulumi.export("deployment_settings_stack", settings.stack_name)
```

### Values detected from git

Anything not passed in is filled from the local git checkout of the calling program. The component provider runs in the program's directory, so it sees the program's repo:

- `repository`: the `origin` remote URL converted to `owner/repo` (https, ssh, and `git@host:owner/repo` forms).
- `branch`: the checked-out branch. On a detached HEAD it uses the remote's default branch, and falls back to `main`.
- `repoDir`: the program folder's path relative to the repo root.
- `paths`: `repoDir/**`, plus the folder of every local-path (`./` or `../`) package in `Pulumi.yaml` that is inside the repo, so changes to in-repo components also trigger deployments.
- `installationId`: when the Pulumi org has several VCS integrations of the same provider (e.g. multiple GitHub accounts), the integration whose account name matches the repository owner. This is looked up through the Pulumi Cloud API using the current login (`PULUMI_ACCESS_TOKEN` or `~/.pulumi/credentials.json`). If the lookup fails or nothing matches, the input is left unset and Pulumi Cloud chooses. Pass `installation_id` to override.

Because `branch` follows the checkout, running `pulumi up` from a feature branch changes the deployment branch. Pass `branch` explicitly to keep it fixed. If no repository can be detected (no git or no `origin` remote), the component fails and asks for `repository`.

To configure a different stack (e.g. from a separate "platform" project that manages settings for many stacks), set `organization`, `project`, and `stack` explicitly.

Sensitive environment variables should be wrapped as secrets so they are stored encrypted in Pulumi Cloud:

```python
environment_variables={
    "LOG_LEVEL": "info",
    "API_TOKEN": config.require_secret("apiToken"),  # already a secret Output
},
```

## Inputs and outputs

| Input | Default | Description |
|-------|---------|-------------|
| `repository` | local git `origin` remote | Repository to deploy from, e.g. `org/repo` for GitHub. |
| `organization` | current org | Pulumi org that owns the stack. |
| `project` | current project | Pulumi project of the stack. |
| `stack` | current stack | Stack to configure. |
| `vcsProvider` | `github` | `github`, `gitlab`, `bitbucket`, `azure_devops`, or `custom`. |
| `branch` | checked-out branch, else `main` | Branch to deploy. |
| `repoDir` | program's folder in the repo | Folder containing the project's `Pulumi.yaml`. |
| `deployCommits` | `false` | Run `pulumi up` on pushes to the branch. |
| `previewPullRequests` | `true` | Run `pulumi preview` on pull requests. |
| `paths` | `repoDir` + local packages in `Pulumi.yaml` | Only trigger on changes under these paths. |
| `agentPoolId` | Pulumi-hosted | Customer-managed runner pool ID, or `pulumi-provided-runners` to use Pulumi-hosted runners. |
| `executorImage` | Pulumi default | Custom executor image. |
| `environmentVariables` | | Env vars for the deployment. |
| `preRunCommands` | | Shell commands run before the Pulumi operation. |
| `cacheDependencies` | `true` | Cache the program's dependencies between deployments. |

| Output | Description |
|--------|-------------|
| `stackName` | Fully qualified `org/project/stack` the settings apply to. |
