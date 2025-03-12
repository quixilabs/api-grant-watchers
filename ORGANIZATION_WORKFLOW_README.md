# Organization Grant Processing Workflow

This workflow processes a specific organization through the entire grant matching pipeline, from extracting keywords to creating an email campaign.

## Overview

The workflow performs the following steps:

1. **Get Organization Data**: Retrieves the organization's information by name or ID
2. **Extract Organization Keywords**: Extracts keywords from the organization's grant interests
3. **Find Grants by Keywords**: Finds grants that match the organization's keywords within the specified date range
4. **Generate Grant Summaries**: Generates summaries for matching grants that don't have summaries
5. **Match Organization with Grants**: Matches the organization with grants using DeepSeek AI
6. **Create Email Campaign**: Creates an email campaign with the matching grants

## Requirements

- Python 3.9+
- Prefect 3.0+
- Access to the Grant Watchers API

## Installation

1. Ensure Prefect is installed:
   ```
   pip install -U prefect
   ```

2. Start the Prefect server (if not already running):
   ```
   prefect server start
   ```

3. Deploy the workflow:
   ```
   python prefect_deployment.py
   ```

## Usage

### Running the Workflow from the Command Line

You can run the workflow directly from the command line:

```bash
python organization_workflow.py "Organization Name" 30
```

Or with an organization ID:

```bash
python organization_workflow.py "7c5057e4-04e7-4566-8100-6ebe406e49ad" 30
```

The second parameter (30) is the date range in days to look back for grants. It's optional and defaults to 30 days.

### Running the Workflow via Prefect

To run the workflow via Prefect:

```bash
prefect deployment run organization-grant-processing-pipeline/organization-grant-processing --param organization_name_or_id="Organization Name" --param date_range=30
```

Or with an organization ID:

```bash
prefect deployment run organization-grant-processing-pipeline/organization-grant-processing --param organization_name_or_id="7c5057e4-04e7-4566-8100-6ebe406e49ad" --param date_range=30
```

The `date_range` parameter is optional and defaults to 30 days.

### Scheduling the Workflow

You can schedule the workflow to run at specific intervals using the Prefect UI or CLI:

```bash
prefect deployment set-schedule organization-grant-processing-pipeline/organization-grant-processing --cron "0 9 * * 1" --timezone "America/New_York"
```

This example schedules the workflow to run every Monday at 9 AM Eastern Time.

## Workflow Details

### 1. Get Organization Data

The workflow first attempts to find the organization by ID. If that fails, it searches for the organization by name (case-insensitive).

**API Calls:**
```python
# Try to get by ID
GET /api/v1/organizations/{organization_id}

# If not found by ID, get all organizations and filter by name
GET /api/v1/organizations
```

### 2. Extract Organization Keywords

Keywords are extracted from the organization's `grant_interests` field. This field can be either a comma-separated string or a list of keywords.

**Processing:**
```python
# If grant_interests is a list
org_keywords = [keyword.strip().lower() for keyword in org_interests]

# If grant_interests is a string
org_keywords = [keyword.strip().lower() for keyword in org_interests.split(',') if keyword.strip()]
```

### 3. Find Grants by Keywords

The workflow searches for grants that contain any of the organization's keywords in their title, description, or search keywords. It only considers grants published within the specified date range (default: 30 days).

**API Calls:**
```python

# Search Grants by Keywords
GET /api/v1/grants/search?keyword={keyword}&date_range={date_range}&opp_statuses=forecasted|posted&rows=5000&sort_by=openDate|desc
```

### 4. Generate Grant Summaries

For any matching grants that don't have summaries, the workflow generates summaries using the API.

**API Calls:**
```python
# For each grant without a summary
POST /api/v1/grants/generate-summary/{grant_id}

# Get the updated grant with summary
# Uses Supabase client directly since there's no specific endpoint
client.table("grants").select("*").eq("id", grant_id).execute()
```

### 5. Match Organization with Grants

The workflow matches the organization with the filtered grants using DeepSeek AI. This process evaluates how well each grant matches the organization's profile and interests.

**API Calls:**
```python
# Start the matching process
POST /api/v1/organizations/match-with-grants/{organization_id}?force_rematch=true&run_in_background=true

# Check task status until completed
GET /api/v1/organizations/task-status/{task_id}

# Get the matches
GET /api/v1/organizations/grant-matches/{organization_id}
```

### 6. Create Email Campaign

Finally, the workflow creates an email campaign containing the matching grants, which can be sent to the organization's contacts.

**API Calls:**
```python
# Send email with matches
POST /api/v1/email/send-grant-matches
# Request body:
# {
#   "organization_id": "{organization_id}",
#   "matches": [...]
# }
```

## Troubleshooting

- **No Organization Found**: Ensure the organization name or ID is correct.
- **No Keywords Found**: Make sure the organization has keywords in the `grant_interests` field.
- **No Matching Grants**: If no grants match the organization's keywords, try adding more general keywords to the organization's profile or increasing the date range.
- **API Connection Issues**: Check that the API is running and accessible.

## Environment Variables

- `API_BASE_URL`: The base URL for the API (default: `http://localhost:8020/api/v1`)
- `PREFECT_API_URL`: The URL for the Prefect API (default: `http://127.0.0.1:4200/api`)

## Logs

Logs are available in the Prefect UI and can be used to track the progress of the workflow and diagnose any issues. 