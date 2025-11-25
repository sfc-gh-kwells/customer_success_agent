"""
PDF Report Generator with Charts

This module generates PDF executive reports with visualizations from the weekly report data.
Uses ReportLab for PDF generation and matplotlib for charts.
"""

import io
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import snowflake.connector

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
    Table, TableStyle, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY


class PDFReportGenerator:
    """Generates PDF reports with charts from weekly report data."""
    
    def __init__(self, connection_name: str = "MY_DEMO"):
        """Initialize the PDF report generator with Snowflake connection."""
        self.conn = snowflake.connector.connect(
            connection_name=os.getenv("SNOWFLAKE_CONNECTION_NAME") or connection_name
        )
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
    def _setup_custom_styles(self):
        """Define custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E3A8A'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Section heading style
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1E3A8A'),
            spaceBefore=20,
            spaceAfter=12,
            borderWidth=0,
            borderPadding=5,
            borderColor=colors.HexColor('#3B82F6'),
            backColor=colors.HexColor('#EFF6FF')
        ))
        
        # Body text style
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=10
        ))
        
        # Metric style (for highlighting key numbers)
        self.styles.add(ParagraphStyle(
            name='MetricText',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#059669'),
            fontName='Helvetica-Bold'
        ))
    
    def get_customer_metrics(self, customer_id: str, days: int = 30) -> Dict:
        """Fetch customer metrics from the database."""
        cursor = self.conn.cursor()
        
        # Get conversion metrics
        cursor.execute("""
            SELECT 
                DATE_TRUNC('day', conversion_date) as date,
                COUNT(*) as conversion_count,
                SUM(conversion_value) as total_revenue,
                AVG(conversion_value) as avg_conversion_value
            FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.conversions
            WHERE customer_id = %s
              AND conversion_date >= DATEADD(day, -%s, CURRENT_DATE())
            GROUP BY 1
            ORDER BY 1
        """, (customer_id, days))
        
        conversion_data = cursor.fetchall()
        
        # Get engagement metrics by channel
        cursor.execute("""
            SELECT 
                channel,
                SUM(messages_sent) as total_sent,
                SUM(messages_opened) as total_opened,
                SUM(messages_clicked) as total_clicked,
                AVG(engagement_score) as avg_engagement_score
            FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.historical_engagement
            WHERE customer_id = %s
              AND engagement_date >= DATEADD(day, -%s, CURRENT_DATE())
            GROUP BY 1
            ORDER BY 2 DESC
        """, (customer_id, days))
        
        engagement_by_channel = cursor.fetchall()
        
        # Get attribution by channel
        cursor.execute("""
            SELECT 
                channel,
                COUNT(*) as touchpoint_count,
                SUM(attributed_revenue) as total_attributed_revenue,
                AVG(attribution_weight) as avg_attribution_weight
            FROM CUSTOMER_SUCCESS_DATA.ANALYTICS.attributions
            WHERE customer_id = %s
              AND touchpoint_date >= DATEADD(day, -%s, CURRENT_DATE())
            GROUP BY 1
            ORDER BY 3 DESC
        """, (customer_id, days))
        
        attribution_data = cursor.fetchall()
        
        cursor.close()
        
        return {
            'conversion_data': conversion_data,
            'engagement_by_channel': engagement_by_channel,
            'attribution_data': attribution_data
        }
    
    def create_conversion_trend_chart(self, conversion_data: List, customer_id: str) -> str:
        """Create a line chart showing conversion trends over time."""
        if not conversion_data:
            return None
            
        fig, ax = plt.subplots(figsize=(10, 5))
        
        dates = [row[0] for row in conversion_data]
        revenues = [float(row[2]) if row[2] else 0 for row in conversion_data]
        counts = [int(row[1]) if row[1] else 0 for row in conversion_data]
        
        # Create dual axis
        ax1 = ax
        ax2 = ax1.twinx()
        
        # Plot revenue
        ax1.plot(dates, revenues, color='#3B82F6', linewidth=2, marker='o', label='Revenue')
        ax1.set_xlabel('Date', fontsize=12)
        ax1.set_ylabel('Revenue ($)', color='#3B82F6', fontsize=12)
        ax1.tick_params(axis='y', labelcolor='#3B82F6')
        ax1.grid(True, alpha=0.3)
        
        # Plot conversion count
        ax2.bar(dates, counts, color='#10B981', alpha=0.3, label='Conversions')
        ax2.set_ylabel('Conversion Count', color='#10B981', fontsize=12)
        ax2.tick_params(axis='y', labelcolor='#10B981')
        
        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        plt.title(f'Conversion Trends - {customer_id}', fontsize=14, fontweight='bold')
        
        # Add legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        plt.tight_layout()
        
        # Save to bytes
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        # Save to temp file
        temp_file = f'/tmp/conversion_trend_{customer_id}.png'
        with open(temp_file, 'wb') as f:
            f.write(img_buffer.getvalue())
        
        return temp_file
    
    def create_channel_performance_chart(self, engagement_data: List, customer_id: str) -> str:
        """Create a bar chart showing channel performance metrics."""
        if not engagement_data:
            return None
            
        fig, ax = plt.subplots(figsize=(10, 5))
        
        channels = [row[0] for row in engagement_data]
        open_rates = [
            (float(row[2]) / float(row[1]) * 100) if row[1] and row[1] > 0 else 0 
            for row in engagement_data
        ]
        ctr = [
            (float(row[3]) / float(row[2]) * 100) if row[2] and row[2] > 0 else 0 
            for row in engagement_data
        ]
        
        x = range(len(channels))
        width = 0.35
        
        ax.bar([i - width/2 for i in x], open_rates, width, label='Open Rate (%)', color='#3B82F6')
        ax.bar([i + width/2 for i in x], ctr, width, label='Click-Through Rate (%)', color='#10B981')
        
        ax.set_xlabel('Channel', fontsize=12)
        ax.set_ylabel('Rate (%)', fontsize=12)
        ax.set_title(f'Channel Performance - {customer_id}', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(channels, rotation=45, ha='right')
        ax.legend()
        ax.grid(True, axis='y', alpha=0.3)
        
        plt.tight_layout()
        
        # Save to temp file
        temp_file = f'/tmp/channel_performance_{customer_id}.png'
        plt.savefig(temp_file, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        
        return temp_file
    
    def create_attribution_chart(self, attribution_data: List, customer_id: str) -> str:
        """Create a horizontal bar chart showing attribution by channel."""
        if not attribution_data:
            return None
            
        fig, ax = plt.subplots(figsize=(10, 5))
        
        channels = [row[0] for row in attribution_data]
        revenues = [float(row[2]) if row[2] else 0 for row in attribution_data]
        
        colors_map = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        bar_colors = [colors_map[i % len(colors_map)] for i in range(len(channels))]
        
        y_pos = range(len(channels))
        ax.barh(y_pos, revenues, color=bar_colors)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(channels)
        ax.set_xlabel('Attributed Revenue ($)', fontsize=12)
        ax.set_title(f'Attribution by Channel - {customer_id}', fontsize=14, fontweight='bold')
        ax.grid(True, axis='x', alpha=0.3)
        
        # Add value labels
        for i, v in enumerate(revenues):
            ax.text(v + max(revenues) * 0.01, i, f'${v:,.0f}', 
                   va='center', fontsize=10)
        
        plt.tight_layout()
        
        # Save to temp file
        temp_file = f'/tmp/attribution_{customer_id}.png'
        plt.savefig(temp_file, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        
        return temp_file
    
    def create_metrics_summary_table(self, metrics: Dict) -> Table:
        """Create a summary table of key metrics."""
        # Calculate summary metrics
        total_conversions = sum(row[1] for row in metrics['conversion_data'] if row[1])
        total_revenue = sum(row[2] for row in metrics['conversion_data'] if row[2])
        avg_conv_value = total_revenue / total_conversions if total_conversions > 0 else 0
        
        total_sent = sum(row[1] for row in metrics['engagement_by_channel'] if row[1])
        total_opened = sum(row[2] for row in metrics['engagement_by_channel'] if row[2])
        overall_open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
        
        data = [
            ['Metric', 'Value'],
            ['Total Conversions', f"{total_conversions:,}"],
            ['Total Revenue', f"${total_revenue:,.2f}"],
            ['Avg Conversion Value', f"${avg_conv_value:,.2f}"],
            ['Messages Sent', f"{total_sent:,}"],
            ['Overall Open Rate', f"{overall_open_rate:.1f}%"],
        ]
        
        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F4F6')]),
        ]))
        
        return table
    
    def generate_pdf_report(
        self,
        customer_id: str,
        csm_name: str,
        report_sections: Dict[str, str],
        output_path: str,
        week_start: datetime,
        week_end: datetime
    ) -> str:
        """Generate a complete PDF report with charts."""
        
        print(f"Generating PDF report for {customer_id}...")
        
        # Create document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        
        # Title page
        story.append(Paragraph(
            "EXECUTIVE REVIEW REPORT",
            self.styles['CustomTitle']
        ))
        story.append(Spacer(1, 0.2*inch))
        
        # Report metadata
        metadata = f"""
        <para align=center>
        <b>Customer:</b> {customer_id}<br/>
        <b>Customer Success Manager:</b> {csm_name}<br/>
        <b>Report Period:</b> {week_start.strftime('%B %d, %Y')} - {week_end.strftime('%B %d, %Y')}<br/>
        <b>Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
        </para>
        """
        story.append(Paragraph(metadata, self.styles['BodyText']))
        story.append(Spacer(1, 0.3*inch))
        
        # Get metrics data
        metrics = self.get_customer_metrics(customer_id, days=30)
        
        # Add executive summary with metrics table
        story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))
        
        summary_table = self.create_metrics_summary_table(metrics)
        story.append(summary_table)
        story.append(Spacer(1, 0.2*inch))
        
        story.append(PageBreak())
        
        # Section 1: Performance Analysis with Charts
        story.append(Paragraph("1. PERFORMANCE VS BENCHMARKS", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))
        
        # Add performance text
        for paragraph in report_sections['performance'].split('\n\n'):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), self.styles['BodyText']))
                story.append(Spacer(1, 0.1*inch))
        
        # Add conversion trend chart
        chart_file = self.create_conversion_trend_chart(metrics['conversion_data'], customer_id)
        if chart_file:
            story.append(Spacer(1, 0.2*inch))
            img = Image(chart_file, width=6.5*inch, height=3.25*inch)
            story.append(img)
            story.append(Spacer(1, 0.2*inch))
        
        story.append(PageBreak())
        
        # Section 2: Business Value with Channel Performance
        story.append(Paragraph("2. BUSINESS VALUE ANALYSIS", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))
        
        # Add business value text
        for paragraph in report_sections['business_value'].split('\n\n'):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), self.styles['BodyText']))
                story.append(Spacer(1, 0.1*inch))
        
        # Add channel performance chart
        chart_file = self.create_channel_performance_chart(metrics['engagement_by_channel'], customer_id)
        if chart_file:
            story.append(Spacer(1, 0.2*inch))
            img = Image(chart_file, width=6.5*inch, height=3.25*inch)
            story.append(img)
            story.append(Spacer(1, 0.2*inch))
        
        # Add attribution chart
        chart_file = self.create_attribution_chart(metrics['attribution_data'], customer_id)
        if chart_file:
            story.append(Spacer(1, 0.2*inch))
            img = Image(chart_file, width=6.5*inch, height=3.25*inch)
            story.append(img)
        
        story.append(PageBreak())
        
        # Section 3: Recommendations
        story.append(Paragraph("3. RECOMMENDATIONS & BEST PRACTICES", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))
        
        # Add recommendations text
        for paragraph in report_sections['recommendations'].split('\n\n'):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), self.styles['BodyText']))
                story.append(Spacer(1, 0.1*inch))
        
        # Build PDF
        doc.build(story)
        
        print(f"✓ PDF report generated: {output_path}")
        
        return output_path
    
    def close(self):
        """Close the Snowflake connection."""
        self.conn.close()


def main():
    """Test PDF generation."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate PDF report with charts')
    parser.add_argument('--customer-id', required=True, help='Customer ID')
    parser.add_argument('--csm-name', required=True, help='CSM name')
    parser.add_argument('--output', default='executive_report.pdf', help='Output PDF file path')
    
    args = parser.parse_args()
    
    # Mock report sections for testing
    report_sections = {
        'performance': """
        Performance analysis for the reporting period shows strong conversion metrics 
        with total revenue of $125,450 from 482 conversions. The average conversion 
        value of $260 represents a 15% increase compared to the previous period.
        
        Channel performance indicates that Email and SMS are the top performers, 
        with Email driving 35% of total conversions and maintaining an open rate of 42%.
        """,
        'business_value': """
        The business value analysis reveals positive trends across key engagement metrics. 
        Customer engagement scores have increased by 12% month-over-month, indicating 
        improved message relevance and timing.
        
        Attribution analysis shows that multi-touch strategies are working effectively, 
        with an average of 3.2 touchpoints per conversion. Email continues to be the 
        strongest attribution channel, contributing $45,000 in attributed revenue.
        """,
        'recommendations': """
        Based on the data analysis and industry best practices, we recommend:
        
        1. Increase investment in Email and SMS channels, which show the highest ROI
        2. Implement A/B testing for push notification timing to improve engagement
        3. Leverage case study insights from similar Media & Entertainment companies
        4. Consider implementing predictive models for churn prevention
        5. Optimize content recommendations based on engagement patterns
        """
    }
    
    generator = PDFReportGenerator()
    
    try:
        week_end = datetime.now()
        week_start = week_end - timedelta(days=7)
        
        output_path = generator.generate_pdf_report(
            customer_id=args.customer_id,
            csm_name=args.csm_name,
            report_sections=report_sections,
            output_path=args.output,
            week_start=week_start,
            week_end=week_end
        )
        
        print(f"\n✓ PDF report generated successfully: {output_path}")
        
    finally:
        generator.close()


if __name__ == "__main__":
    main()
