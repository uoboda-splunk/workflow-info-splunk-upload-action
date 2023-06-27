# workflow-info-splunk-upload-action
GitHub action to send information to Splunk about previous jobs in workflow. It should be the last one job in workflow to have data about all previous jobs. Using this action you can track job statuses, timestamps etc.

## Inputs
|  Input Parameter   | Required | Description                                                             |
|:------------------:|:--------:|-------------------------------------------------------------------------|
|     repository     |   true   | GitHub repository name to gather data from                              |
|       run_id       |   true   | Workflow run id to fetch data from                                      |
|        user        |   true   | User which triggered workflow                                           |
|    splunk_host     |   true   | Splunk host address                                                     |
|    splunk_token    |   true   | Splunk HEC token                                                        |
|       index        |  false   | Splunk index in which data will be stored                               |
|    splunk_port     |  false   | Splunk HEC port                                                         |
| splunk_hec_scheme  |  false   | protocol which will be used while sending data through HEC - http/https |

## Example usage:

```yaml
# jobs section in GH actions  workflow file 
  report_workflow:
    runs-on: ubuntu-latest
    needs: last_previous_job
    steps:
      - uses: uoboda-splunk/workflow-info-splunk-upload-action@v1
        with:
          repository: ${{ github.repository }}
          run_id: ${{ github.run_id }}
          user: ${{ github.actor }}
          splunk_host: ${{ secrets.SPLUNK_HOST }}
          splunk_token: ${{ secrets.SPLUNK_TOKEN }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
