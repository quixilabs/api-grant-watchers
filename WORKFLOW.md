# API Workflows

This document outlines the workflows and algorithms for each endpoint in the Grant Watchers API.

## 1. Grant Management Endpoints

### 1.1 Check New Grants for Keywords (`POST /api/v1/keywords/check-new-grants`)

```mermaid
graph TD
    A[Start] --> B[Get date range from query params]
    B --> C[Get all tracked keywords]
    C --> D[For each keyword]
    D --> E[Search Grants.gov API]
    E --> F[Filter new grants]
    F --> G{New grants found?}
    G -->|Yes| H[Save grant details]
    H --> I[Update keyword stats]
    G -->|No| J[Skip to next keyword]
    J --> D
    I --> D
    D -->|Done| K[Return results]
    K --> L[End]
```

**Algorithm:**
1. Receive date range parameter (default: 5 days)
2. Retrieve all tracked keywords from database
3. For each keyword:
   - Search Grants.gov API for matching grants
   - Filter out already saved grants
   - Save new grant details to database
   - Update keyword statistics
4. Return summary of processed grants

### 1.2 Generate Grant Summaries (`POST /api/v1/grants/generate-summaries`)

```mermaid
graph TD
    A[Start] --> B[Get batch size & force flag]
    B --> C[Get grants without summaries]
    C --> D[For each grant]
    D --> E{Has existing summary?}
    E -->|Yes| F{Force regenerate?}
    F -->|Yes| G[Generate new summary]
    F -->|No| H[Skip grant]
    E -->|No| G
    G --> I[Save summary to database]
    I --> D
    H --> D
    D -->|Done| J[Return results]
    J --> K[End]
```

**Algorithm:**
1. Accept batch size and force_regenerate parameters
2. Retrieve grants without summaries (or all if force_regenerate)
3. For each grant:
   - Check if summary exists
   - If no summary or force_regenerate:
     - Generate summary using OpenAI
     - Save to database
4. Return processing results

### 1.3 Generate Single Grant Summary (`POST /api/v1/grants/generate-summary/{grant_id}`)

```mermaid
graph TD
    A[Start] --> B[Get grant ID & force flag]
    B --> C[Fetch grant details]
    C --> D{Grant exists?}
    D -->|No| E[Return 404]
    D -->|Yes| F{Has summary?}
    F -->|Yes| G{Force regenerate?}
    G -->|No| H[Return existing]
    G -->|Yes| I[Generate new summary]
    F -->|No| I
    I --> J[Save to database]
    J --> K[Return summary]
    H --> K
    K --> L[End]
```

**Algorithm:**
1. Accept grant_id and force_regenerate parameters
2. Fetch grant details from database
3. If grant exists:
   - Check for existing summary
   - Generate new summary if none exists or force_regenerate is true
   - Save and return summary
4. Return 404 if grant not found

## 2. Organization Management Endpoints

### 2.1 Organization Webhook Handler (`POST /api/v1/webhooks`)

```mermaid
graph TD
    A[Start] --> B[Verify webhook signature]
    B --> C{Valid signature?}
    C -->|No| D[Return 401]
    C -->|Yes| E[Parse webhook payload]
    E --> F{Is organization insert?}
    F -->|No| G[Return success]
    F -->|Yes| H[Extract organization data]
    H --> I[Generate summary using GPT]
    I --> J[Save summary to database]
    J --> K[Return result]
    K --> L[End]
```

**Algorithm:**
1. Verify incoming webhook signature
2. Parse webhook payload
3. If event is organization insert:
   - Extract organization details
   - Generate summary using OpenAI GPT
   - Save summary to organization record
4. Return processing result

## 3. Keyword Management Endpoints

### 3.1 Track New Keyword (`POST /api/v1/keywords/track`)

```mermaid
graph TD
    A[Start] --> B[Validate keyword]
    B --> C{Keyword exists?}
    C -->|Yes| D[Return existing]
    C -->|No| E[Search initial grants]
    E --> F[Save keyword]
    F --> G[Save found grants]
    G --> H[Update stats]
    H --> I[Return results]
    I --> J[End]
```

**Algorithm:**
1. Validate keyword input
2. Check if keyword already tracked
3. If new keyword:
   - Search Grants.gov for initial matches
   - Save keyword to database
   - Save found grants
   - Update keyword statistics
4. Return tracking results

### 3.2 Get Keyword Statistics (`GET /api/v1/keywords/stats`)

```mermaid
graph TD
    A[Start] --> B[Get all keywords]
    B --> C[For each keyword]
    C --> D[Calculate statistics]
    D --> E[Aggregate results]
    E --> F[Return stats]
    F --> G[End]
```

**Algorithm:**
1. Retrieve all tracked keywords
2. For each keyword:
   - Calculate total grants found
   - Calculate grants per time period
   - Gather success/failure rates
3. Return aggregated statistics

## 4. Database Migrations

### 4.1 Apply Migrations (`apply_migrations.py`)

```mermaid
graph TD
    A[Start] --> B[Load environment variables]
    B --> C[Connect to Supabase]
    C --> D[Get migration files]
    D --> E[For each migration]
    E --> F[Read SQL content]
    F --> G[Execute migration]
    G --> H{Success?}
    H -->|Yes| I[Log success]
    H -->|No| J[Log error]
    I --> E
    J --> E
    E -->|Done| K[End]
```

**Algorithm:**
1. Load environment configuration
2. Establish Supabase connection
3. Get list of migration files
4. For each migration:
   - Read SQL content
   - Execute migration
   - Log results
5. Return migration status

## Notes

- All endpoints include error handling and logging
- Database operations are wrapped in try-catch blocks
- Webhook signatures are verified for security
- Rate limiting is applied where appropriate
- Pagination is implemented for large result sets
