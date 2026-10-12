"""Deploy one digest to the existing MCP service; never log task definition content."""

import argparse
import copy
import json
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
    if definition.get("executionRoleArn") not in {LEGACY_EXECUTION_ROLE, EXECUTION_ROLE}:
        raise DeploymentError("Unexpected task execution role")
    if definition.get("taskRoleArn"):
        raise DeploymentError("MCP task must not carry an application AWS role")
    payload = copy.deepcopy({key: value for key, value in definition.items() if key in TASK_FIELDS})
    payload.pop("taskRoleArn", None)
    payload["executionRoleArn"] = EXECUTION_ROLE
    containers = [item for item in payload["containerDefinitions"] if item["name"] == CONTAINER]
    if len(containers) != 1 or not any(item.get("containerPort") == 80 for item in containers[0].get("portMappings", [])):
        raise DeploymentError("Expected the existing MCP container on port 80")
    logging = containers[0].get("logConfiguration", {})
    options = logging.get("options", {})
    if (logging.get("logDriver") != "awslogs"
            or options.get("awslogs-group") != LOG_GROUP
            or options.get("awslogs-region") != REGION
            or options.get("awslogs-create-group") not in {None, "true", "false"}):
        raise DeploymentError("Unexpected MCP log destination or creation setting")
    options["awslogs-create-group"] = "false"
    containers[0]["image"] = image
    return payload


def verify_running(aws, task_definition, image=None):
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


def deploy(aws, image, execute=False, receipt=None, http_check=verify_public_http):
    service = describe_service(aws)
    previous = service["taskDefinition"]
    if not re.fullmatch(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{FAMILY}:[0-9]+", previous):
        raise DeploymentError("Unexpected prior task definition identity")
    definition = aws.call("ecs", "describe-task-definition", "--task-definition", previous)["taskDefinition"]
    payload = render_task_definition(definition, image)
    result = {"serviceArn": SERVICE_ARN, "previousTaskDefinition": previous, "image": image, "status": "planned"}
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
    rollback_payload = render_task_definition(definition, prior_images.pop())

    def register(request):
        registered = aws.call("ecs", "register-task-definition", payload=request)["taskDefinition"]
        arn = registered["taskDefinitionArn"]
        if not re.fullmatch(f"arn:aws:ecs:{REGION}:{ACCOUNT}:task-definition/{FAMILY}:[0-9]+", arn):
            raise DeploymentError("Registration returned an unexpected task definition")
        if any(registered.get(key) != value for key, value in request.items()):
            raise DeploymentError("Registered task definition differs from requested runtime settings")
        return arn

    # A rollback definition uses the exact prior running image and dedicated role.
    # Neither registration nor rollback requires passing the broad legacy role.
    rollback = register(rollback_payload)
    result["rollbackTaskDefinition"] = rollback
    result["rollbackImage"] = next(item["image"] for item in rollback_payload["containerDefinitions"]
                                   if item["name"] == CONTAINER)
    result["status"] = "rollback-prepared"
    save_receipt(receipt, result)
    candidate = register(payload)
    result["taskDefinition"] = candidate
    result["status"] = "registered"
    save_receipt(receipt, result)
    try:
        # Revalidate against out-of-band changes immediately before updating the service.
        if describe_service(aws)["taskDefinition"] != previous:
            raise DeploymentError("Service changed before deployment; no update performed")
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
    except DeploymentError:
        current = describe_service(aws)["taskDefinition"]
        if current == candidate:
            aws.call("ecs", "update-service", "--cluster", CLUSTER, "--service", SERVICE,
                     "--task-definition", rollback)
            aws.call("ecs", "wait", "services-stable", "--cluster", CLUSTER, "--services", SERVICE)
            verify_running(aws, rollback, result["rollbackImage"])
            result["status"] = "rolled-back"
        elif current == previous:
            verify_running(aws, previous)
            result["status"] = "previous-task-definition-retained"
        else:
            result["status"] = "rollback-skipped-concurrent-change"
        save_receipt(receipt, result)
        raise


def save_receipt(path, result):
    if path:
        Path(path).write_text(json.dumps(result, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--execute", action="store_true", help="Update only the existing MCP service")
    parser.add_argument("--receipt", required=True, help="Sanitized image/task identity evidence")
    args = parser.parse_args()
    try:
        result = deploy(Aws(), args.image, execute=args.execute, receipt=args.receipt)
        save_receipt(args.receipt, result)
        print(json.dumps(result))
    except DeploymentError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
