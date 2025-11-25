# PDF Report Generator - Installation and Usage Guide

## Overview

The PDF report generator creates professional executive review reports with charts and visualizations from your weekly report data.

## Features

- **Professional Layout**: Multi-page PDF with custom styling and branding
- **Interactive Charts**:
  - Conversion trend line chart (revenue + count over time)
  - Channel performance bar chart (open rates + CTR by channel)
  - Attribution horizontal bar chart (revenue by channel)
- **Executive Summary**: Key metrics table
- **Three Main Sections**: Performance, Business Value, Recommendations
- **Automated Data Visualization**: Pulls metrics directly from Snowflake

## Installation

### Required Python Packages

```bash
# Core dependencies (already installed for weekly reports)
pip install snowflake-connector-python requests

# PDF generation dependencies
pip install matplotlib reportlab
```

### Package Details

- **matplotlib**: Creates charts and visualizations
- **reportlab**: Generates professional PDF documents

## Usage

### Generate Text Report + PDF

```bash
# Generate both text and PDF report for a single customer
python weekly_report_generator.py \
  --mode single \
  --csm-id CSM001 \
  --customer-id CUST_12345 \
  --pdf \
  --pdf-output reports/customer_12345_report.pdf
```

### Generate Text Report Only (Default)

```bash
# Text report only (no PDF)
python weekly_report_generator.py \
  --mode single \
  --csm-id CSM001 \
  --customer-id CUST_12345
```

### Test PDF Generator Standalone

```bash
# Test PDF generation with mock data
python pdf_report_generator.py \
  --customer-id CUST_12345 \
  --csm-name "Sarah Johnson" \
  --output test_report.pdf
```

## PDF Report Structure

### Page 1: Title & Executive Summary
- Report title and metadata (customer, CSM, date range)
- Key metrics summary table:
  - Total Conversions
  - Total Revenue
  - Average Conversion Value
  - Messages Sent
  - Overall Open Rate

### Page 2: Performance Analysis
- Performance vs Benchmarks text section
- **Chart 1**: Conversion Trends Over Time
  - Dual-axis line chart
  - Revenue trend (blue line)
  - Conversion count (green bars)
  - 30-day historical view

### Page 3: Business Value Analysis
- Business value analysis text section
- **Chart 2**: Channel Performance
  - Bar chart comparing open rates and CTR
  - Side-by-side bars per channel
  - Highlights top-performing channels
- **Chart 3**: Attribution by Channel
  - Horizontal bar chart
  - Shows attributed revenue per channel
  - Color-coded for easy comparison

### Page 4: Recommendations
- Recommendations & best practices text section
- Action items with supporting data
- Case study references

## Chart Details

### 1. Conversion Trend Chart
**Data Source**: `conversions` table (last 30 days)
**Metrics**:
- Revenue (line, primary y-axis)
- Conversion count (bars, secondary y-axis)
**Purpose**: Show daily performance trends and patterns

### 2. Channel Performance Chart
**Data Source**: `historical_engagement` table (last 30 days)
**Metrics**:
- Open rate percentage by channel
- Click-through rate percentage by channel
**Purpose**: Compare engagement effectiveness across channels

### 3. Attribution Chart
**Data Source**: `attributions` table (last 30 days)
**Metrics**:
- Total attributed revenue per channel
**Purpose**: Understand channel contribution to conversions

## Customization

### Modify Chart Styles

Edit `pdf_report_generator.py`:

```python
# Change colors
ax.plot(dates, revenues, color='#YOUR_COLOR_HEX')

# Change chart size
fig, ax = plt.subplots(figsize=(WIDTH, HEIGHT))

# Adjust DPI (resolution)
plt.savefig(temp_file, format='png', dpi=150)  # Higher = better quality
```

### Modify PDF Layout

Edit custom styles in `_setup_custom_styles()`:

```python
# Change title color
self.styles['CustomTitle'].textColor = colors.HexColor('#YOUR_COLOR')

# Change section heading style
self.styles['SectionHeading'].fontSize = 18  # Larger headings
```

### Add New Charts

1. Create chart function in `PDFReportGenerator` class:
```python
def create_your_custom_chart(self, data, customer_id):
    # Your matplotlib code here
    fig, ax = plt.subplots(figsize=(10, 5))
    # ... chart creation logic ...
    plt.savefig(temp_file, format='png', dpi=150)
    return temp_file
```

2. Add chart to report in `generate_pdf_report()`:
```python
chart_file = self.create_your_custom_chart(data, customer_id)
if chart_file:
    img = Image(chart_file, width=6.5*inch, height=3.25*inch)
    story.append(img)
```

## Data Requirements

For charts to render properly, ensure:

1. **Customer has activity**: At least some conversions, engagement, or attribution data
2. **Date range**: Data within the last 30 days
3. **Valid customer_id**: Matches data in source tables

## File Outputs

### Generated Files

```
/tmp/
  ├── conversion_trend_CUST_12345.png    # Temporary chart files
  ├── channel_performance_CUST_12345.png
  └── attribution_CUST_12345.png

/path/to/output/
  └── executive_report.pdf                # Final PDF report
```

### Cleanup

Temporary chart PNG files are created in `/tmp/` and can be cleaned up:

```bash
rm /tmp/conversion_trend_*.png
rm /tmp/channel_performance_*.png
rm /tmp/attribution_*.png
```

## Integration with Snowflake Task

To generate PDFs automatically with the weekly task, modify the stored procedure in `setup_weekly_task.sql` to include PDF generation logic (requires Snowflake external access for file I/O).

Alternatively:
1. Run task to generate text reports in database
2. Run separate Python script to generate PDFs from stored reports
3. Upload PDFs to Snowflake stage or external storage

## Troubleshooting

### Missing Data / Empty Charts

```python
# Check if customer has data
SELECT COUNT(*) FROM conversions WHERE customer_id = 'CUST_12345';
SELECT COUNT(*) FROM historical_engagement WHERE customer_id = 'CUST_12345';
```

### Import Errors

```bash
# Verify packages are installed
python -c "import matplotlib; import reportlab; print('OK')"

# If errors, reinstall
pip install --upgrade matplotlib reportlab
```

### Chart Not Rendering

- Check that data query returns results
- Verify customer_id exists in source tables
- Check date range (last 30 days)
- Ensure matplotlib backend is set to 'Agg' (non-interactive)

### PDF Layout Issues

- Adjust image sizes: `width=6.5*inch, height=3.25*inch`
- Add more spacers: `story.append(Spacer(1, 0.3*inch))`
- Use `PageBreak()` to control page breaks

## Example Output

### Executive Summary Table
```
┌─────────────────────────┬──────────────┐
│ Metric                  │ Value        │
├─────────────────────────┼──────────────┤
│ Total Conversions       │ 482          │
│ Total Revenue           │ $125,450.00  │
│ Avg Conversion Value    │ $260.19      │
│ Messages Sent           │ 45,230       │
│ Overall Open Rate       │ 42.3%        │
└─────────────────────────┴──────────────┘
```

### Chart Types

1. **Line + Bar Combo**: Shows trends with dual metrics
2. **Grouped Bar**: Compares multiple metrics side-by-side
3. **Horizontal Bar**: Emphasizes ranking and comparison

## Best Practices

1. **Generate PDFs after text reports**: Ensure data is saved to database first
2. **Use descriptive filenames**: `reports/CSM001_CUST12345_2025W47.pdf`
3. **Archive PDFs**: Store in date-organized directories
4. **Review before sending**: Check data accuracy and chart quality
5. **Customize for audience**: Adjust detail level for executives vs. analysts

## Advanced Features

### Add Company Branding

```python
# Add logo to title page
logo = Image('/path/to/logo.png', width=2*inch, height=1*inch)
story.insert(0, logo)

# Custom color scheme
PRIMARY_COLOR = colors.HexColor('#YOUR_BRAND_COLOR')
```

### Multi-Customer Comparison

Create comparison charts showing multiple customers:
```python
def create_comparison_chart(self, customer_ids):
    # Plot multiple customers on same chart
    for cid in customer_ids:
        data = self.get_customer_metrics(cid)
        ax.plot(dates, revenues, label=cid)
```

### Export Charts Separately

```python
# Save chart as standalone file
chart_file = generator.create_conversion_trend_chart(metrics, customer_id)
# File is saved to /tmp/ and can be copied elsewhere
```

## Support

For issues with:
- **Chart data**: Check source tables and SQL queries
- **PDF layout**: Review ReportLab documentation
- **Chart styling**: Review matplotlib documentation
- **Integration**: Check weekly_report_generator.py integration

## Files

- `pdf_report_generator.py` - PDF generation class with chart functions
- `weekly_report_generator.py` - Integrated weekly report generator (text + PDF)
- `README_PDF_REPORTS.md` - This documentation
