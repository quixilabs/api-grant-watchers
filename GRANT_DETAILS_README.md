# Grant Details and Summaries Workflow

This workflow processes all grants in the database to ensure they have complete details and AI-generated summaries.

## Overview

The `grant_details_workflow.py` script provides a Prefect workflow that:

1. Fetches all grants from the database in batches
2. Identifies grants missing details
3. Retrieves missing details from the Grants.gov API
4. Identifies grants missing summaries
5. Generates AI-powered summaries for grants that need them

## Requirements

- Prefect 3.0 or newer
- Python 3.8 or newer
- Access to the Grant Watchers API
- Environment variables properly configured

## Configuration

Set the following environment variables:

```
API_BASE_URL=http://localhost:8020/api/v1  # Your API base URL
PREFECT_API_URL=http://127.0.0.1:4200/api  # Your Prefect API URL
```

## Running the Workflow

### Command-line Arguments

The workflow accepts several command-line arguments for customization:

- `--batch-size`: Number of grants to fetch in each batch (default: 100)
- `--max-batches`: Maximum number of batches to process (for testing/debugging)
- `--details-batch-size`: Number of grants to process in each batch for details (default: 10)
- `--details-delay`: Delay between API calls for details in seconds (default: 5)
- `--summaries-batch-size`: Number of grants to process in each batch for summaries (default: 5)
- `--summaries-delay`: Delay between API calls for summaries in seconds (default: 15)
- `--skip-details`: Skip processing grant details
- `--skip-summaries`: Skip processing grant summaries
- `--max-details`: Maximum number of grants to process for details
- `--max-summaries`: Maximum number of grants to process for summaries

### Running Directly

To run the workflow directly:

```bash
python grant_details_workflow.py
```

With custom parameters:

```bash
python grant_details_workflow.py --batch-size 50 --details-batch-size 5 --summaries-batch-size 2 --summaries-delay 180
```

To process only details:

```bash
python grant_details_workflow.py --skip-summaries
```

To process only summaries:

```bash
python grant_details_workflow.py --skip-details
```

For testing with limited grants:

```bash
python grant_details_workflow.py --max-details 10 --max-summaries 5
```

### Running as a Prefect Deployment

After creating the deployment with the `prefect_deployment.py` script, you can run it:

```bash
prefect deployment run grant-details-summaries-pipeline/grant-details-summaries
```

With parameters:

```bash
prefect deployment run grant-details-summaries-pipeline/grant-details-summaries --param batch_size=50 --param process_details=true --param process_summaries=true --param max_details_grants=10
```

## How It Works

### Fetching Grants

The workflow fetches grants in batches to avoid memory issues with large databases. It makes paginated calls to the API endpoint to retrieve all grants.

### Processing Details

For grants without details, the workflow calls the Grants.gov API (via your backend) to retrieve and store detailed information. This includes the full grant description, eligibility requirements, and other metadata.

### Processing Summaries

For grants without summaries, the workflow uses your AI-powered summarization service to generate concise, informative summaries. This helps organizations quickly understand the grant's purpose without reading the entire description.

### Batch Processing and Rate Limiting

The workflow implements batch processing and rate limiting to:

1. Avoid overwhelming your API
2. Manage rate limits from external services
3. Handle large datasets efficiently
4. Allow for error recovery at the batch level

## Recommended Usage

This workflow is designed to be run periodically (e.g., weekly) to ensure all grants have complete information. Running it as a scheduled Prefect deployment makes this process automatic.

For very large grant databases, consider:

1. Running details and summaries processes separately
2. Using larger delays between API calls
3. Setting maximum limits for testing before full runs

## Monitoring

The workflow provides detailed logging throughout the process. You can monitor progress through the Prefect UI or logs. 