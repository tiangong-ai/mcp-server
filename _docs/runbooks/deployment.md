---
docType: runbook
scope: repo
status: current
authoritative: true
owner: mcp
language: en
whenToUse: 'When building, deploying, verifying, or recovering the MCP ECS service.'
whenToUpdate: 'When CI triggers, source-image packaging, OIDC, target identities, deployment checks or rollback change.'
checkPaths:
  - Dockerfile
  - .dockerignore
  - .github/workflows/deploy.yml
  - scripts/**
lastReviewedAt: 2026-10-12
lastReviewedCommit: 3f39012edf73bc825944b15647fcce8ae6ad3cae
---

# MCP Source Image Deployment

## Entry point and ownership

`.github/workflows/deploy.yml` validates pull requests and automatically deploys reviewed `main` pushes that change source, build or deployment inputs. Manual `workflow_dispatch` is supported only on `main`. The GitHub `production` environment must permit only `main`; the deploy job also checks the exact repository/ref and excludes pull-request events. Concurrent deployments queue rather than cancelling an in-progress rollout.

This repository owns its source image and deployment workflow. Shared AWS IAM, ECR/ECS infrastructure and production environment configuration remain with the infrastructure owner. No static AWS credentials or npm publishing token is used. The source image does not install the published MCP package; npm distribution is independent of this deployment path.

## Source image gates

`Dockerfile` builds the checked-out TypeScript source with a digest-pinned Node 22 Alpine base, verifies the public tool inventory, and copies only production dependencies, package metadata and compiled code into the final image. Build output is cleared first so deleted modules cannot remain. Existing repository convention ignores `package-lock.json`; image install/prune explicitly avoid creating a tracked lockfile. Dependency ranges are unchanged. Builds do not claim byte-for-byte dependency reproducibility; the tested final image records its actual resolved dependency versions in `runtime-dependencies.json`.

CI builds `linux/arm64` on native `ubuntu-24.04-arm` runners, matching the existing ECS task ([GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)). It runs the final image's offline MCP registry test with networking disabled, verifies ARM64, and runs mocked deployment safety tests. These checks run before AWS credentials are requested. The image that passes the deploy job's checks is pushed once under a unique commit/run/attempt tag; ECS receives its exact ECR SHA256 digest, never a floating tag.

Local equivalents:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
docker buildx build --platform linux/arm64 --load -t mcp-candidate:local .
docker run --rm --network none --entrypoint node mcp-candidate:local dist/src/test_tool_registry.js
actionlint .github/workflows/deploy.yml
```

## OIDC and existing target

The production environment provides `AWS_ROLE_ARN` as a variable. The credentials action enforces account `339712838008`, Region `us-east-1` and short-lived OIDC. The repository currently uses the immutable GitHub subject prefix:

`repo:tiangong-ai@328661783/mcp-server@956466135:environment:production`

The IAM trust also requires audience `sts.amazonaws.com`. Verify live GitHub OIDC configuration and environment branch rules before creating/changing trust; a name-only subject is not equivalent to the current immutable subject.

Deployment is restricted to:

- ECR repository: `339712838008.dkr.ecr.us-east-1.amazonaws.com/tiangong-ai-mcp`.
- ECS cluster: `tiangong-ai-mcp`.
- Existing service: `arn:aws:ecs:us-east-1:339712838008:service/tiangong-ai-mcp/tiangong-ai-mcp-service`.
- Task family: `tiangong-ai-mcp-task`; ARM64, 256 CPU units, 512 MiB.
- Container: `tiangong-ai-mcp`, port 80.
- Dedicated execution role: `arn:aws:iam::339712838008:role/TiangongAIMCPTaskExecutionRole`.

The helper accepts only the original `ecsTaskExecutionRole` or dedicated role as its current execution role, and always registers with the dedicated role. It rejects any nonempty task application role. IAM must not grant the deploy role permission to pass the broad shared execution role. ECR push/pull metadata, exact service/task reads and update, log-group existence reads, task registration, and passing only the dedicated execution role are required; no resource creation/deletion is part of routine CI. The infrastructure owner maintains the actual permission policy.

## Deployment and rollback

`scripts/deploy_ecs.py` is read-only unless given `--execute`. It reads the existing service and active task definition, rejects unknown API fields or unexpected target/capacity/role state, and preserves runtime environment, secret references, ports, logging and all supported task settings. It changes only the target container image, the explicit execution-role migration, and `awslogs-create-group=false`. The log driver/destination must match the exact existing `/ecs/tiangong-ai-mcp-task` group in `us-east-1`; CI proves that group exists before any task registration. The dedicated role cannot create groups. Task-definition JSON can include credentials: it is passed through a 0600 runner temporary file, removed immediately, and never printed or uploaded.

Before rollout, CI qualifies the exact digest shared by the prior running tasks and registers a rollback definition with that image plus the dedicated execution role. It then registers the candidate definition, revalidates that the service still uses the observed prior revision, and updates only that service. The script waits for stability and verifies desired/running counts, all running task-definition identities and exact container image digests.

Public probes require `GET /health = 200` and unauthenticated `POST /mcp = 401` at `https://mcp.tiangong.earth`; `GET /mcp` intentionally returns 405 and is not an authentication probe. No authentication bypass is introduced.

If rollout, task identity or HTTP checks fail, CI rolls back to its prepared rollback definition only while the service still points at its candidate. An out-of-band service change is never overwritten. ECS stability and exact rollback image identity are verified after rollback. A failed deploy remains a failed workflow. Cancellation or runner loss can interrupt cleanup; inspect the receipt and live service before any manual recovery, then use an explicitly qualified task definition rather than replaying a stale deployment.

## Evidence and verification boundary

The artifact `mcp-deployment-<run>-<attempt>` contains only sanitized service, prior/candidate/rollback task identities, image digests, running task IDs, HTTP status checks and deployment/rollback state. A separate `runtime-dependencies.json` records the exact source revision, package/Node version, architecture and resolved production dependency versions from the final image that was tested and pushed. Never attach a full task definition, environment dump or credential. The helper does not delete task revisions or ECR images; retention belongs to infrastructure policy.

CI verifies the nine-tool public contract inside the exact final image, ECS running image identity, health and the authentication boundary. An authenticated live `initialize` plus `tools/list` is a separate operator check using existing client credentials in memory; no credential is uploaded to CI, and no business search tool is called. Record that independent evidence with the exact workflow commit/image/task identity before claiming live retirement complete. A source merge, green offline test or task registration alone is not production completion.
