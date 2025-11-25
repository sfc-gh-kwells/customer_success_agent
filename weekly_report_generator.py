"""
Weekly Executive Report Generator using Cortex Agent

This script generates weekly executive review reports for customer success managers
by calling the Cortex Agent API to analyze customer data and create structured reports.
"""

import os
import json
import requests
from datetime import datetime, timedelta
import snowflake.connector
from typing import Dict, List, Optional


class WeeklyReportGenerator:
    """Generates weekly executive reports using Cortex Agent."""
    
    def __init__(self, connection_name: str = "MY_DEMO"):
        """Initialize the report generator with Snowflake connection."""
        self.conn = snowflake.connector.connect(
            connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or connection_name
        )
        self.account_url = self._get_account_url()
        self.token = self.conn.rest.token
        
    def _get_account_url(self) -> str:
        """Get the Snowflake account URL for API calls."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT CURRENT_ACCOUNT_URL()")
        account_url = cursor.fetchone()[0]
        cursor.close()
        
        # Format: https://account.region.snowflakecomputing.com
        if not account_url.startswith('http'):
            account_url = f"https://{account_url}"
        return account_url
    
    def create_thread(self, origin_app: str = "weekly_report_generator") -> str:
        """Create a new thread for agent conversation."""
        url = f"{self.account_url}/api/v2/cortex/threads"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Snowflake Token="{self.token}"'
        }
        payload = {
            "origin_application": origin_app
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return response.json()['thread_id']
    
    def call_agent(
        self, 
        thread_id: str, 
        parent_message_id: str,
        user_message: str,
        database: str = "SNOWFLAKE_INTELLIGENCE",
        schema: str = "AGENTS",
        agent_name: str = "EXECUTIVE_REVIEW_ASSISTANT"
    ) -> Dict:
        """Call the Cortex Agent with a user message."""
        url = f"{self.account_url}/api/v2/databases/{database}/schemas/{schema}/agents/{agent_name}:run"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Snowflake Token="{self.token}"'
        }
        payload = {
            "thread_id": thread_id,
            "parent_message_id": parent_message_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_message
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def extract_text_from_response(self, response: Dict) -> str:
        """Extract text content from agent response."""
        text_parts = []
        
        if 'message' in response and 'content' in response['message']:
            for content_item in response['message']['content']:
                if content_item.get('type') == 'text':
                    text_parts.append(content_item.get('text', ''))
        
        return '\n\n'.join(text_parts)
    
    def generate_report_for_customer(
        self, 
        customer_id: str,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, str]:
        """Generate a multi-section report for a specific customer."""
        
        # Create a thread for this report generation
        thread_id = self.create_thread()
        print(f"Created thread: {thread_id}")
        
        # Define report sections and their prompts
        sections = {
            'performance': f"""
            Analyze performance vs industry benchmarks for customer {customer_id} 
            for the period {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}.
            
            Include:
            1. Key conversion metrics (total revenue, conversion count, average value)
            2. Engagement metrics (open rates, click-through rates, engagement scores)
            3. Comparison to industry benchmarks where available
            4. Year-over-year comparison if sufficient historical data exists
            
            Keep it concise and highlight the most important metrics.
            """,
            
            'business_value': f"""
            Provide a business value analysis for customer {customer_id}.
            
            Focus on:
            1. Revenue trends and growth indicators
            2. Customer engagement health
            3. Channel effectiveness (which channels are driving the most value)
            4. Attribution insights (which touchpoints contribute most to conversions)
            
            Translate metrics into business impact statements.
            """,
            
            'recommendations': f"""
            Based on the data for customer {customer_id} and relevant case studies from 
            the Media & Entertainment industry, provide 3-5 actionable recommendations.
            
            For each recommendation:
            1. State the recommendation clearly
            2. Reference supporting data or case study examples
            3. Explain the expected impact
            
            Focus on: channel optimization, engagement strategies, and churn prevention.
            """
        }
        
        report_sections = {}
        parent_message_id = "0"
        
        # Generate each section
        for section_name, prompt in sections.items():
            print(f"Generating {section_name} section...")
            
            response = self.call_agent(
                thread_id=thread_id,
                parent_message_id=parent_message_id,
                user_message=prompt
            )
            
            # Extract text from response
            section_text = self.extract_text_from_response(response)
            report_sections[section_name] = section_text
            
            # Update parent_message_id for next call (maintains context)
            parent_message_id = response.get('message_id', parent_message_id)
            
            print(f"  ✓ {section_name} section generated ({len(section_text)} chars)")
        
        return report_sections
    
    def format_full_report(
        self, 
        customer_id: str,
        csm_name: str,
        week_start: datetime,
        week_end: datetime,
        sections: Dict[str, str]
    ) -> str:
        """Format all sections into a complete report."""
        
        report = f"""
================================================================================
WEEKLY EXECUTIVE REVIEW REPORT
================================================================================

Customer ID: {customer_id}
CSM: {csm_name}
Report Period: {week_start.strftime('%B %d, %Y')} - {week_end.strftime('%B %d, %Y')}
Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}

================================================================================
1. PERFORMANCE VS BENCHMARKS
================================================================================

{sections['performance']}

================================================================================
2. BUSINESS VALUE ANALYSIS
================================================================================

{sections['business_value']}

================================================================================
3. RECOMMENDATIONS & BEST PRACTICES
================================================================================

{sections['recommendations']}

================================================================================
END OF REPORT
================================================================================
"""
        return report
    
    def save_report_to_database(
        self,
        csm_id: str,
        customer_id: str,
        week_start: datetime,
        week_end: datetime,
        sections: Dict[str, str],
        full_report: str
    ) -> int:
        """Save the generated report to the database."""
        
        cursor = self.conn.cursor()
        
        insert_sql = """
        INSERT INTO CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports 
        (csm_id, customer_id, report_date, report_week_start, report_week_end, 
         performance_section, business_value_section, recommendations_section, full_report)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_sql, (
            csm_id,
            customer_id,
            datetime.now().date(),
            week_start.date(),
            week_end.date(),
            sections['performance'],
            sections['business_value'],
            sections['recommendations'],
            full_report
        ))
        
        # Get the generated report_id
        cursor.execute("SELECT LAST_QUERY_ID()")
        
        cursor.close()
        self.conn.commit()
        
        return cursor.rowcount
    
    def get_csm_assignments(self) -> List[Dict]:
        """Get all CSM assignments from the database."""
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT csm_id, csm_name, csm_email, assigned_customer_ids, region
            FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.csm_assignments
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        
        csm_list = []
        for row in rows:
            csm_list.append({
                'csm_id': row[0],
                'csm_name': row[1],
                'csm_email': row[2],
                'customer_ids': json.loads(row[3]),  # Parse JSON array
                'region': row[4]
            })
        
        return csm_list
    
    def generate_weekly_reports(self):
        """Generate reports for all CSMs and their assigned customers."""
        
        # Calculate report period (last 7 days)
        week_end = datetime.now()
        week_start = week_end - timedelta(days=7)
        
        print(f"\n{'='*80}")
        print(f"WEEKLY REPORT GENERATION")
        print(f"Period: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}")
        print(f"{'='*80}\n")
        
        # Get all CSM assignments
        csms = self.get_csm_assignments()
        
        report_count = 0
        
        for csm in csms:
            print(f"\nProcessing CSM: {csm['csm_name']} ({csm['csm_id']})")
            print(f"Region: {csm['region']}")
            print(f"Assigned Customers: {len(csm['customer_ids'])}")
            
            for customer_id in csm['customer_ids']:
                if customer_id and customer_id != 'undefined':
                    print(f"\n  Generating report for customer: {customer_id}")
                    
                    try:
                        # Generate report sections
                        sections = self.generate_report_for_customer(
                            customer_id=customer_id,
                            week_start=week_start,
                            week_end=week_end
                        )
                        
                        # Format full report
                        full_report = self.format_full_report(
                            customer_id=customer_id,
                            csm_name=csm['csm_name'],
                            week_start=week_start,
                            week_end=week_end,
                            sections=sections
                        )
                        
                        # Save to database
                        self.save_report_to_database(
                            csm_id=csm['csm_id'],
                            customer_id=customer_id,
                            week_start=week_start,
                            week_end=week_end,
                            sections=sections,
                            full_report=full_report
                        )
                        
                        print(f"  ✓ Report saved to database")
                        report_count += 1
                        
                    except Exception as e:
                        print(f"  ✗ Error generating report for {customer_id}: {str(e)}")
        
        print(f"\n{'='*80}")
        print(f"COMPLETED: Generated {report_count} reports")
        print(f"{'='*80}\n")
    
    def generate_single_report(self, csm_id: str, customer_id: str) -> str:
        """Generate a single report for testing purposes."""
        
        week_end = datetime.now()
        week_start = week_end - timedelta(days=7)
        
        # Get CSM info
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT csm_name FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.csm_assignments WHERE csm_id = %s",
            (csm_id,)
        )
        result = cursor.fetchone()
        cursor.close()
        
        if not result:
            raise ValueError(f"CSM {csm_id} not found")
        
        csm_name = result[0]
        
        print(f"Generating report for {customer_id} (CSM: {csm_name})...")
        
        # Generate sections
        sections = self.generate_report_for_customer(
            customer_id=customer_id,
            week_start=week_start,
            week_end=week_end
        )
        
        # Format full report
        full_report = self.format_full_report(
            customer_id=customer_id,
            csm_name=csm_name,
            week_start=week_start,
            week_end=week_end,
            sections=sections
        )
        
        # Save to database
        self.save_report_to_database(
            csm_id=csm_id,
            customer_id=customer_id,
            week_start=week_start,
            week_end=week_end,
            sections=sections,
            full_report=full_report
        )
        
        return full_report
    
    def close(self):
        """Close the Snowflake connection."""
        self.conn.close()


def main():
    """Main entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate weekly executive reports')
    parser.add_argument('--mode', choices=['all', 'single'], default='all',
                       help='Generate reports for all CSMs or a single customer')
    parser.add_argument('--csm-id', help='CSM ID (required for single mode)')
    parser.add_argument('--customer-id', help='Customer ID (required for single mode)')
    parser.add_argument('--pdf', action='store_true',
                       help='Generate PDF report with charts (requires matplotlib and reportlab)')
    parser.add_argument('--pdf-output', default='executive_report.pdf',
                       help='Output path for PDF report')
    
    args = parser.parse_args()
    
    generator = WeeklyReportGenerator()
    
    try:
        if args.mode == 'single':
            if not args.csm_id or not args.customer_id:
                parser.error("--csm-id and --customer-id are required for single mode")
            
            report = generator.generate_single_report(args.csm_id, args.customer_id)
            print("\n" + "="*80)
            print("GENERATED REPORT:")
            print("="*80)
            print(report)
            
            # Generate PDF if requested
            if args.pdf:
                try:
                    from cortex_code_workbook.customer_success_use_case.pdf_report_generator import PDFReportGenerator
                    
                    # Get CSM info
                    cursor = generator.conn.cursor()
                    cursor.execute(
                        "SELECT csm_name FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.csm_assignments WHERE csm_id = %s",
                        (args.csm_id,)
                    )
                    result = cursor.fetchone()
                    cursor.close()
                    
                    if result:
                        csm_name = result[0]
                        
                        # Get report sections from database
                        cursor = generator.conn.cursor()
                        cursor.execute("""
                            SELECT performance_section, business_value_section, recommendations_section
                            FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.weekly_reports
                            WHERE csm_id = %s AND customer_id = %s
                            ORDER BY generation_timestamp DESC
                            LIMIT 1
                        """, (args.csm_id, args.customer_id))
                        
                        sections_row = cursor.fetchone()
                        cursor.close()
                        
                        if sections_row:
                            report_sections = {
                                'performance': sections_row[0],
                                'business_value': sections_row[1],
                                'recommendations': sections_row[2]
                            }
                            
                            week_end = datetime.now()
                            week_start = week_end - timedelta(days=7)
                            
                            pdf_gen = PDFReportGenerator()
                            try:
                                pdf_gen.generate_pdf_report(
                                    customer_id=args.customer_id,
                                    csm_name=csm_name,
                                    report_sections=report_sections,
                                    output_path=args.pdf_output,
                                    week_start=week_start,
                                    week_end=week_end
                                )
                                print(f"\n✓ PDF report generated: {args.pdf_output}")
                            finally:
                                pdf_gen.close()
                        else:
                            print("\n⚠ No report sections found in database for PDF generation")
                    else:
                        print("\n⚠ CSM not found for PDF generation")
                        
                except ImportError as e:
                    print(f"\n⚠ PDF generation requires additional packages: {e}")
                    print("   Install with: pip install matplotlib reportlab")
                except Exception as e:
                    print(f"\n✗ Error generating PDF: {e}")
        else:
            generator.generate_weekly_reports()
    
    finally:
        generator.close()


if __name__ == "__main__":
    main()
