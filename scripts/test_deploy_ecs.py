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
    "executionRoleArn": deployment.EXECUTION_ROLE,
    "runtimePlatform": {"cpuArchitecture": "ARM64", "operatingSystemFamily": "LINUX"},
    "requiresCompatibilities": ["FARGATE"], "volumes": [],
    "containerDefinitions": [{
        "name": deployment.CONTAINER, "image": deployment.REPOSITORY + "@sha256:" + "b" * 64,
        "portMappings": [{"containerPort": 80, "hostPort": 80, "protocol": "tcp"}],
        "environment": [{"name": "PORT", "value": "80"}],
        "secrets": [
            {"name": key, "valueFrom": f"arn:aws:secretsmanager:{deployment.REGION}:{deployment.ACCOUNT}:secret:tiangong-ai/mcp/runtime-AbCd12:{key}::"}
            for key in ["UPSTASH_REDIS_URL", "UPSTASH_REDIS_TOKEN"]
        ],
        "logConfiguration": {"logDriver": "awslogs", "options": {"awslogs-group": deployment.LOG_GROUP, "awslogs-region": deployment.REGION}},
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
                "deployments": [{"id": "deployment-" + self.current, "status": "PRIMARY", "rolloutState": "COMPLETED", "taskDefinition": self.current}],
                "deploymentConfiguration": {"minimumHealthyPercent": 100, "maximumPercent": 200,
                    "deploymentCircuitBreaker": {"enable": True, "rollback": True}},
            }]}
        if action == "describe-task-definition":
            return {"taskDefinition": self.definition}
        if action == "register-task-definition":
            self.register_count += 1
            arn = ROLLBACK if self.register_count == 1 else CANDIDATE
            self.registered = copy.deepcopy(payload)
            self.definitions[arn] = copy.deepcopy(payload)
            return {"taskDefinition": {key: value for key, value in {**payload, "taskDefinitionArn": arn}.items() if key != "tags"},
                    "tags": payload["tags"]}
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
    def setUp(self):
        guard = patch("deploy_ecs.verify_current_source")
        guard.start()
        self.addCleanup(guard.stop)

    def test_preserves_approved_runtime_settings_except_image(self):
        original = copy.deepcopy(DEFINITION)
        rendered = deployment.render_task_definition(original, IMAGE)
        expected = copy.deepcopy({key: value for key, value in DEFINITION.items() if key in deployment.TASK_FIELDS})
        expected["executionRoleArn"] = deployment.EXECUTION_ROLE
        expected["containerDefinitions"][0]["image"] = IMAGE
        self.assertEqual(rendered, expected)
        self.assertEqual(original, DEFINITION)

    def test_rejects_foreign_or_floating_image_and_role_drift(self):
        for image in [deployment.REPOSITORY + ":latest", "other@sha256:" + "a" * 64]:
            with self.assertRaises(deployment.DeploymentError):
                deployment.render_task_definition(DEFINITION, image)
        cases = [("family", "other"), ("cpu", "512"), ("memory", "1024"),
                 ("executionRoleArn", "foreign-role"), ("executionRoleArn", deployment.LEGACY_EXECUTION_ROLE), ("taskRoleArn", "application-role"),
                 ("unknownApiField", True), ("runtimePlatform", {"cpuArchitecture": "X86_64"})]
        for key, value in cases:
            definition = copy.deepcopy(DEFINITION)
            definition[key] = value
            with self.subTest(key=key), self.assertRaises(deployment.DeploymentError):
                deployment.render_task_definition(definition, IMAGE)

    def test_disabled_log_group_creation_must_be_omitted(self):
        definition = copy.deepcopy(DEFINITION)
        options = definition["containerDefinitions"][0]["logConfiguration"]["options"]
        options.pop("awslogs-create-group", None)
        rendered = deployment.render_task_definition(definition, IMAGE)
        self.assertNotIn("awslogs-create-group", rendered["containerDefinitions"][0]["logConfiguration"]["options"])
        for value in ["false", "true"]:
            options["awslogs-create-group"] = value
            with self.subTest(value=value), self.assertRaises(deployment.DeploymentError):
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
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=lambda: {})
        self.assertFalse(aws.updates())
        self.assertIsNone(aws.registered)

    def test_rejects_plaintext_or_foreign_runtime_secret(self):
        for mutation in ["plaintext", "foreign", "missing"]:
            definition = copy.deepcopy(DEFINITION)
            container = definition["containerDefinitions"][0]
            if mutation == "plaintext":
                container["environment"].append({"name": "UPSTASH_REDIS_TOKEN", "value": "forbidden"})
            elif mutation == "foreign":
                container["secrets"][0]["valueFrom"] = "foreign-secret"
            else:
                container["secrets"].pop()
            with self.subTest(mutation=mutation), self.assertRaises(deployment.DeploymentError):
                deployment.render_task_definition(definition, IMAGE)

    def test_uncontrolled_prior_revision_is_rejected_before_mutation(self):
        aws = FakeAws()
        aws.current = FOREIGN
        original_call = aws.call
        def missing_tags(*args, **kwargs):
            if args[1] == "list-tags-for-resource":
                return {"tags": []}
            return original_call(*args, **kwargs)
        aws.call = missing_tags
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=lambda: {})
        self.assertFalse(aws.updates())
        self.assertIsNone(aws.registered)

    def test_controlled_prior_revision_has_required_lineage_tags(self):
        aws = FakeAws()
        aws.current = CANDIDATE
        original_call = aws.call
        def controlled(*args, **kwargs):
            if args[1] == "list-tags-for-resource":
                return {"tags": [
                    {"key": "Application", "value": "tiangong-ai-mcp"},
                    {"key": "Repository", "value": "tiangong-ai/mcp-server"},
                    {"key": "DeploymentKind", "value": "candidate"},
                    {"key": "DeploymentCommit", "value": "c" * 40},
                ]}
            return original_call(*args, **kwargs)
        aws.call = controlled
        self.assertEqual(deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40)["status"], "planned")

    def test_reviewed_template_contains_only_qualified_runtime_refs(self):
        definition = json.loads((Path(__file__).resolve().parent.parent / "deployment/task-definition.json").read_text())
        rendered = deployment.render_task_definition(definition, IMAGE)
        self.assertEqual(rendered["containerDefinitions"][0]["environment"], [{"name": "PORT", "value": "80"}])
        self.assertEqual(rendered["containerDefinitions"][0]["image"], IMAGE)

    def test_bootstrap_image_drift_is_rejected_before_registration(self):
        aws = FakeAws()
        definition = copy.deepcopy(DEFINITION)
        definition["containerDefinitions"][0]["image"] = deployment.REPOSITORY + "@sha256:" + "c" * 64
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, definition, "d" * 40, execute=True)
        self.assertIsNone(aws.registered)
        self.assertFalse(aws.updates())

    def test_rollback_failure_records_recovery_state(self):
        aws = FakeAws(wait_failure=True)
        original_call = aws.call
        def fail_rollback(*args, **kwargs):
            if args[1] == "wait" and aws.current == ROLLBACK and CANDIDATE in aws.updates():
                raise deployment.DeploymentError("Rollback waiter failed")
            return original_call(*args, **kwargs)
        aws.call = fail_rollback
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaises(deployment.DeploymentError):
                deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, receipt=path, http_check=lambda: {})
            self.assertEqual(json.loads(path.read_text())["status"], "rollback-verification-failed")

    def test_bootstrap_migration_failure_stops_before_candidate(self):
        aws = FakeAws()
        original_call = aws.call
        def failed_baseline(*args, **kwargs):
            if args[1] == "wait" and aws.current == ROLLBACK:
                raise deployment.DeploymentError("Migration waiter failed")
            return original_call(*args, **kwargs)
        aws.call = failed_baseline
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaises(deployment.DeploymentError):
                deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, receipt=path, http_check=lambda: {})
            self.assertEqual(aws.updates(), [ROLLBACK])
            self.assertEqual(json.loads(path.read_text())["status"], "bootstrap-migration-not-qualified")

    def test_bootstrap_breaker_return_to_legacy_is_failure_not_success(self):
        aws = FakeAws()
        original_call = aws.call
        def reverted_baseline(*args, **kwargs):
            if args[1] == "wait" and aws.current == ROLLBACK:
                aws.current = PREVIOUS
                raise deployment.DeploymentError("Migration reverted")
            return original_call(*args, **kwargs)
        aws.call = reverted_baseline
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaises(deployment.DeploymentError):
                deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, receipt=path, http_check=lambda: {})
            self.assertEqual(aws.updates(), [ROLLBACK])
            self.assertEqual(json.loads(path.read_text())["status"], "bootstrap-migration-failed-legacy-retained")

    def test_candidate_breaker_return_to_qualified_baseline_is_failure(self):
        aws = FakeAws()
        original_call = aws.call
        def reverted_candidate(*args, **kwargs):
            if args[1] == "wait" and aws.current == CANDIDATE:
                aws.current = ROLLBACK
                raise deployment.DeploymentError("Candidate reverted")
            return original_call(*args, **kwargs)
        aws.call = reverted_candidate
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaises(deployment.DeploymentError):
                deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, receipt=path, http_check=lambda: {})
            self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE])
            self.assertEqual(json.loads(path.read_text())["status"], "qualified-baseline-retained")

    def test_in_progress_rollout_is_not_qualified_by_counts(self):
        aws = FakeAws()
        original_call = aws.call
        def incomplete(*args, **kwargs):
            response = original_call(*args, **kwargs)
            if args[1] == "describe-services":
                response["services"][0]["deployments"][0]["rolloutState"] = "IN_PROGRESS"
            return response
        aws.call = incomplete
        with self.assertRaises(deployment.DeploymentError):
            deployment.verify_running(aws, PREVIOUS)

    def test_services_stable_can_precede_completed_bootstrap_candidate_and_rollback(self):
        for candidate_failure in [False, True]:
            with self.subTest(candidate_failure=candidate_failure):
                aws = FakeAws(wait_failure=candidate_failure)
                original_call = aws.call
                transient = False
                def completing(*args, **kwargs):
                    nonlocal transient
                    response = original_call(*args, **kwargs)
                    if args[1] == "wait":
                        transient = True
                    elif args[1] == "describe-services" and transient:
                        transient = False
                        response["services"][0]["deployments"][0]["rolloutState"] = "IN_PROGRESS"
                    return response
                aws.call = completing
                probes = []
                def http():
                    probes.append(aws.current)
                    return {"health": 200, "unauthenticatedMcp": 401}
                with patch("deploy_ecs.time.sleep") as sleep:
                    if candidate_failure:
                        with self.assertRaisesRegex(deployment.DeploymentError, "Mock waiter failed"):
                            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=http)
                        self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE, ROLLBACK])
                        self.assertEqual(probes, [ROLLBACK])
                    else:
                        result = deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=http)
                        self.assertEqual(result["status"], "verified")
                        self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE])
                        self.assertEqual(probes, [ROLLBACK, CANDIDATE])
                    self.assertEqual(sleep.call_count, 2)

    def test_completed_rollout_wait_times_out_without_qualifying_tasks(self):
        aws = FakeAws()
        original_call = aws.call
        def incomplete(*args, **kwargs):
            response = original_call(*args, **kwargs)
            if args[1] == "describe-services":
                response["services"][0]["deployments"][0]["rolloutState"] = "IN_PROGRESS"
            return response
        aws.call = incomplete
        with patch("deploy_ecs.time.monotonic", side_effect=[0, 0, 5, 10]), patch("deploy_ecs.time.sleep") as sleep:
            with self.assertRaisesRegex(deployment.DeploymentError, "Timed out"):
                deployment.wait_for_completed_rollout(aws, PREVIOUS, timeout=10, poll_interval=5)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(len(aws.calls), 3)
        self.assertTrue(all(args[1] == "describe-services" for args, _ in aws.calls))

    def test_completed_rollout_wait_rejects_failed_unknown_and_drift_without_retry(self):
        for mutation in ["FAILED", "unknown", "definition", "deployment-definition", "primary", "configuration", "counts", "multiple"]:
            with self.subTest(mutation=mutation):
                aws = FakeAws()
                original_call = aws.call
                def changed(*args, **kwargs):
                    response = original_call(*args, **kwargs)
                    service = response["services"][0]
                    current = service["deployments"][0]
                    current["rolloutState"] = "IN_PROGRESS"
                    if mutation in {"FAILED", "unknown"}:
                        current["rolloutState"] = mutation
                    elif mutation == "definition":
                        service["taskDefinition"] = FOREIGN
                    elif mutation == "deployment-definition":
                        current["taskDefinition"] = FOREIGN
                    elif mutation == "primary":
                        current["status"] = "ACTIVE"
                    elif mutation == "configuration":
                        service["deploymentConfiguration"]["minimumHealthyPercent"] = 0
                    elif mutation == "counts":
                        service["pendingCount"] = 1
                    else:
                        service["deployments"].append(copy.deepcopy(current))
                    return response
                aws.call = changed
                with patch("deploy_ecs.time.sleep") as sleep:
                    with self.assertRaises(deployment.DeploymentError):
                        deployment.wait_for_completed_rollout(aws, PREVIOUS)
                sleep.assert_not_called()
                self.assertEqual(len(aws.calls), 1)

    def test_completed_rollout_wait_rejects_same_definition_new_deployment(self):
        aws = FakeAws()
        original_call = aws.call
        reads = 0
        def replaced(*args, **kwargs):
            nonlocal reads
            response = original_call(*args, **kwargs)
            reads += 1
            current = response["services"][0]["deployments"][0]
            if reads == 1:
                current["rolloutState"] = "IN_PROGRESS"
            else:
                current["id"] = "replacement-deployment"
            return response
        aws.call = replaced
        with patch("deploy_ecs.time.sleep") as sleep:
            with self.assertRaisesRegex(deployment.DeploymentError, "Deployment changed"):
                deployment.wait_for_completed_rollout(aws, PREVIOUS)
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(len(aws.calls), 2)

    def test_same_revision_rollout_guard_drift_blocks_updates(self):
        aws = FakeAws()
        original_call = aws.call
        reads = 0
        def changed_guards(*args, **kwargs):
            nonlocal reads
            response = original_call(*args, **kwargs)
            if args[1] == "describe-services":
                reads += 1
                if reads >= 3:
                    response["services"][0]["deploymentConfiguration"]["minimumHealthyPercent"] = 0
            return response
        aws.call = changed_guards
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=lambda: {})
        self.assertFalse(aws.updates())

    def test_stale_source_stops_before_any_aws_operation(self):
        aws = FakeAws()
        def stale(_revision):
            raise deployment.StaleSourceError("Stale source")
        with self.assertRaises(deployment.StaleSourceError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, source_check=stale)
        self.assertFalse(aws.calls)

    def test_source_advance_during_bootstrap_keeps_qualified_baseline(self):
        aws = FakeAws()
        calls = 0
        def changes(_revision):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise deployment.StaleSourceError("Main advanced")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            with self.assertRaises(deployment.StaleSourceError):
                deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True,
                    source_check=changes, receipt=path, http_check=lambda: {})
            result = json.loads(path.read_text())
            self.assertEqual(aws.updates(), [ROLLBACK])
            self.assertTrue(result["staleSource"])
            self.assertEqual(result["status"], "qualified-baseline-retained")

    def test_plan_does_not_mutate(self):
        aws = FakeAws()
        result = deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(aws.updates())
        self.assertIsNone(aws.registered)

    def test_success_verifies_image_and_sanitizes_receipt(self):
        aws = FakeAws()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            result = deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, receipt=path,
                                       http_check=lambda: {"health": 200, "unauthenticatedMcp": 401})
            self.assertEqual(result["status"], "verified")
            self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE])
            self.assertFalse(any(args[1] == "describe-task-definition" for args, _ in aws.calls))
            registrations = [payload for args, payload in aws.calls if args[1] == "register-task-definition"]
            self.assertEqual(len(registrations), 2)
            for payload, kind in zip(registrations, ["rollback", "candidate"]):
                self.assertEqual({tag["key"]: tag["value"] for tag in payload["tags"]}, {
                    "Application": "tiangong-ai-mcp", "Repository": "tiangong-ai/mcp-server",
                    "DeploymentCommit": "d" * 40, "DeploymentKind": kind,
                })
                self.assertEqual(payload["executionRoleArn"], deployment.EXECUTION_ROLE)
            self.assertNotIn("sensitive-test-sentinel", path.read_text())
            self.assertNotIn("containerDefinitions", path.read_text())

    def test_wait_failure_rolls_back(self):
        aws = FakeAws(wait_failure=True)
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=lambda: {})
        self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE, ROLLBACK])

    def test_wrong_running_digest_rolls_back(self):
        aws = FakeAws(wrong_digest=True)
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=lambda: {})
        self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE, ROLLBACK])

    def test_public_probe_failure_rolls_back(self):
        aws = FakeAws()
        def failed_http():
            if aws.current == CANDIDATE:
                raise deployment.DeploymentError("HTTP probe failed")
            return {"health": 200, "unauthenticatedMcp": 401}
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=failed_http)
        self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE, ROLLBACK])

    def test_foreign_deployment_is_never_overwritten_by_rollback(self):
        aws = FakeAws(wait_failure=True, concurrent=True)
        with self.assertRaises(deployment.DeploymentError):
            deployment.deploy(aws, IMAGE, DEFINITION, "d" * 40, execute=True, http_check=lambda: {})
        self.assertEqual(aws.updates(), [ROLLBACK, CANDIDATE])
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
            payload = copy.deepcopy(DEFINITION)
            payload["containerDefinitions"][0]["environment"] = [{"name": "TEST_PRIVATE", "value": "sensitive-test-sentinel"}]
            deployment.Aws().call("ecs", "register-task-definition", payload=payload)
        self.assertTrue(all(not path.exists() for path in captured_paths))


if __name__ == "__main__":
    unittest.main()
