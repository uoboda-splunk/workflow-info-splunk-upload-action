import json
import logging
import os
import sys
import requests

from datetime import datetime

LOGGER = logging.getLogger("reporter")


def get_github_data(repository, run_id, gh_token, endpoint):
    headers = {"Authorization": "token " + gh_token}
    endpoint = endpoint.format(repository=repository, run_id=run_id)
    response = requests.get(endpoint, headers=headers)
    return response.json()


class SplunkReporter:
    def __init__(
        self,
        host,
        splunk_token,
        index,
        port,
        hec_scheme,
    ):
        self.host = host
        self.port = port
        self.hec_scheme = hec_scheme
        self.token = splunk_token
        self.index = index

    def send_job_report(self, job, user, report):
        fields = {"user": user}
        fields.update(job)
        steps = []
        for step in job["steps"]:
            steps.append(step["name"])
        fields["steps"] = steps
        _format = "%Y-%m-%dT%H:%M:%SZ"
        start = datetime.strptime(job["started_at"], _format)
        end = datetime.strptime(job["completed_at"], _format)
        fields["duration_in_seconds"] = (end - start).total_seconds()
        report["jobs"].append(job["name"])
        report["duration_in_seconds"] += fields["duration_in_seconds"]
        event = {
            "index": self.index,
            "event": f"Job {job['name']} finished with {job['conclusion']} conclusion. Started at {job['started_at']}."
            f" Trigerred by {user}",
            "source": "github-workflows",
            "sourcetype": "github:workflow:job",
            "host": job["runner_name"],
            "fields": fields,
        }
        self.send_and_log_event(event)

    def send_artifacts_report(self, artifact, user, report):
        fields = {"user": user, "run_id": artifact["workflow_run"]["id"]}
        fields.update(artifact)
        fields.pop("workflow_run")
        report["artifacts"].append(artifact["name"])
        event = {
            "index": self.index,
            "event": f"Artifact {fields['name']} uploaded for workflow {fields['run_id']}"
            f" Trigerred by {user}",
            "source": "github-workflows",
            "sourcetype": "github:workflow:artifact",
            "host": job["runner_name"],
            "fields": fields,
        }
        self.send_and_log_event(event)

    def send_workflow_report(self, report, user, run_id):
        event = {
            "index": self.index,
            "event": f"Workflow run with ID {run_id} finished with jobs {', '.join(report['jobs'])} and artifacts {', '.join(report['artifacts'])}"
            f" Trigerred by {user}",
            "source": "github-workflows",
            "sourcetype": "github:workflow",
            "host": job["runner_name"],
            "fields": report,
        }
        self.send_and_log_event(event)

    def send_and_log_event(self, event):
        result = self._send_event_to_splunk(event)
        if result and result.status_code in (200, 201):
            LOGGER.info("event ingested successfully")
        elif result:
            LOGGER.warning(
                f"event ingestion failed - HTTP error {result.status_code}: {result.text}"
            )
        return result

    def _send_event_to_splunk(self, event):
        LOGGER.info(f"Sending event to Splunk: {event}")
        try:
            return requests.post(
                f"{self.hec_scheme}://{self.host}:{self.port}/services/collector",
                headers={"Authorization": f"Splunk {self.token}"},
                data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                verify=False,
            )
        except requests.exceptions.ConnectionError as e:
            LOGGER.warning(f"Exception error caught during ingestion: {e}")


if __name__ == "__main__":
    github_token = os.getenv("GITHUB_TOKEN")

    (
        _,
        repository,
        run_id,
        user,
        splunk_host,
        splunk_token,
        index,
        splunk_port,
        hec_scheme,
    ) = sys.argv
    spl_reporter = SplunkReporter(
        splunk_host, splunk_token, index, splunk_port, hec_scheme
    )
    workflow_endpoint = (
        "https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs"
    )
    data = get_github_data(repository, run_id, github_token, workflow_endpoint)
    worfklow_report = {"jobs": [], "artifacts": [], "duration_in_seconds": 0}
    for job in data["jobs"]:
        if job["conclusion"] is not None:
            spl_reporter.send_job_report(job, user, worfklow_report)
    artifact_endpoint = (
        "https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts"
    )
    artifact_data = get_github_data(repository, run_id, github_token, artifact_endpoint)
    for artifact in artifact_data["artifacts"]:
        spl_reporter.send_artifacts_report(artifact, user, worfklow_report)
    worfklow_report["run_id"] = run_id
    spl_reporter.send_workflow_report(worfklow_report, user, run_id)
