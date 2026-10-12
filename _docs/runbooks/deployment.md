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
lastReviewedCommit: 0bfd160b108c997d71d33a08935bb4bcafa44fdb
---

# MCP Source Image Deployment

## Entry point and ownership

`.github/workflows/deploy.yml` validates pull requests and automatically deploys reviewed `main` pushes that change source, build or deployment inputs. Manual `workflow_dispatch` is supported only on `main`. The GitHub `production` environment must permit only `main`; the deploy job also checks the exact repository/ref and excludes pull-request events. Concurrent deployments queue rather than cancelling an in-progress rollout. CI checks the fresh remote `main` SHA after image validation and before OIDC, and the helper rechecks before forward service updates. A source advance during bootstrap stops candidate rollout and retains the qualified baseline. An old workflow rerun is not a rollback mechanism.

This repository owns its source image and deployment workflow. Shared AWS IAM, ECR/ECS infrastructure and production environment configuration remain with the infrastructure owner. No static AWS credentials or npm publishing token is used. The source image does not install the published MCP package; npm distribution is independent of this deployment path.

## Source image gates

`Dockerfile` builds the checked-out TypeScript source with a digest-pinned Node 22 Alpine base, verifies the public tool inventory, and copies only production dependencies, package metadata and compiled code into the final image. Build output is cleared first so deleted modules cannot remain. Existing repository convention ignores `package-lock.json`; image install/prune explicitly avoid creating a tracked lockfile. The runtime Zod range is restored to the published/production-compatible `^3.25.76` line (latest stable Zod 3 verified in npm); other dependency ranges are unchanged. The source baseline had an unpublished Zod 4 shift that omitted object `additionalProperties=false` from the wire schemas. That migration needs separate qualification; this deployment preserves the nine live tool definitions. Builds do not claim byte-for-byte dependency reproducibility; the tested final image records its actual resolved dependency versions in `runtime-dependencies.json`.

CI builds `linux/arm64` on native `ubuntu-24.04-arm` runners, matching the existing ECS task ([GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)). It runs the final image's offline MCP registry test with networking disabled, verifies ARM64, and runs mocked deployment safety tests. These checks run before AWS credentials are requested. The image that passes the deploy job's checks is pushed once under a unique commit/run/attempt tag; ECS receives its exact ECR SHA256 digest, never a floating tag. Build attestations are disabled for this single-platform image so the pushed digest is the ARM64 image manifest checked against the running ECS container, rather than a manifest-index digest.

Local equivalents:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py' -v
docker buildx build --platform linux/arm64 --provenance=false --sbom=false --load -t mcp-candidate:local .
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

The approved `deployment/task-definition.json` template is the reviewed runtime configuration authority. It contains only non-sensitive configuration and exact Secrets Manager JSON-key references for `UPSTASH_REDIS_URL` and `UPSTASH_REDIS_TOKEN`. Their values stay in the dedicated secret and are injected by the execution role; CI has no permission to read the secret. The helper rejects plaintext Redis values, foreign references and any application task role. Only the dedicated execution role may be passed; the broad shared role is not required for candidate or rollback registration.

The CI role can read the existing service/tasks, controlled task-definition tags and log-group existence metadata, register tagged own-family task revisions, and update only the existing service. It cannot call `DescribeTaskDefinition`, which has no family resource scope and could expose unrelated plaintext values. It cannot read Secrets Manager values. The execution role has ECR pull, exact existing log-group writes and `GetSecretValue` on the one exact runtime secret. The infrastructure owner maintains the actual permission policy.

## Deployment and rollback

`scripts/deploy_ecs.py` is read-only unless given `--execute`. It reads the existing service/tasks and uses the approved template, rejecting unknown template fields or unexpected target/capacity/role/secret state. The template preserves ports, capacity and supported runtime settings from the reviewed original task; Redis values move from plaintext environment to exact secret references without changing their values. The controlled migration changes the target container image, execution role, Redis environment delivery to Secrets Manager references, and `awslogs-create-group=false`. The log driver/destination must match the exact existing `/ecs/tiangong-ai-mcp-task` group in `us-east-1`; CI proves that group exists before any task registration. The dedicated role cannot create groups. The approved JSON has secret references rather than values; it is still passed through a 0600 runner temporary file, removed immediately, and never printed or uploaded.

The exact original task revision `tiangong-ai-mcp-task:1` is the only bootstrap input. Later service revisions must be in the same family and carry all four controlled registration tags: `Application=tiangong-ai-mcp`, `Repository=tiangong-ai/mcp-server`, `DeploymentCommit=<full source SHA>`, and `DeploymentKind=candidate|rollback`. Unknown lineage fails before mutation. Candidate and rollback registrations include these tags; receipts include the approved template hash for review.

Before rollout, CI qualifies the exact digest shared by the prior running tasks and registers a rollback definition with that image plus the dedicated execution role and secret references. Bootstrap also requires the prior digest to match the reviewed original template. The first deployment rolls out that old-image baseline, waits and verifies its identity/HTTP checks, then rolls out the candidate. This qualifies role/secret migration before replacing product code and gives the ECS breaker a dedicated-role rollback target. If bootstrap fails, CI stops before candidate rollout and reports the observed retained state; it never passes the legacy role. Subsequent controlled deployments can proceed directly to the candidate. The existing desired count 1, minimum healthy 100%, maximum 200%, and enabled rollback circuit breaker are mandatory guards. The script waits for stability and verifies desired/running counts, all running task-definition identities and exact container image digests. The unique deployment must also report `rolloutState=COMPLETED`; stable counts alone do not qualify it. The existing rollout configuration guards are rechecked on every service read before updates.

Public probes require `GET /health = 200` and unauthenticated `POST /mcp = 401` at `https://mcp.tiangong.earth`; `GET /mcp` intentionally returns 405 and is not an authentication probe. No authentication bypass is introduced.

If rollout, task identity or HTTP checks fail, CI rolls back to its prepared rollback definition only while the service still points at its candidate. Observed out-of-band changes stop updates/rollback. ECS Describe→Update has no compare-and-swap guarantee: these identity/configuration checks are best effort. CI is the single deployment writer; manual infrastructure changes must not run concurrently with CI, and must coordinate a pause/inspection through the owner. ECS stability and exact rollback image identity are verified after rollback. A failed deploy remains a failed workflow. Cancellation or runner loss can interrupt cleanup; inspect the receipt and live service before any manual recovery, then use an explicitly qualified task definition rather than replaying a stale deployment.

## Evidence and verification boundary

The artifact `mcp-deployment-<run>-<attempt>` contains only sanitized service, prior/candidate/rollback task identities, image digests, running task IDs, HTTP status checks and deployment/rollback state. A separate `runtime-dependencies.json` records the exact source revision, package/Node version, architecture and resolved production dependency versions from the final image that was tested and pushed. Never attach a full task definition, environment dump or credential. The helper does not delete task revisions or ECR images; retention belongs to infrastructure policy.

CI verifies the nine-tool public contract inside the exact final image, ECS running image identity, health and the authentication boundary. An authenticated live `initialize` plus `tools/list` is a separate operator check using existing client credentials in memory; no credential is uploaded to CI, and no business search tool is called. Record that independent evidence with the exact workflow commit/image/task identity before claiming live retirement complete. A source merge, green offline test or task registration alone is not production completion.
