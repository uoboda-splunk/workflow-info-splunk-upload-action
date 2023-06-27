import json
import logging
import os
import sys
import requests

from datetime import datetime

LOGGER = logging.getLogger("reporter")


def get_workflow_data(repository, run_id, gh_token):
    headers = {"Authorization": "token " + gh_token}
    endpoint = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs"
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

    def send_job_report(self, job, user):
        _id = job["id"]
        _run_id = job["run_id"]
        fields = {"user": user}
        fields.update(job)
        steps = []
        for step in job["steps"]:
            steps.append(step["name"])
        fields["steps"] = steps
        format = "%Y-%m-%dT%H:%M:%SZ"
        start = datetime.strptime(job["started_at"], format)
        end = datetime.strptime(job["completed_at"], format)
        fields["duration_in_seconds"] = (end - start).total_seconds()
        event = {
            "index": self.index,
            "event": f"Job {job['name']} finished with {job['conclusion']} conclusion. Started at {job['started_at']}."
            f" Trigerred by {user}",
            "source": "github-workflows",
            "sourcetype": "github:workflow:action",
            "host": job["runner_name"],
            "fields": fields,
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
    data = get_workflow_data(repository, run_id, github_token)
    for job in data["jobs"]:
        if job["conclusion"] is not None:
            spl_reporter.send_job_report(job, user)
