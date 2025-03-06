# Grants Webhooks API

A FastAPI application that fetches data from the Grants.gov API and stores it in a Supabase database.

## Features

- Fetch grant opportunities from the Grants.gov API
- Save grant data to Supabase
- RESTful API endpoints for searching grants
- Support for both GET and POST requests
- Duplicate detection to prevent storing the same grant multiple times
- Keyword tracking to associate grants with search terms
- Automated checking for new grants based on saved keywords
- Statistics on grants found per keyword
- Detailed grant information fetched from the Grants.gov details API
- Automatic generation of grant summaries using Ollama
- Webhook support for processing new organization records and generating summaries
- Organization-grant matching functionality

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and update with your Supabase credentials:
   ```
   cp .env.example .env
   ```
5. Update the `.env` file with your Supabase URL and API key

## Database Setup

Create a table in your Supabase project with the following structure:

```sql
CREATE TABLE grants (
    id TEXT PRIMARY KEY,
    number TEXT,
    title TEXT,
    agency_code TEXT,
    agency TEXT,
    open_date TEXT,
    close_date TEXT,
    status TEXT,
    doc_type TEXT,
    cfda_list TEXT[],
    raw_data JSONB,
    search_params JSONB,
    search_keyword TEXT,
    description TEXT,
    category_explanation TEXT,
    award_ceiling TEXT,
    award_floor TEXT,
    expected_awards TEXT,
    funding_instrument_type TEXT,
    eligibility_categories TEXT[],
    cost_sharing TEXT,
    additional_information JSONB,
    agency_contacts JSONB,
    details_raw_data JSONB,
    applicant_eligibility_desc TEXT,
    funding_activity_categories TEXT[],
    opportunity_category TEXT,
    response_date TEXT,
    posting_date TEXT,
    estimated_funding TEXT,
    synopsis_desc TEXT,
    synopsis_summary JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add an index on search_keyword for faster searches
CREATE INDEX idx_grants_search_keyword ON grants(search_keyword);
```

### Grants Table Column Descriptions

| Column | Description |
|--------|-------------|
| id | Primary key - unique identifier for the grant |
| number | Grant opportunity number |
| title | Title of the grant opportunity |
| agency_code | Code of the agency offering the grant |
| agency | Name of the agency offering the grant |
| open_date | Date when the grant opportunity opens |
| close_date | Date when the grant opportunity closes |
| status | Current status of the grant opportunity |
| doc_type | Document type |
| cfda_list | List of CFDA (Catalog of Federal Domestic Assistance) numbers |
| raw_data | Raw JSON data from the search API |
| search_params | Parameters used to search for this grant |
| search_keyword | Keyword used to find this grant |
| description | Detailed description of the grant opportunity |
| category_explanation | Explanation of the grant category |
| award_ceiling | Maximum award amount |
| award_floor | Minimum award amount |
| expected_awards | Expected number of awards |
| funding_instrument_type | Type of funding instrument (e.g., Grant, Cooperative Agreement) |
| eligibility_categories | Categories of eligible applicants |
| cost_sharing | Cost sharing or matching requirements |
| additional_information | Additional information about the grant |
| agency_contacts | Contact information for the agency |
| details_raw_data | Raw data from the details API response |
| applicant_eligibility_desc | Detailed description of who is eligible to apply for the grant |
| funding_activity_categories | Categories of funding activities |
| opportunity_category | Category of the opportunity (e.g., Discretionary) |
| response_date | Due date for applications |
| posting_date | Date when the opportunity was posted |
| estimated_funding | Total estimated funding available |
| synopsis_desc | Synopsis description of the grant opportunity |
| synopsis_summary | AI-generated summary of the grant in structured format |
| created_at | Timestamp when the record was created |

## Running the Application

You can run the application in two ways:

### Method 1: Using the build script (Recommended)
```bash
# Make the build script executable
chmod +x build.sh

# Run the build script
./build.sh
```

### Method 2: Manual setup
1. Create and activate virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run database migrations:
   ```
   python apply_migrations.py
   ```
4. Start the application:
   ```
   python run.py
   ```

The API will be available at http://localhost:8020

## Prerequisites

Before running the application, make sure you have:

1. Ollama installed and running:
   ```bash
   # Install Ollama
   curl https://ollama.ai/install.sh | sh
   
   # Pull the Mistral model
   ollama pull mistral
   
   # Start the Ollama server
   ollama serve
   ```

2. The background task status table created in your database:
   ```sql
   -- Run the migration
   psql -d your_database -f migrations/add_background_task_status.sql
   ```

## API Endpoints

### Organization Management

#### POST /api/v1/organizations/generate-summary/{organization_id}

Generate a summary for a specific organization using Ollama.

Path Parameters:
- `organization_id`: The ID of the organization to process

Query Parameters:
- `force_regenerate` (optional, default: false): Whether to regenerate the summary even if it exists

Example:
```
POST /api/v1/organizations/generate-summary/123e4567-e89b-12d3-a456-426614174000
```

Response:
```json
{
  "success": true,
  "message": "Successfully generated organization summary",
  "organization_id": "123e4567-e89b-12d3-a456-426614174000",
  "result": {
    "mission": "Brief statement of the organization's mission",
    "expertise": ["Area 1", "Area 2", "Area 3"],
    "funding_interests": ["Interest 1", "Interest 2"],
    "notable_aspects": ["Notable aspect 1", "Notable aspect 2"]
  }
}
```

#### POST /api/v1/organizations/match-with-grants/{organization_id}

Match a specific organization with relevant grants.

Path Parameters:
- `organization_id`: The ID of the organization to process

Query Parameters:
- `force_rematch` (optional, default: false): Whether to rematch even if matches exist

Example:
```
POST /api/v1/organizations/match-with-grants/123e4567-e89b-12d3-a456-426614174000
```

Response:
```json
{
  "success": true,
  "message": "Successfully matched organization with grants",
  "organization_id": "123e4567-e89b-12d3-a456-426614174000",
  "matches_count": 5,
  "result": {
    "success": true,
    "matches": [...]
  }
}
```

#### GET /api/v1/organizations/grant-matches/{organization_id}

Get all grant matches for a specific organization with formatted HTML output.

Path Parameters:
- `organization_id`: The ID of the organization to get matches for

Example:
```
GET /api/v1/organizations/grant-matches/123e4567-e89b-12d3-a456-426614174000
```

Response:
```json
{
  "organization": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "Example Organization",
    "email": "contact@example.org",
    "description": "Organization description"
  },
  "matches": [
    {
      "grant": {
        "id": "grant123",
        "title": "Example Grant",
        "agency": "Example Agency",
        "award_floor": "$10,000",
        "award_ceiling": "$100,000",
        "close_date": "2024-12-31",
        "description": "Grant description",
        "eligibility": "Eligibility criteria",
        "grant_link": "https://www.grants.gov/search-grants.html?keywords=grant123"
      },
      "match_score": 0.85,
      "match_reason": "Strong match based on expertise and funding interests"
    }
  ],
  "html_content": "<div>...</div>",
  "total_matches": 1
}
```

### Grant Management

#### GET /api/v1/grants/search

Query Parameters:
- `keyword` (optional): Keyword to search for
- `date_range` (optional, default: "30"): Date range to search in
- `opp_statuses` (optional, default: "forecasted|posted"): Opportunity statuses
- `rows` (optional, default: 5000): Number of rows to return
- `sort_by` (optional, default: "openDate|desc"): Sort order
- `save_to_supabase` (optional, default: true): Whether to save results to Supabase

Example:
```
GET /api/v1/grants/search?keyword=education&date_range=30
```

Response:
```json
{
  "success": true,
  "message": "Successfully fetched and saved X grants",
  "data": {
    "count": X,
    "total_found": Y
  }
}
```

#### POST /api/v1/grants/search

Request Body:
```json
{
  "keyword": "virus",
  "date_range": "30",
  "opp_statuses": "forecasted|posted",
  "rows": 5000,
  "sort_by": "openDate|desc",
  "save_to_supabase": true
}
```

Response: Same as GET endpoint

### Keyword Management

#### POST /api/v1/keywords/check-new-grants

This endpoint checks for new grants for all keywords stored in the database. It runs as a background task and updates each keyword's execution date after processing. For each new grant found, it also fetches detailed information from the Grants.gov details API.

Query Parameters:
- `date_range` (optional, default: "1"): Number of days to look back for new grants
- `opp_statuses` (optional, default: "forecasted|posted"): Opportunity statuses
- `rows` (optional, default: 5000): Maximum number of results per keyword
- `sort_by` (optional, default: "openDate|desc"): Sort order

Example:
```
POST /api/v1/keywords/check-new-grants
```

Response:
```json
{
  "success": true,
  "message": "Background task started to check for new grants for all keywords",
  "date_range": "1"
}
```

#### GET /api/v1/keywords/stats

This endpoint provides statistics about grants found for each keyword in the database.

Query Parameters:
- `days` (optional, default: 7): Number of days to look back
- `organization_id` (optional): Filter keywords by organization ID

Example:
```
GET /api/v1/keywords/stats?days=30
```

Response:
```json
{
  "success": true,
  "message": "Found X grants for Y keywords in the last Z days",
  "data": {
    "keywords": [
      {
        "keyword_id": "uuid",
        "keyword": "education",
        "grants_count": 42,
        "last_execution": "2023-06-01T12:00:00Z"
      },
      {
        "keyword_id": "uuid",
        "keyword": "research",
        "grants_count": 35,
        "last_execution": "2023-06-01T12:05:00Z"
      }
    ],
    "total_keywords": 2,
    "total_grants": 77,
    "days": 30,
    "start_date": "2023-05-02T00:00:00Z"
  }
}
```

### Environment Variables

The application uses the following environment variables:

- `SECRET_KEY`: Secret key for the application
- `WEBHOOK_SECRET`: Secret for webhooks
- `SUPABASE_URL`: URL of your Supabase project
- `SUPABASE_KEY`: API key for your Supabase project
- `OPENAI_API_KEY`: API key for OpenAI (required for grant summary generation)

## Grant Summaries

The application can generate concise summaries of grant opportunities using OpenAI's GPT model. These summaries provide key information about each grant in a structured format.

### Summary Format

Each grant summary includes:
- `goal`: The main objective of the grant (what it aims to accomplish)
- `duration`: The timeframe for the grant opportunity
- `success_criteria`: Key points that make for a successful application
- `good_to_know`: Important information applicants should be aware of

### Generate Summaries for All Grants

#### POST /api/v1/grants/generate-summaries

This endpoint starts a background task to generate summaries for all grants in the database.

Query Parameters:
- `force_regenerate` (optional, default: false): Whether to regenerate summaries for grants that already have them

Example:
```
POST /api/v1/grants/generate-summaries
```

Response:
```json
{
  "success": true,
  "message": "Background task started successfully",
  "task_id": "71baa24b-33c4-4f5a-9b6c-31606a55f5c5"
}
```

#### GET /api/v1/grants/task-status/{task_id}

Check the status of a background task.

Path Parameters:
- `task_id`: The ID of the task to check

Example:
```
GET /api/v1/grants/task-status/71baa24b-33c4-4f5a-9b6c-31606a55f5c5
```

Response:
```json
{
  "id": "71baa24b-33c4-4f5a-9b6c-31606a55f5c5",
  "task_type": "grant_summary",
  "status": "running",
  "total_items": 100,
  "processed_items": 45,
  "failed_items": 2,
  "current_item_id": "358459",
  "started_at": "2024-03-20T10:00:00Z",
  "last_updated_at": "2024-03-20T10:30:00Z"
}
```

#### GET /api/v1/grants/active-tasks

Get information about all currently running background tasks.

Example:
```
GET /api/v1/grants/active-tasks
```

Response:
```json
{
  "71baa24b-33c4-4f5a-9b6c-31606a55f5c5": {
    "id": "71baa24b-33c4-4f5a-9b6c-31606a55f5c5",
    "task_type": "grant_summary",
    "status": "running",
    "total_items": 100,
    "processed_items": 45,
    "failed_items": 2,
    "current_item_id": "358459",
    "started_at": "2024-03-20T10:00:00Z",
    "last_updated_at": "2024-03-20T10:30:00Z"
  }
}
```

#### POST /api/v1/grants/stop-task/{task_id}

Stop a specific background task.

Path Parameters:
- `task_id`: The ID of the task to stop

Example:
```
POST /api/v1/grants/stop-task/71baa24b-33c4-4f5a-9b6c-31606a55f5c5
```

Response:
```json
{
  "success": true,
  "message": "Task 71baa24b-33c4-4f5a-9b6c-31606a55f5c5 stopped successfully"
}
```
## Documentation

API documentation is available at http://localhost:8000/docs when the application is running.

## How to Run the Grant Summary Generation

Before running the grant summary generation, make sure you have:

1. Ollama installed and running:
   ```bash
   # Install Ollama
   curl https://ollama.ai/install.sh | sh
   
   # Pull the Mistral model
   ollama pull mistral
   
   # Start the Ollama server
   ollama serve
   ```

2. The background task status table created in your database:
   ```sql
   -- Run the migration
   psql -d your_database -f migrations/add_background_task_status.sql
   ```

3. The application running on port 8020:
   ```bash
   ./build.sh
   ```

To start generating summaries:

1. Start the background task:
   ```bash
   curl -X POST "http://localhost:8020/api/v1/grants/generate-summaries"
   ```

2. Monitor the progress using the returned task_id:
   ```bash
   curl "http://localhost:8020/api/v1/grants/task-status/{task_id}"
   ```

3. View all active tasks:
   ```bash
   curl "http://localhost:8020/api/v1/grants/active-tasks"
   ```

4. Stop the task if needed:
   ```bash
   curl -X POST "http://localhost:8020/api/v1/grants/stop-task/{task_id}"
   ```

The system will:
- Process one grant every 2 minutes to avoid rate limiting
- Skip grants that already have summaries (unless force_regenerate is True)
- Update progress in real-time
- Handle errors gracefully
- Allow you to monitor and control the process

## Scheduled Tasks

The application includes a script for running scheduled tasks:

```
python scheduled_tasks.py check_new_grants
```

This script can be set up as a cron job to automatically check for new grants daily:

```
# Run daily at 2 AM
0 2 * * * cd /path/to/project && /path/to/venv/bin/python scheduled_tasks.py check_new_grants
```

## Troubleshooting

If you encounter issues with environment variables not loading correctly:

1. Make sure your `.env` file is in the root directory of the project
2. Verify that the values in the `.env` file are correct
3. Check the application logs for any error messages related to environment variables

## Data Storage

When grants are saved to Supabase:

1. The system checks for duplicates to avoid storing the same grant multiple times
2. Each grant is associated with the search keyword that was used to find it
3. Both the raw data and search parameters are stored for reference
4. For each new grant, detailed information is fetched from the Grants.gov details API
5. The detailed information includes award amounts, eligibility criteria, and contact information

## Webhooks

The API supports webhooks for various events:

### Organization Webhook

When a new organization is added to the Supabase `organizations` table, a webhook is triggered that:

1. Receives the new organization data
2. Generates a summary of the organization using Ollama
3. Updates the organization record with the summary

To set up this webhook in Supabase:

1. Go to your Supabase project dashboard
2. Navigate to Database > Webhooks
3. Create a new webhook with the following settings:
   - Name: `organization_summary_generator`
   - Table: `organizations`
   - Events: `INSERT`
   - HTTP Method: `POST`
   - URL: `https://your-api-url.com/api/v1/webhooks`
   - Headers: Add a header `x-webhook-signature` with a secret value that matches your `WEBHOOK_SECRET` environment variable

The webhook will automatically process new organizations and generate summaries based on the provided information.

