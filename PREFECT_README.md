# Grant Processing Pipeline with Prefect

This project contains a Prefect workflow that orchestrates the grant processing pipeline, automating the following steps:

1. Finding new grants
2. Adding summaries to new grants
3. Adding summaries to new organizations
4. Matching organizations with grants
5. Creating email campaigns for new grant matches

## Prerequisites

- Python 3.8+
- Prefect 3.0+
- Running instance of the Grant Webhooks API

## Installation

1. Install Prefect with all dependencies (this prevents common installation issues):

```bash
pip install "prefect[all]"
```

If you encounter any dependency errors like missing `griffe` package, run:

```bash
pip install "griffe>=0.25.0"
```

2. Install additional required packages:

```bash
pip install httpx
```

3. Set up the environment variables:

```bash
export API_BASE_URL="http://localhost:8020/api/v1"  # Update with your API URL
```

## Running the Workflow

### Local Execution

To run the workflow locally:

```bash
python prefect_workflows.py
```

### Setting Up Prefect

1. Start the Prefect server (if not already running):

```bash
prefect server start
```

2. Create a work pool (if it doesn't exist):

```bash
prefect work-pool create default --type process
```

3. In a new terminal, create the deployments:

```bash
python prefect_deployment.py
```

This will create two deployments:
- `daily-grant-processing`: For processing grants from the last day
- `weekly-grant-processing`: For processing grants from the last week

4. Start a Prefect worker to execute the flows:

```bash
prefect worker start --pool default
```

5. Run a deployment manually:

```bash
prefect deployment run grant-processing-pipeline/daily-grant-processing
```

or

```bash
prefect deployment run grant-processing-pipeline/weekly-grant-processing
```

> **Note**: The deployment script will automatically connect to your running Prefect server (default: http://127.0.0.1:4200/api). If your server is running at a different URL, set the `PREFECT_API_URL` environment variable before running the script:
> 
> ```bash
> export PREFECT_API_URL="http://your-server-url:4200/api"
> python prefect_deployment.py
> ```
>
> When starting a worker or running deployments, you'll also need to set the same environment variable:
>
> ```bash
> export PREFECT_API_URL="http://your-server-url:4200/api"
> prefect worker start --pool default
> prefect deployment run grant-processing-pipeline/daily-grant-processing
> ```

## Monitoring

You can monitor your workflows through the Prefect UI:

1. Open your browser and navigate to `http://localhost:4200`
2. View flows, deployments, and flow runs
3. Check logs and task statuses

## Troubleshooting

### Installation Issues

If you encounter dependency errors:

1. Install Prefect with all dependencies: `pip install "prefect[all]"`
2. If specific packages are missing, install them directly: `pip install griffe`
3. Make sure you're using a compatible Python version (3.8-3.11)

### API Connection Issues

If the workflow fails to connect to the API:

1. Verify the API is running: `curl http://localhost:8020/api/v1/health`
2. Check the `API_BASE_URL` environment variable
3. Ensure network connectivity between the Prefect worker and the API

### Task Failures

If specific tasks are failing:

1. Check the logs in the Prefect UI
2. Increase the `retries` parameter for problematic tasks
3. Adjust the `retry_delay_seconds` for tasks that might need more time

## Advanced Configuration

### Changing the Retry Policy

You can modify the retry behavior for API calls by changing:

```python
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
```

### Adjusting Task Wait Times

For long-running background tasks, you can adjust the maximum wait time:

```python
task_result = await wait_for_task_completion(task_id, max_wait_time=7200)  # Wait up to 2 hours
```

## Adding New Tasks

To add a new task to the workflow:

1. Create a new task function with the `@task` decorator
2. Add appropriate error handling and logging
3. Integrate the task into the main flow in `grant_processing_pipeline()` 