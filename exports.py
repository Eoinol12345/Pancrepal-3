"""
US-21: Doctor-Ready Export - CSV Only

Professional CSV export for healthcare providers.
PDF export temporarily disabled due to hosting memory constraints.

FEATURES:
- CSV export using Python's csv module
- Date range selector: 30 / 60 / 90 day views
- Irish/European date format (DD/MM/YYYY)
- Includes all data: glucose, carbs, meal type, mood, notes
"""

import csv
import io
from datetime import datetime
from typing import List

from db import LogEntry


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
