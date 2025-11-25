-- Snowflake Task to run weekly report generation
-- This task will execute the Python script every Monday at 8 AM

USE SCHEMA CUSTOMER_SUCCESS_DATA.ANALYTICS;

-- Create a stored procedure that runs the Python report generator
CREATE OR REPLACE PROCEDURE generate_weekly_reports()
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-connector-python', 'requests')
HANDLER = 'run_report_generation'
EXECUTE AS CALLER
AS
$$
import os
import json
import requests
from datetime import datetime, timedelta
import snowflake.connector

def run_report_generation(session):
    """
    Generate weekly reports for all CSMs using Cortex Agent.
    This is a simplified version that runs within Snowflake.
    """
    
    # Get connection info from session
    conn = session._conn._conn
    
    # Get account URL
    cursor = conn.cursor()
    cursor.execute("SELECT CURRENT_ACCOUNT_URL()")
    account_url = cursor.fetchone()[0]
    if not account_url.startswith('http'):
        account_url = f"https://{account_url}"
    
    token = conn.rest.token
    
    # Calculate report period
    week_end = datetime.now()
    week_start = week_end - timedelta(days=7)
    
    # Get CSM assignments
    cursor.execute("""
        SELECT csm_id, csm_name, assigned_customer_ids
        FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.csm_assignments
    """)
    
    csm_rows = cursor.fetchall()
    report_count = 0
    errors = []
    
    for csm_id, csm_name, customer_ids_json in csm_rows:
        customer_ids = json.loads(customer_ids_json)
        
        for customer_id in customer_ids:
            if customer_id and customer_id != 'undefined':
                try:
                    # Create thread
                    thread_response = requests.post(
                        f"{account_url}/api/v2/cortex/threads",
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f'Snowflake Token="{token}"'
                        },
                        json={"origin_application": "weekly_report_task"}
                    )
                    thread_response.raise_for_status()
                    thread_id = thread_response.json()['thread_id']
                    
                    # Generate performance section
                    perf_prompt = f"""
                    Analyze performance vs benchmarks for customer {customer_id} 
                    for {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}.
                    Include key metrics and comparisons. Be concise.
                    """
                    
                    perf_response = requests.post(
                        f"{account_url}/api/v2/databases/SNOWFLAKE_INTELLIGENCE/schemas/AGENTS/agents/EXECUTIVE_REVIEW_ASSISTANT:run",
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f'Snowflake Token="{token}"'
                        },
                        json={
                            "thread_id": thread_id,
                            "parent_message_id": "0",
                            "messages": [{
                                "role": "user",
                                "content": [{"type": "text", "text": perf_prompt}]
                            }]
                        }
                    )
                    perf_response.raise_for_status()
                    
                    # Extract text
                    perf_text = ""
                    for item in perf_response.json()['message']['content']:
                        if item.get('type') == 'text':
                            perf_text += item.get('text', '')
                    
                    parent_msg_id = perf_response.json().get('message_id', '1')
                    
                    # Generate business value section
                    value_prompt = f"""
                    Provide business value analysis for customer {customer_id}.
                    Focus on revenue trends, engagement health, and channel effectiveness.
                    """
                    
                    value_response = requests.post(
                        f"{account_url}/api/v2/databases/SNOWFLAKE_INTELLIGENCE/schemas/AGENTS/agents/EXECUTIVE_REVIEW_ASSISTANT:run",
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f'Snowflake Token="{token}"'
                        },
                        json={
                            "thread_id": thread_id,
                            "parent_message_id": parent_msg_id,
                            "messages": [{
                                "role": "user",
                                "content": [{"type": "text", "text": value_prompt}]
                            }]
                        }
                    )
                    value_response.raise_for_status()
                    
                    value_text = ""
                    for item in value_response.json()['message']['content']:
                        if item.get('type') == 'text':
                            value_text += item.get('text', '')
                    
                    parent_msg_id = value_response.json().get('message_id', '2')
                    
                    # Generate recommendations section
                    rec_prompt = f"""
                    Provide 3-5 actionable recommendations for customer {customer_id}
                    based on data and relevant case studies. Include supporting examples.
                    """
                    
                    rec_response = requests.post(
                        f"{account_url}/api/v2/databases/SNOWFLAKE_INTELLIGENCE/schemas/AGENTS/agents/EXECUTIVE_REVIEW_ASSISTANT:run",
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f'Snowflake Token="{token}"'
                        },
                        json={
                            "thread_id": thread_id,
                            "parent_message_id": parent_msg_id,
                            "messages": [{
                                "role": "user",
                                "content": [{"type": "text", "text": rec_prompt}]
                            }]
                        }
                    )
                    rec_response.raise_for_status()
                    
                    rec_text = ""
                    for item in rec_response.json()['message']['content']:
                        if item.get('type') == 'text':
                            rec_text += item.get('text', '')
                    
                    # Format full report
                    full_report = f"""
WEEKLY EXECUTIVE REVIEW REPORT
Customer: {customer_id} | CSM: {csm_name}
Period: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}

1. PERFORMANCE VS BENCHMARKS
{perf_text}

2. BUSINESS VALUE ANALYSIS
{value_text}

3. RECOMMENDATIONS
{rec_text}
"""
                    
                    # Save to database
                    cursor.execute("""
                        INSERT INTO CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports 
                        (csm_id, customer_id, report_date, report_week_start, report_week_end,
                         performance_section, business_value_section, recommendations_section, full_report)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        csm_id, customer_id, datetime.now().date(),
                        week_start.date(), week_end.date(),
                        perf_text, value_text, rec_text, full_report
                    ))
                    
                    report_count += 1
                    
                except Exception as e:
                    errors.append(f"Error for {customer_id}: {str(e)}")
    
    cursor.close()
    
    result = f"Generated {report_count} reports. "
    if errors:
        result += f"Errors: {'; '.join(errors[:3])}"
    
    return result
$$;

-- Create a task that runs every Monday at 8 AM
CREATE OR REPLACE TASK weekly_report_generation_task
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 0 8 * * MON America/Los_Angeles'
AS
    CALL generate_weekly_reports();

-- To enable the task (commented out by default):
-- ALTER TASK weekly_report_generation_task RESUME;

-- To manually run the task for testing:
-- EXECUTE TASK weekly_report_generation_task;

SELECT 'Task and stored procedure created. Use ALTER TASK...RESUME to enable scheduled execution.' AS status;
