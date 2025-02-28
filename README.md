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
| created_at | Timestamp when the record was created |

## Running the Application

```
python run.py
```

The API will be available at http://localhost:8000

## API Endpoints

### Search Grants

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

## Documentation

API documentation is available at http://localhost:8000/docs when the application is running.

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
