# aws-lambda-cloudfront-project
Pulumi project that deploys a simple Python Lambda app behind a CloudFront CDN and uses component resources.

The app code lives in `./app` alongside the infrastructure code, and is packaged and deployed by `pulumi up`.

# Set Up Steps

- Create an empty repo and clone it.
- In the repo folder, run `pulumi new https://github.com/MitchGerdischOrg/aws-lambda-cloudfront-template`
  - You are prompted for the project name, description, stack name, and `agentPoolId`.
  - `agentPoolId` is the Pulumi Deployments agent pool ID to run deployments on. Accept the default, `pulumi-provided-runners`, to use Pulumi Cloud hosted runners.
  - Change it later with `pulumi config set agentPoolId <value>`.
 
## Set up the Component Packages

The repo contains two component resource packages in separate folders. 
One abstracts the code for packaging and deploying the Lambda function (with its IAM role, logging and function URL) and the other abstracts the deployment settings.
Although the components can can be used as locally referenced components, for this exercise, we will work with them as component packages.

Initially, we will install them as local component packages, but later discuss managing them in git repos with semantic versioning.
 
From the Pulumi project folder (where `pulumi new` created the project), run `pulumi package add` to install and set up the two component resource packages. 

- Run `pulumi package add ./component-aws-lambda-services`

- Run `pulumi package add ./component-pulumi-deployment-settings`

The `pulumi package add` command performs the following tasks:
  - It adds a packages directive to the `Pulumi.yaml` file.
  - It creates an `sdks` folder. 
  - It updates `requirements.txt` or similar with the path to the SDKs. 
  - It provides the import lines for the generated SDKs.
    - **ADD** The import lines to `__main__.py`.

*SUBSEQUENTLY*, you only need to run `pulumi install` which will use the `packages` directive in `Pulumi.yaml` to generate the local SDKs

## (Optional) Version and Publish the Component Resources 

You can skip these steps initially, and jump down to "Deploying the Stack" below.

But, to better adopt centrally managed component packages, you can move the components into their own git repos and enable versioning and more centralized management of the components.
If you do so, the Pulumi project code will need to be updated with the proper packages references and related sdk names.

So after moving the components to git repos, you will want to run `pulumi package add` again but point it at the github repo.
For example: `pulumi package add https://GITREPO-PATH-TO-COMPONENT/component-aws-lambda-services`
and similarly for the deployment-settings component.

As before the `pulumi package add` command will udpate `Pulumi.yaml` and provide the import lines for `__main__.py`. You will need to clean up `Pulumi.yaml` to remove the local component references and update `__main__.py` with the new import lines.

Once the components are in their own repos, you can set up versioning for the components:
- Tag the repo with version(s) of the form `vX.Y.Z`.
- In the `packages` directive in `Pulumi.yaml` add `@vX.Y.Z` to use the specific version of the component. 
- Run `pulumi install` before `pulumi up` to udpate to the given version. 

You can also publish the package to the Pulumi Cloud component registry to be able to track usage of the and auto generate API docs.
- Publish the package: `pulumi package publish GITREPO_PATH_TO_COMPONENNT --publisher PULUMI_ORG_NAME`
  - Where `GITREPO_PATH_TO_COMPONENT` is the same path used for the `pulumi package add` command.
  - Where `PULUMI_ORG_NAME` is the name of your Pulumi org.

# Deploying the Stack

##  Runtime Prerequisites

Whereever `pulumi up` is run (laptop, deployment runner, etc) the following needs to be available:
- AWS credentials/access with applicable permissions.
- Your preferred python tooling is available.

## The App

The sample app is `app/handler.py`, a Lambda handler that serves an HTML page at `/` and a JSON health check at `/health`.
Edit the code and run `pulumi up`: the `./app` folder is zipped and the function is updated whenever its contents change.
Dependencies are not installed automatically, so stick to the standard library or vendor packages into `./app`.

The stack exports both the `cloudfront_url` and the raw Lambda `function_url`.

## Initializing and Bootstrapping Deployments

This project is set up such that it requires an initial pulumi up from a laptop to bootstrap the deployment settings using the deployment settings component resource.
In production, the deployment settings could be managed by a completely separate stack that manages the deployment settings for multiple stacks using the same sort of logic captured in the component resource.
But for ease of use, this initial boostrapping approach is used.

```bash
pulumi install
pulumi up
```

# Running from Deployments

**BE SURE** to push the code to the repo you created for the new project before trying to run from Pulumi deployments.

From the Pulumi UI, use the `Actions` button in the upper right when viewing the stack to run udpates, previews, etc.

You can also set things up to run deployments automatically for various conditions:
- Scheduled events such as drift detection or shut down, etc.
- Run previews when a PR is created.
- Run updates when a PR is merged.





