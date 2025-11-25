# Weekly Executive Report Generator

Automated system for generating weekly executive business review reports for customer success managers using Snowflake Cortex Agent.

## Overview

This system generates comprehensive weekly reports for each CSM's assigned customers by:
1. Analyzing structured data (conversions, engagement, benchmarks) via Cortex Analyst
2. Searching relevant case studies and best practices via Cortex Search
3. Generating multi-section reports with performance analysis, business value, and recommendations
4. Storing reports in Snowflake for historical tracking

## Architecture

### Components

1. **CSM Assignment Table** (`csm_assignments`)
   - Maps customer success managers to their assigned customer IDs
   - Stores CSM contact information and region

2. **Report Storage Table** (`weekly_reports`)
   - Stores generated reports with full text and individual sections
   - Tracks generation timestamps and metadata

3. **Cortex Agent** (`executive_review_assistant`)
   - Orchestrates across Cortex Analyst (structured data) and Cortex Search (case studies)
   - Generates insights combining quantitative metrics and qualitative examples

4. **Python Script** (`weekly_report_generator.py`)
   - Standalone script for generating reports
   - Can run for all CSMs or a single customer
   - Uses Cortex Agent REST API

5. **Snowflake Task** (Optional)
   - Scheduled stored procedure that runs weekly
   - Automatically generates reports for all CSMs

## Setup

### Prerequisites

```bash
# Install required Python packages
pip install snowflake-connector-python requests
```

### Database Objects

All database objects are created in the `MY_DEMO` connection:

```
CUSTOMER_SUCCESS_DATA
├── ANALYTICS (schema)
│   ├── conversions (structured data)
│   ├── attributions (structured data)
│   ├── industry_benchmarks (structured data)
│   ├── historical_engagement (structured data)
│   ├── case_studies (unstructured data)
│   ├── csm_assignments (CSM to customer mapping)
│   ├── weekly_reports (generated reports)
│   └── case_study_search (Cortex Search service)
└── SEMANTIC_MODELS (schema)
    └── MODEL_STAGE (stage containing YAML)

SNOWFLAKE_INTELLIGENCE
└── AGENTS (schema)
    └── executive_review_assistant (Cortex Agent)
```

## Usage

### Option 1: Python Script (Recommended for Testing)

#### Generate report for a single customer:

```bash
export SNOWFLAKE_CONNECTION_NAME=MY_DEMO

python weekly_report_generator.py \
  --mode single \
  --csm-id CSM001 \
  --customer-id CUST_12345
```

#### Generate reports for all CSMs:

```bash
export SNOWFLAKE_CONNECTION_NAME=MY_DEMO

python weekly_report_generator.py --mode all
```

### Option 2: Snowflake Task (Production)

#### Setup the task:

```sql
-- Run the setup script
source setup_weekly_task.sql

-- Enable the task (runs every Monday at 8 AM Pacific)
ALTER TASK weekly_report_generation_task RESUME;
```

#### Manual execution for testing:

```sql
-- Execute immediately
EXECUTE TASK weekly_report_generation_task;

-- Check results
SELECT * FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports
ORDER BY generation_timestamp DESC
LIMIT 5;
```

#### Monitor task execution:

```sql
-- Check task history
SELECT *
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
WHERE NAME = 'WEEKLY_REPORT_GENERATION_TASK'
ORDER BY SCHEDULED_TIME DESC
LIMIT 10;
```

## Report Structure

Each generated report contains three main sections:

### 1. Performance vs Benchmarks
- Key conversion metrics (revenue, count, average value)
- Engagement metrics (open rates, CTR, engagement scores)
- Comparison to industry benchmarks
- Year-over-year trends

### 2. Business Value Analysis
- Revenue trends and growth indicators
- Customer engagement health assessment
- Channel effectiveness analysis
- Attribution insights

### 3. Recommendations & Best Practices
- 3-5 actionable recommendations
- Supporting data and case study examples
- Expected impact for each recommendation
- Focus on optimization and churn prevention

## Sample CSM Assignments

```
CSM001 - Sarah Johnson (North America)
  ├── CUST_12345
  ├── CUST_23456
  └── CUST_34567

CSM002 - Michael Chen (Asia Pacific)
  ├── CUST_45678
  └── CUST_56789

CSM003 - Emma Rodriguez (Europe)
  ├── CUST_67890
  └── CUST_78901

CSM004 - James Williams (Latin America)
  ├── CUST_89012
  └── CUST_90123
```

## Viewing Reports

### Query reports in SQL:

```sql
-- Get latest report for a specific customer
SELECT 
    csm_id,
    customer_id,
    report_week_start,
    report_week_end,
    full_report,
    generation_timestamp
FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports
WHERE customer_id = 'CUST_12345'
ORDER BY generation_timestamp DESC
LIMIT 1;

-- Get all reports for a CSM
SELECT 
    customer_id,
    report_week_start,
    LENGTH(full_report) as report_length_chars,
    generation_timestamp
FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports
WHERE csm_id = 'CSM001'
ORDER BY generation_timestamp DESC;

-- Weekly report generation summary
SELECT 
    DATE_TRUNC('week', generation_timestamp) as week,
    COUNT(*) as reports_generated,
    COUNT(DISTINCT csm_id) as csms_served,
    COUNT(DISTINCT customer_id) as customers_analyzed
FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports
GROUP BY 1
ORDER BY 1 DESC;
```

## How It Works

### Report Generation Flow

1. **Thread Creation**: Creates a new conversation thread for context maintenance
2. **Section Generation**: Sequentially generates each report section:
   - Calls agent with section-specific prompt
   - Agent queries structured data (Cortex Analyst) and case studies (Cortex Search)
   - Extracts and stores response text
   - Uses previous message_id to maintain conversation context
3. **Report Assembly**: Combines all sections into formatted report
4. **Storage**: Saves individual sections and full report to database

### API Calls per Report

- 1x Thread creation (`POST /api/v2/cortex/threads`)
- 3x Agent calls (`POST /api/v2/databases/.../agents/...:run`)
  - Performance analysis
  - Business value analysis
  - Recommendations

### Conversation Context

The system maintains conversation context across sections by:
- Using a single thread_id for all sections
- Passing parent_message_id from previous response to next request
- Allowing the agent to reference earlier analysis in later sections

## Customization

### Modify Report Sections

Edit the `sections` dictionary in `weekly_report_generator.py`:

```python
sections = {
    'performance': """Your custom prompt...""",
    'business_value': """Your custom prompt...""",
    'recommendations': """Your custom prompt..."""
}
```

### Add New Sections

Add entries to the `sections` dictionary and update database schema:

```sql
ALTER TABLE weekly_reports 
ADD COLUMN new_section TEXT;
```

### Change Schedule

Modify the CRON expression in `setup_weekly_task.sql`:

```sql
-- Every Monday at 8 AM
SCHEDULE = 'USING CRON 0 8 * * MON America/Los_Angeles'

-- Every Friday at 5 PM
SCHEDULE = 'USING CRON 0 17 * * FRI America/Los_Angeles'
```

## Troubleshooting

### Agent API Errors

```python
# Check agent exists
SHOW AGENTS IN SCHEMA SNOWFLAKE_INTELLIGENCE.AGENTS;

# Verify permissions
SHOW GRANTS ON AGENT SNOWFLAKE_INTELLIGENCE.AGENTS.EXECUTIVE_REVIEW_ASSISTANT;
```

### Task Not Running

```sql
-- Check task status
SHOW TASKS LIKE 'weekly_report_generation_task';

-- Resume suspended task
ALTER TASK weekly_report_generation_task RESUME;

-- Check warehouse is running
SHOW WAREHOUSES LIKE 'COMPUTE_WH';
```

### Empty Reports

- Ensure customer_id exists in source data tables
- Check date range has data (reports look at last 7 days)
- Verify agent tools are properly configured

## Performance Considerations

- **Rate Limits**: Cortex Agent API has rate limits; consider staggering report generation
- **Warehouse Size**: Use appropriate warehouse size for task execution
- **Timeout**: Agent queries have 120s timeout; complex analyses may need adjustment
- **Cost**: Each agent call consumes Cortex credits; monitor usage

## Files

- `weekly_report_generator.py` - Main Python script for report generation
- `setup_weekly_task.sql` - SQL script to create task and stored procedure
- `executive_review_semantic_model.yaml` - Semantic model for Cortex Analyst

## Support

For issues or questions:
1. Check agent configuration in Snowflake Intelligence UI
2. Review task execution history for error messages
3. Test with single customer first before running for all CSMs
4. Verify all source tables have recent data
