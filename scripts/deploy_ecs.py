"""Deploy one digest to the existing MCP service; never log task definition content."""

import argparse
import copy
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.request

REGION = "us-east-1"
ACCOUNT = "339712838008"
CLUSTER = "tiangong-ai-mcp"
SERVICE = "tiangong-ai-mcp-service"
SERVICE_ARN = f"arn:aws:ecs:{REGION}:{ACCOUNT}:service/{CLUSTER}/{SERVICE}"
FAMILY = "tiangong-ai-mcp-task"
CONTAINER = "tiangong-ai-mcp"
REPOSITORY = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/tiangong-ai-mcp"
EXECUTION_ROLE = f"arn:aws:iam::{ACCOUNT}:role/TiangongAIMCPTaskExecutionRole"
LOG_GROUP = "/ecs/tiangong-ai-mcp-task"
LEGACY_EXECUTION_ROLE = f"arn:aws:iam::{ACCOUNT}:role/ecsTaskExecutionRole"
TASK_FIELDS = {
    "family", "taskRoleArn", "executionRoleArn", "networkMode", "containerDefinitions",
    "volumes", "placementConstraints", "requiresCompatibilities", "cpu", "memory",
    "pidMode", "ipcMode", "proxyConfiguration", "inferenceAccelerators",
    "ephemeralStorage", "runtimePlatform", "enableFaultInjection",
}
READ_ONLY_FIELDS = {
    "taskDefinitionArn", "revision", "status", "requiresAttributes", "compatibilities",
    "registeredAt", "registeredBy", "deregisteredAt",
}


class DeploymentError(RuntimeError):
    pass


class Aws:
    def call(self, *args, payload=None):
        command = ["aws", "--region", REGION, "--no-cli-pager", *args]
        path = None
        try:
            if payload is not None:
                # Existing environment values can be sensitive. Never put them in argv/logs.
                descriptor, path = tempfile.mkstemp(prefix="mcp-task-", suffix=".json")
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(payload, stream)
                command += ["--cli-input-json", f"file://{path}"]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode:
                raise DeploymentError(f"AWS {args[0]} {args[1]} failed ({result.returncode})")
            return json.loads(result.stdout) if result.stdout.strip() else {}
        finally:
            if path is not None:
                Path(path).unlink(missing_ok=True)


def describe_service(aws):
    response = aws.call("ecs", "describe-services", "--cluster", CLUSTER, "--services", SERVICE)
    if response.get("failures") or len(response.get("services", [])) != 1:
        raise DeploymentError("Expected exactly one existing MCP service")
    service = response["services"][0]
    if service.get("serviceArn") != SERVICE_ARN or service.get("status") != "ACTIVE":
        raise DeploymentError("Unexpected service identity or status")
    return service


def render_task_definition(definition, image):
    if not re.fullmatch(re.escape(REPOSITORY) + r"@sha256:[0-9a-f]{64}", image):
        raise DeploymentError("Expected an immutable digest in the MCP ECR repository")
    if set(definition) - TASK_FIELDS - READ_ONLY_FIELDS:
        raise DeploymentError("Unrecognized task definition fields; inspect before deployment")
    if (definition.get("family") != FAMILY or definition.get("cpu") != "256"
            or definition.get("memory") != "512"
            or definition.get("runtimePlatform", {}).get("cpuArchitecture") != "ARM64"):
        raise DeploymentError("MCP task family, capacity or architecture changed")
    if definition.get("executionRoleArn") != EXECUTION_ROLE:
        raise DeploymentError("Unexpected task execution role")
    if definition.get("taskRoleArn"):
        raise DeploymentError("MCP task must not carry an application AWS role")
    payload = copy.deepcopy({key: value for key, value in definition.items() if key in TASK_FIELDS})
    payload.pop("taskRoleArn", None)
    payload["executionRoleArn"] = EXECUTION_ROLE
    containers = [item for item in payload["containerDefinitions"] if item["name"] == CONTAINER]
    if len(payload["containerDefinitions"]) != 1 or len(containers) != 1 or not any(item.get("containerPort") == 80 for item in containers[0].get("portMappings", [])):
        raise DeploymentError("Expected the existing MCP container on port 80")
    logging = containers[0].get("logConfiguration", {})
    options = logging.get("options", {})
    if (logging.get("logDriver") != "awslogs"
            or options.get("awslogs-group") != LOG_GROUP
            or options.get("awslogs-region") != REGION
            or options.get("awslogs-create-group") not in {None, "true", "false"}):
        raise DeploymentError("Unexpected MCP log destination or creation setting")
    if options.get("awslogs-create-group") != "false":
        raise DeploymentError("Approved template must disable log-group creation")
    secret_refs = {item.get("name"): item.get("valueFrom") for item in containers[0].get("secrets", [])}
    if len(containers[0].get("secrets", [])) != 2 or set(secret_refs) != {"UPSTASH_REDIS_URL", "UPSTASH_REDIS_TOKEN"}:
        raise DeploymentError("Expected only the dedicated MCP Redis secret keys")
    secret_arns = set()
    for name, reference in secret_refs.items():
        pattern = (f"arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:tiangong-ai/mcp/runtime-"
                   r"[A-Za-z0-9]{6}:" + name + r"::")
        if not isinstance(reference, str) or not re.fullmatch(pattern, reference):
            raise DeploymentError("Unexpected MCP runtime secret reference")
        secret_arns.add(reference.rsplit(":", 3)[0])
    if len(secret_arns) != 1:
        raise DeploymentError("Redis references must use one dedicated runtime secret")
    if any(item.get("name") in secret_refs for item in containers[0].get("environment", [])):
        raise DeploymentError("Approved template must not include plaintext Redis values")
    containers[0]["image"] = image
    return payload


def verify_running(aws, task_definition, image=None, digest=None):
    service = describe_service(aws)
    if (service.get("taskDefinition") != task_definition
            or service.get("pendingCount") != 0
            or service.get("runningCount") != service.get("desiredCount")
            or service.get("desiredCount", 0) < 1
            or len(service.get("deployments", [])) != 1):
        raise DeploymentError("Service did not stabilize on the intended task definition")
    response = aws.call("ecs", "list-tasks", "--cluster", CLUSTER, "--service-name", SERVICE, "--desired-status", "RUNNING")
    arns = response.get("taskArns", [])
    if len(arns) != service["desiredCount"] or len(arns) > 100:
        raise DeploymentError("Running task inventory does not match desired count")
    response = aws.call("ecs", "describe-tasks", "--cluster", CLUSTER, "--tasks", *arns)
    if response.get("failures") or len(response.get("tasks", [])) != len(arns):
        raise DeploymentError("Incomplete running task descriptions")
    for task in response["tasks"]:
        if task.get("lastStatus") != "RUNNING" or task.get("taskDefinitionArn") != task_definition:
            raise DeploymentError("A running task uses the wrong task definition")
        containers = [item for item in task.get("containers", []) if item.get("name") == CONTAINER]
        if len(containers) != 1:
            raise DeploymentError("MCP container missing from a running task")
        if image is not None and (containers[0].get("image") != image
                or containers[0].get("imageDigest") != image.split("@", 1)[1]):
            raise DeploymentError("A running MCP container uses the wrong immutable image")
        if digest is not None and containers[0].get("imageDigest") != digest:
            raise DeploymentError("A retained MCP container uses the wrong prior digest")
    return arns


def verify_public_http():
    checks = {}
    requests = [
        ("health", urllib.request.Request("https://mcp.tiangong.earth/health"), 200),
        ("unauthenticatedMcp", urllib.request.Request(
            "https://mcp.tiangong.earth/mcp", data=b'{}',
            headers={"Content-Type": "application/json"}, method="POST"), 401),
    ]
    for name, request, expected in requests:
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
        except (urllib.error.URLError, TimeoutError) as error:
            raise DeploymentError("Public HTTP probe failed") from error
        if status != expected:
            raise DeploymentError(f"Public {name} probe returned unexpected status {status}")
        checks[name] = status
    return checks


def deploy(aws, image, definition, source_revision, execute=False, receipt=None, http_check=verify_public_http):
    service = describe_service(aws)
    previous = service["taskDefinition"]
    configuration = service.get("deploymentConfiguration", {})
    breaker = configuration.get("deploymentCircuitBreaker", {})
    if (service.get("desiredCount") != 1 or configuration.get("minimumHealthyPercent") != 100
            or configuration.get("maximumPercent") != 200
            or breaker.get("enable") is not True or breaker.get("rollback") is not True):
        raise DeploymentError("Expected desired=1 and existing 100/200 circuit-breaker rollout guards")
    if not re.fullmatch(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{FAMILY}:[0-9]+", previous):
        raise DeploymentError("Unexpected prior task definition identity")
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise DeploymentError("Expected a complete source revision")
    if previous != f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{FAMILY}:1":
        response = aws.call("ecs", "list-tags-for-resource", "--resource-arn", previous)
        tags = {item["key"]: item["value"] for item in response.get("tags", [])}
        if (tags.get("Application") != "tiangong-ai-mcp"
                or tags.get("Repository") != "tiangong-ai/mcp-server"
                or tags.get("DeploymentKind") not in {"candidate", "rollback"}
                or not re.fullmatch(r"[0-9a-f]{40}", tags.get("DeploymentCommit", ""))):
            raise DeploymentError("The prior task definition is outside controlled deployment lineage")
    payload = render_task_definition(definition, image)
    result = {"sourceRevision": source_revision,
              "templateDigest": "sha256:" + hashlib.sha256(json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
              "serviceArn": SERVICE_ARN, "previousTaskDefinition": previous, "image": image, "status": "planned"}
    if not execute:
        return result
    groups = aws.call("logs", "describe-log-groups", "--log-group-name-prefix", LOG_GROUP).get("logGroups", [])
    if len([group for group in groups if group.get("logGroupName") == LOG_GROUP]) != 1:
        raise DeploymentError("The exact existing MCP log group is required before role migration")
    task_arns = verify_running(aws, previous)
    response = aws.call("ecs", "describe-tasks", "--cluster", CLUSTER, "--tasks", *task_arns)
    tasks = response.get("tasks", [])
    if response.get("failures") or len(tasks) != len(task_arns):
        raise DeploymentError("Incomplete prior task image snapshot")
    prior_images = set()
    for task in tasks:
        if task.get("taskDefinitionArn") != previous or task.get("lastStatus") != "RUNNING":
            raise DeploymentError("Prior task identity changed during rollback qualification")
        container = next(item for item in task["containers"] if item["name"] == CONTAINER)
        digest = container.get("imageDigest", "")
        if (not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                or not container.get("image", "").startswith(REPOSITORY + ":")
                and not container.get("image", "").startswith(REPOSITORY + "@")):
            raise DeploymentError("Cannot qualify an immutable prior MCP image for rollback")
        prior_images.add(REPOSITORY + "@" + digest)
    if len(prior_images) != 1:
        raise DeploymentError("Prior running tasks disagree on image digest")
    if previous.endswith(":1"):
        approved_image = next(item["image"] for item in definition["containerDefinitions"]
                              if item["name"] == CONTAINER)
        if prior_images != {approved_image}:
            raise DeploymentError("Bootstrap running image differs from the reviewed original image")
    rollback_payload = render_task_definition(definition, prior_images.pop())

    def register(request, kind):
        request = {**request, "tags": [
            {"key": "Application", "value": "tiangong-ai-mcp"},
            {"key": "Repository", "value": "tiangong-ai/mcp-server"},
            {"key": "DeploymentCommit", "value": source_revision},
            {"key": "DeploymentKind", "value": kind},
        ]}
        response = aws.call("ecs", "register-task-definition", payload=request)
        registered = response["taskDefinition"]
        arn = registered["taskDefinitionArn"]
        if not re.fullmatch(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{FAMILY}:[0-9]+", arn):
            raise DeploymentError("Registration returned an unexpected task definition")
        if (any(registered.get(key) != value for key, value in request.items() if key != "tags")
                or sorted(response.get("tags", []), key=lambda item: item["key"])
                != sorted(request["tags"], key=lambda item: item["key"])):
            raise DeploymentError("Registered task definition differs from requested runtime settings")
        return arn

    # A rollback definition uses the exact prior running image and dedicated role.
    # Neither registration nor rollback requires passing the broad legacy role.
    rollback = register(rollback_payload, "rollback")
    result["rollbackTaskDefinition"] = rollback
    result["rollbackImage"] = next(item["image"] for item in rollback_payload["containerDefinitions"]
                                   if item["name"] == CONTAINER)
    result["status"] = "rollback-prepared"
    save_receipt(receipt, result)
    candidate = register(payload, "candidate")
    result["taskDefinition"] = candidate
    result["status"] = "registered"
    save_receipt(receipt, result)
    bootstrap = previous.endswith(":1")
    baseline = previous
    migration_verified = not bootstrap
    try:
        if describe_service(aws)["taskDefinition"] != previous:
            raise DeploymentError("Service changed before deployment; no update performed")
        if bootstrap:
            # Qualify secret/role migration on the prior image before changing product code.
            aws.call("ecs", "update-service", "--cluster", CLUSTER, "--service", SERVICE,
                     "--task-definition", rollback)
            result["status"] = "migrating-baseline"
            save_receipt(receipt, result)
            aws.call("ecs", "wait", "services-stable", "--cluster", CLUSTER, "--services", SERVICE)
            verify_running(aws, rollback, result["rollbackImage"])
            result["migrationHttpChecks"] = http_check()
            baseline = rollback
            migration_verified = True
            result["status"] = "baseline-migration-verified"
            save_receipt(receipt, result)
        if describe_service(aws)["taskDefinition"] != baseline:
            raise DeploymentError("Service changed before candidate rollout; no update performed")
        aws.call("ecs", "update-service", "--cluster", CLUSTER, "--service", SERVICE,
                 "--task-definition", candidate)
        result["status"] = "deploying"
        save_receipt(receipt, result)
        aws.call("ecs", "wait", "services-stable", "--cluster", CLUSTER, "--services", SERVICE)
        result["tasks"] = verify_running(aws, candidate, image)
        result["publicHttpChecks"] = http_check()
        result["authenticatedToolsList"] = "not-run-in-ci; independent operator verification"
        result["status"] = "verified"
        save_receipt(receipt, result)
        return result
    except DeploymentError as original_error:
        try:
            observed = describe_service(aws)
            current = observed["taskDefinition"]
            result["observedTaskDefinition"] = current
            result["observedRunningCount"] = observed.get("runningCount")
            result["observedPendingCount"] = observed.get("pendingCount")
            if bootstrap and not migration_verified:
                if current == previous:
                    verify_running(aws, previous, digest=result["rollbackImage"].split("@", 1)[1])
                    result["status"] = "bootstrap-migration-failed-legacy-retained"
                elif current == rollback:
                    result["status"] = "bootstrap-migration-not-qualified"
                else:
                    result["status"] = "rollback-skipped-concurrent-change"
                # Never grant/pass the legacy role or deploy new code after migration failure.
            elif current == candidate:
                aws.call("ecs", "update-service", "--cluster", CLUSTER, "--service", SERVICE,
                         "--task-definition", rollback)
                aws.call("ecs", "wait", "services-stable", "--cluster", CLUSTER, "--services", SERVICE)
                verify_running(aws, rollback, result["rollbackImage"])
                result["status"] = "rolled-back"
            elif current == baseline:
                verify_running(aws, baseline, result["rollbackImage"] if bootstrap else None)
                result["status"] = "qualified-baseline-retained" if bootstrap else "previous-task-definition-retained"
            else:
                result["status"] = "rollback-skipped-concurrent-change"
        except DeploymentError:
            result["status"] = "rollback-verification-failed"
            save_receipt(receipt, result)
            raise DeploymentError("Deployment failed and rollback could not be verified; inspect receipt/live state") from original_error
        save_receipt(receipt, result)
        raise original_error



def save_receipt(path, result):
    if path:
        Path(path).write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--template", default="deployment/task-definition.json")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--execute", action="store_true", help="Update only the existing MCP service")
    parser.add_argument("--receipt", required=True, help="Sanitized image/task identity evidence")
    args = parser.parse_args()
    try:
        definition = json.loads(Path(args.template).read_text())
        result = deploy(Aws(), args.image, definition, args.source_revision,
                        execute=args.execute, receipt=args.receipt)
        save_receipt(args.receipt, result)
        print(json.dumps(result))
    except DeploymentError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
