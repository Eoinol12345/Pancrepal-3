import csv
import io
import gc  # OPTIMIZATION: Garbage collection for memory cleanup
from datetime import datetime
from typing import List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import matplotlib

matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

from db import LogEntry
from analytics import calculate_advanced_metrics, prepare_export_data


# ============================================================================
# CSV EXPORT
# ============================================================================

def generate_csv_export(entries: List[LogEntry]) -> str:
    """
    Generate CSV file with all log entry data.

    Format optimized for:
    - Import into Excel/Google Sheets
    - Clinical review systems
    - Personal backup

    Args:
        entries: List of LogEntry objects

    Returns:
        CSV string ready for download
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        'Date',
        'Time',
        'Blood Glucose (mmol/L)',
        'Carbs (g)',
        'Meal Type',
        'Mood',
        'Notes'
    ])

    # Data rows - Irish date format (DD/MM/YYYY)
    for entry in sorted(entries, key=lambda e: e.timestamp):
        writer.writerow([
            entry.timestamp.strftime('%d/%m/%Y'),  # DD/MM/YYYY for Ireland
            entry.timestamp.strftime('%H:%M'),
            entry.blood_glucose,
            entry.carbs_grams if entry.carbs_grams is not None else '',
            entry.meal_type,
            entry.mood,
            entry.notes if entry.notes else ''
        ])

    return output.getvalue()


# ============================================================================
# PDF EXPORT - CHARTS (OPTIMIZED + FIXED)
# ============================================================================

def create_glucose_trend_chart(entries: List[LogEntry]) -> BytesIO:
    """
    Create professional glucose trend chart for PDF embedding.

    OPTIMIZATION: Reduced size (7x3 instead of 10x4) and DPI (100 instead of 150)
    FIX: Smart date tick intervals to prevent MAXTICKS error
    Memory savings: ~50% reduction

    Args:
        entries: List of LogEntry objects

    Returns:
        BytesIO buffer containing the chart image
    """
    # OPTIMIZATION: Smaller figure size (was 10, 4)
    fig, ax = plt.subplots(figsize=(7, 3))

    # Sort entries by timestamp
    sorted_entries = sorted(entries, key=lambda e: e.timestamp)

    # Extract data
    timestamps = [e.timestamp for e in sorted_entries]
    glucose_values = [e.blood_glucose for e in sorted_entries]

    # Plot glucose line
    ax.plot(timestamps, glucose_values, color='#4A90E2', linewidth=2, marker='o', markersize=3)

    # Add target range shading
    ax.axhspan(3.9, 10.0, alpha=0.1, color='green', label='Target Range')
    ax.axhline(y=3.9, color='orange', linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(y=10.0, color='orange', linestyle='--', linewidth=1, alpha=0.5)

    # Formatting
    ax.set_xlabel('Date', fontsize=9)
    ax.set_ylabel('Blood Glucose (mmol/L)', fontsize=9)
    ax.set_title('Glucose Trend', fontsize=11, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=7)

    # FIX: Smart date axis formatting - prevents MAXTICKS error
    unique_dates = sorted(set(e.timestamp.date() for e in sorted_entries))
    num_days = len(unique_dates)

    # Smart tick interval based on date range
    if num_days <= 7:
        tick_interval = 1  # Show every day
    elif num_days <= 30:
        tick_interval = 3  # Show every 3 days
    elif num_days <= 60:
        tick_interval = 7  # Show every week
    else:
        tick_interval = 14  # Show every 2 weeks

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=tick_interval))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45, ha='right', fontsize=8)
    plt.yticks(fontsize=8)

    # Set y-axis limits
    ax.set_ylim(2, max(15, max(glucose_values) + 2))

    plt.tight_layout()

    # Save to buffer - OPTIMIZATION: Lower DPI (was 150)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)

    # OPTIMIZATION: Force cleanup
    plt.close(fig)

    return buffer


def create_carb_overlay_chart(entries: List[LogEntry]) -> BytesIO:
    """
    Create chart with glucose line and carb bars overlay.

    OPTIMIZATION: Reduced size and DPI for memory efficiency
    FIX: Smart date tick intervals to prevent MAXTICKS error

    US-22: Visual correlation between carbs and glucose

    Args:
        entries: List of LogEntry objects

    Returns:
        BytesIO buffer containing the chart image
    """
    # OPTIMIZATION: Smaller figure (was 10, 4)
    fig, ax1 = plt.subplots(figsize=(7, 3))

    sorted_entries = sorted(entries, key=lambda e: e.timestamp)
    timestamps = [e.timestamp for e in sorted_entries]
    glucose_values = [e.blood_glucose for e in sorted_entries]
    carb_values = [e.carbs_grams if e.carbs_grams is not None else 0 for e in sorted_entries]

    # Glucose line (primary y-axis)
    color = '#4A90E2'
    ax1.set_xlabel('Date', fontsize=9)
    ax1.set_ylabel('Blood Glucose (mmol/L)', color=color, fontsize=9)
    ax1.plot(timestamps, glucose_values, color=color, linewidth=2, marker='o', markersize=3, label='Glucose')
    ax1.tick_params(axis='y', labelcolor=color, labelsize=8)
    ax1.set_ylim(2, max(15, max(glucose_values) + 2))

    # Carb bars (secondary y-axis)
    ax2 = ax1.twinx()
    color = '#F0AD4E'
    ax2.set_ylabel('Carbohydrates (g)', color=color, fontsize=9)
    ax2.bar(timestamps, carb_values, color=color, alpha=0.3, width=0.3, label='Carbs')
    ax2.tick_params(axis='y', labelcolor=color, labelsize=8)
    ax2.set_ylim(0, max(150, max(carb_values) + 20) if carb_values else 150)

    # Title and grid
    ax1.set_title('Glucose & Carbohydrate Correlation', fontsize=11, fontweight='bold')
    ax1.grid(True, alpha=0.3)

    # FIX: Smart date axis formatting - prevents MAXTICKS error
    unique_dates = sorted(set(e.timestamp.date() for e in sorted_entries))
    num_days = len(unique_dates)

    # Smart tick interval based on date range
    if num_days <= 7:
        tick_interval = 1  # Show every day
    elif num_days <= 30:
        tick_interval = 3  # Show every 3 days
    elif num_days <= 60:
        tick_interval = 7  # Show every week
    else:
        tick_interval = 14  # Show every 2 weeks

    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=tick_interval))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45, ha='right', fontsize=8)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=7)

    plt.tight_layout()

    # OPTIMIZATION: Lower DPI (was 150)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)

    # OPTIMIZATION: Force cleanup
    plt.close(fig)

    return buffer


# ============================================================================
# PDF EXPORT - DOCUMENT GENERATION (OPTIMIZED)
# ============================================================================

def generate_pdf_report(user_email: str, entries: List[LogEntry], days: int = 30) -> BytesIO:
    """
    Generate comprehensive PDF report for healthcare providers.

    US-21: Professional medical report with:
    - Patient information header
    - Summary statistics
    - Glucose trend charts
    - Detailed data tables
    - Carb correlation analysis

    MEMORY OPTIMIZATIONS:
    - Reduced chart sizes and DPI
    - Limited detailed log to 30 entries (was 50)
    - Aggressive cleanup with gc.collect()
    - Fixed date axis to prevent MAXTICKS error

    Args:
        user_email: Patient identifier
        entries: List of LogEntry objects
        days: Report period (30, 60, or 90 days)

    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#4A90E2'),
        spaceAfter=12,
        spaceBefore=12
    )

    # ========================================
    # HEADER: Report Title & Patient Info
    # ========================================
    story.append(Paragraph("PancrePal Diabetes Management Report", title_style))
    story.append(Spacer(1, 0.2 * inch))

    # Patient information table - Irish date format
    report_date = datetime.now().strftime('%d %B %Y')  # e.g., "10 February 2026"
    date_range_start = min(e.timestamp for e in entries).strftime('%d %B %Y')
    date_range_end = max(e.timestamp for e in entries).strftime('%d %B %Y')

    patient_data = [
        ['Patient Email:', user_email],
        ['Report Generated:', report_date],
        ['Data Period:', f'{days} days ({date_range_start} to {date_range_end})'],
        ['Total Readings:', str(len(entries))]
    ]

    patient_table = Table(patient_data, colWidths=[2 * inch, 4 * inch])
    patient_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2C3E50')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))

    story.append(patient_table)
    story.append(Spacer(1, 0.3 * inch))

    # ========================================
    # SECTION 1: Summary Statistics (US-23)
    # ========================================
    story.append(Paragraph("Clinical Summary", heading_style))

    metrics = calculate_advanced_metrics(entries)

    summary_data = [
        ['Metric', 'Value', 'Target'],
        ['Average Glucose', f"{metrics['mean_glucose']} mmol/L", '6.0-8.0 mmol/L'],
        ['Time in Range (3.9-10.0)', f"{metrics['time_in_range_pct']}%", '≥70%'],
        ['Time Below Range (<3.9)', f"{metrics['time_below_range_pct']}%", '<4%'],
        ['Time Above Range (>10.0)', f"{metrics['time_above_range_pct']}%", '<25%'],
        ['Glucose Variability (CV)', f"{metrics['coefficient_of_variation']}%", '<36%'],
        ['Standard Deviation', f"{metrics['std_dev']} mmol/L", '<2.0'],
        ['Hypoglycemic Events', str(metrics['hypo_events']), 'Minimize'],
        ['Hyperglycemic Events', str(metrics['hyper_events']), 'Minimize'],
    ]

    # Add carb data if available (US-22)
    if metrics['avg_daily_carbs']:
        summary_data.append(['Average Daily Carbs', f"{metrics['avg_daily_carbs']}g", 'Individual'])

    summary_table = Table(summary_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch])
    summary_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 11),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    # ========================================
    # SECTION 2: Glucose Trend Chart
    # ========================================
    story.append(Paragraph("Glucose Trend Analysis", heading_style))

    # Generate and embed chart
    chart_buffer = create_glucose_trend_chart(entries)
    # OPTIMIZATION: Smaller image (was 6.5 x 2.6)
    chart_img = Image(chart_buffer, width=5.5 * inch, height=2.2 * inch)
    story.append(chart_img)
    story.append(Spacer(1, 0.2 * inch))

    # OPTIMIZATION: Close buffer
    chart_buffer.close()

    # ========================================
    # SECTION 3: Carb Correlation (US-22)
    # ========================================
    if metrics['entries_with_carbs'] > 0:
        story.append(PageBreak())
        story.append(Paragraph("Carbohydrate & Glucose Correlation", heading_style))

        carb_chart_buffer = create_carb_overlay_chart(entries)
        # OPTIMIZATION: Smaller image
        carb_chart_img = Image(carb_chart_buffer, width=5.5 * inch, height=2.2 * inch)
        story.append(carb_chart_img)
        story.append(Spacer(1, 0.3 * inch))

        # OPTIMIZATION: Close buffer
        carb_chart_buffer.close()

    # OPTIMIZATION: Force garbage collection after charts
    gc.collect()

    # ========================================
    # SECTION 4: Detailed Data Table
    # ========================================
    story.append(Paragraph("Detailed Reading Log", heading_style))

    # OPTIMIZATION: Show 30 entries instead of 50 (saves ~40% memory)
    table_data = [['Date', 'Time', 'Glucose', 'Carbs', 'Meal', 'Notes']]

    for entry in sorted(entries, key=lambda e: e.timestamp, reverse=True)[:30]:
        table_data.append([
            entry.timestamp.strftime('%d/%m'),  # DD/MM format
            entry.timestamp.strftime('%H:%M'),
            f'{entry.blood_glucose}',
            f'{entry.carbs_grams}g' if entry.carbs_grams else '-',
            entry.meal_type.capitalize()[:8],  # Full meal name (max 8 chars for table)
            (entry.notes[:35] + '...') if entry.notes and len(entry.notes) > 35 else (entry.notes or '-')
        ])

    detail_table = Table(table_data, colWidths=[0.7 * inch, 0.7 * inch, 0.8 * inch, 0.7 * inch, 0.8 * inch, 2.8 * inch])
    detail_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 9),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(detail_table)
    story.append(Spacer(1, 0.3 * inch))

    # ========================================
    # FOOTER: Disclaimer
    # ========================================
    story.append(Spacer(1, 0.5 * inch))
    disclaimer = Paragraph(
        "<i>This report is generated from patient-logged data and is intended to supplement clinical assessment. "
        "Please review with patient for accuracy and context. PancrePal is a self-management tool and does not "
        "replace professional medical advice.</i>",
        styles['Normal']
    )
    story.append(disclaimer)

    # Build PDF
    doc.build(story)
    buffer.seek(0)

    # OPTIMIZATION: Final garbage collection
    gc.collect()

    return buffer
