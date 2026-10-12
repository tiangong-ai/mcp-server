"""Offline deployment failure scenarios; no AWS or business requests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import deploy_ecs as deployment

PREVIOUS = f"arn:aws:ecs:{deployment.REGION}:{deployment.ACCOUNT}:task-definition/{deployment.FAMILY}:1"
ROLLBACK = PREVIOUS.rsplit(":", 1)[0] + ":2"
CANDIDATE = PREVIOUS.rsplit(":", 1)[0] + ":3"
FOREIGN = PREVIOUS.rsplit(":", 1)[0] + ":99"
IMAGE = deployment.REPOSITORY + "@sha256:" + "a" * 64
DEFINITION = {
    "taskDefinitionArn": PREVIOUS, "family": deployment.FAMILY, "revision": 1,
    "cpu": "256", "memory": "512", "networkMode": "awsvpc",
    "executionRoleArn": deployment.LEGACY_EXECUTION_ROLE,
    "runtimePlatform": {"cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX"},
    "requiresCompatibilities": ["FARGATE"], "volumes": [],
    "containerDefinitions": [{
        "name": deployment.CONTAINER, "image": deployment.REPOSITORY + ":latest",
        "portMappings": [{"containerPort": 80, "hostPort": 80, "protocol": "tcp"}],
        "environment": [{"name": "UPSTASH_REDIS_TOKEN", "value": "sensitive-test-sentinel"}],
        "secrets": [{"name": "OTHER", "valueFrom": "retained-secret-reference"}],
        "logConfiguration": {"logDriver": "awslogs", "options": {"awslogs-group": deployment.LOG_GROUP, "awslogs-region": deployment.REGION, "awslogs-create-group": "true"}},
    }],
}


class FakeAws:
    def __init__(self, wait_failure=False, wrong_digest=False, concurrent=False):
        self.current = PREVIOUS
        self.definition = copy.deepcopy(DEFINITION)
        self.calls = []
        self.registered = None
        self.definitions = {PREVIOUS: self.definition}
        self.register_count = 0
        self.wait_failure = wait_failure
        self.wrong_digest = wrong_digest
        self.concurrent = concurrent

    def call(self, *args, payload=None):
        self.calls.append((args, copy.deepcopy(payload)))
        action = args[1]
        if action == "describe-log-groups":
            return {"logGroups": [{"logGroupName": deployment.LOG_GROUP}]}
        if action == "describe-services":
            return {"services": [{
                "serviceArn": deployment.SERVICE_ARN, "status": "ACTIVE",
                "taskDefinition": self.current, "desiredCount": 1,
                "runningCount": 1, "pendingCount": 0,
                "deployments": [{"status": "PRIMARY", "taskDefinition": self.current}],
            }]}
        if action == "describe-task-definition":
            return {"taskDefinition": self.definition}
        if action == "register-task-definition":
            self.register_count += 1
            arn = ROLLBACK if self.register_count == 1 else CANDIDATE
            self.registered = copy.deepcopy(payload)
            self.definitions[arn] = copy.deepcopy(payload)
            return {"taskDefinition": {**payload, "taskDefinitionArn": arn}}
        if action == "update-service":
            self.current = args[-1]
            return {}
        if action == "wait":
            if self.current == CANDIDATE and self.wait_failure:
                if self.concurrent:
                    self.current = FOREIGN
                raise deployment.DeploymentError("Mock waiter failed")
            return {}
        if action == "list-tasks":
            return {"taskArns": ["running-task"]}
        if action == "describe-tasks":
            image = self.definitions[self.current]["containerDefinitions"][0]["image"]
            digest = image.split("@", 1)[1] if "@" in image else "sha256:" + "b" * 64
            if self.current == CANDIDATE and self.wrong_digest:
                digest = "sha256:" + "c" * 64
            return {"tasks": [{
                "taskArn": "running-task", "taskDefinitionArn": self.current,
                "lastStatus": "RUNNING", "containers": [{"name": deployment.CONTAINER,
                "image": image, "imageDigest": digest}],
            }]}
        raise AssertionError(args)

    def updates(self):
        return [args[-1] for args, _ in self.calls if args[1] == "update-service"]


class DeployTests(unittest.TestCase):
    def test_preserves_runtime_and_migrates_only_execution_role_and_image(self):
        original = copy.deepcopy(DEFINITION)
        rendered = deployment.render_task_definition(original, IMAGE)
        expected = copy.deepcopy({key: value for key, value in DEFINITION.items() if key in deployment.TASK_FIELDS})
        expected["executionRoleArn"] = deployment.EXECUTION_ROLE
        expected["containerDefinitions"][0]["image"] = IMAGE
        expected["containerDefinitions"][0]["logConfiguration"]["options"]["awslogs-create-group"] = "false"
        self.assertEqual(rendered, expected)
        self.assertEqual(original, DEFINITION)

    def test_rejects_foreign_or_floating_image_and_role_drift(self):
        for image in [deployment.REPOSITORY + ":latest", "other@sha256:" + "a" * 64]:
            with self.assertRaises(deployment.DeploymentError):
                deployment.render_task_definition(DEFINITION, image)
        cases = [("family", "other"), ("cpu", "512"), ("memory", "1024"),
                 ("executionRoleArn", "foreign-role"), ("taskRoleArn", "application-role"),
                 ("unknownApiField", True), ("runtimePlatform", {"cpuArchitecture": "X86_64"})]
        for key, value in cases:
            definition = copy.deepcopy(DEFINITION)
            definition[key] = value
            with self.subTest(key=key), self.assertRaises(deployment.DeploymentError):
                deployment.render_task_definition(definition, IMAGE)

    def test_rejects_foreign_log_destination(self):
        for key, value in [("awslogs-group", "foreign"), ("awslogs-region", "other"), ("awslogs-create-group", "unexpected")]:
            definition = copy.deepcopy(DEFINITION)
            definition["containerDefinitions"][0]["logConfiguration"]["options"][key] = value
            with self.subTest(key=key), self.assertRaises(deployment.DeploymentError):
                deployment.render_task_definition(definition, IMAGE)

    def test_missing_log_group_rejects_before_mutation(self):
        aws = FakeAws()
        original_call = aws.call
        def missing(*args, **kwargs):
            if args[1] == "describe-log-groups":
                return {"logGroups": []}
            return original_call(*args, **kwargs)
        aws.call = missing
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, execute=True)
        self.assertFalse(aws.updates())
        self.assertIsNone(aws.registered)

    def test_plan_does_not_mutate(self):
        aws = FakeAws()
        result = deployment.deploy(aws, IMAGE)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(aws.updates())
        self.assertIsNone(aws.registered)

    def test_success_verifies_image_and_sanitizes_receipt(self):
        aws = FakeAws()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            result = deployment.deploy(aws, IMAGE, execute=True, receipt=path,
                                       http_check=lambda: {"health": 200, "unauthenticatedMcp": 401})
            self.assertEqual(result["status"], "verified")
            self.assertEqual(aws.updates(), [CANDIDATE])
            self.assertNotIn("sensitive-test-sentinel", path.read_text())
            self.assertNotIn("containerDefinitions", path.read_text())

    def test_wait_failure_rolls_back(self):
        aws = FakeAws(wait_failure=True)
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, execute=True)
        self.assertEqual(aws.updates(), [CANDIDATE, ROLLBACK])

    def test_wrong_running_digest_rolls_back(self):
        aws = FakeAws(wrong_digest=True)
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, execute=True)
        self.assertEqual(aws.updates(), [CANDIDATE, ROLLBACK])

    def test_public_probe_failure_rolls_back(self):
        aws = FakeAws()
        def failed_http():
            raise deployment.DeploymentError("HTTP probe failed")
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, execute=True, http_check=failed_http)
        self.assertEqual(aws.updates(), [CANDIDATE, ROLLBACK])

    def test_foreign_deployment_is_never_overwritten_by_rollback(self):
        aws = FakeAws(wait_failure=True, concurrent=True)
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, execute=True)
        self.assertEqual(aws.updates(), [CANDIDATE])
        self.assertEqual(aws.current, FOREIGN)

    def test_task_payload_is_0600_and_removed_without_secret_in_argv(self):
        captured_paths = []
        def fake_run(command, **kwargs):
            self.assertNotIn("sensitive-test-sentinel", " ".join(command))
            path = Path(command[-1].removeprefix("file://"))
            captured_paths.append(path)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertIn("sensitive-test-sentinel", path.read_text())
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        with patch("deploy_ecs.subprocess.run", side_effect=fake_run):
            deployment.Aws().call("ecs", "register-task-definition", payload=DEFINITION)
        self.assertTrue(all(not path.exists() for path in captured_paths))


if __name__ == "__main__":
    unittest.main()
