# Grants Webhooks API

A FastAPI application that fetches data from the Grants.gov API and stores it in a Supabase database.

## Features

- Fetch grant opportunities from the Grants.gov API
- Save grant data to Supabase
- RESTful API endpoints for searching grants
- Support for both GET and POST requests

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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

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

Example:
```
GET /api/v1/grants/search?keyword=education&date_range=30
```

#### POST /api/v1/grants/search

Request Body:
```json
{
  "keyword": "virus",
  "date_range": "30",
  "opp_statuses": "forecasted|posted",
  "rows": 5000,
  "sort_by": "openDate|desc"
}
```

## Documentation

API documentation is available at http://localhost:8000/docs when the application is running.
