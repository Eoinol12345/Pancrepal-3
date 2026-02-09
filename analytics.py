from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional
from db import LogEntry
import statistics

# ============================================================================
# GLUCOSE RANGES (mmol/L)
# ============================================================================
GLUCOSE_TARGET_MIN = 3.9
GLUCOSE_TARGET_MAX = 10.0
GLUCOSE_HIGH_THRESHOLD = 11.1
GLUCOSE_LOW_THRESHOLD = 3.3


# ============================================================================
# US-23: ADVANCED ANALYTICS & METRICS
# ============================================================================

def calculate_advanced_metrics(entries: List[LogEntry]) -> Dict:
    """
    Calculate comprehensive glucose metrics for professional reporting.

    US-23: Advanced Analytics
    - Standard deviation (variability)
    - Time-in-range percentage
    - Hypoglycemia frequency
    - Hyperglycemia frequency
    - Coefficient of variation
    - Average daily carbs (if tracking enabled)

    Args:
        entries: List of LogEntry objects

    Returns:
        Dictionary containing all advanced metrics
    """
    if not entries:
        return {
            'status': 'no_data',
            'message': 'No data available for analysis'
        }

    glucose_values = [e.blood_glucose for e in entries]
    total_readings = len(glucose_values)

    # Basic statistics
    mean_glucose = statistics.mean(glucose_values)

    # Standard deviation (glucose variability)
    if len(glucose_values) > 1:
        std_dev = statistics.stdev(glucose_values)
        coefficient_of_variation = (std_dev / mean_glucose) * 100 if mean_glucose > 0 else 0
    else:
        std_dev = 0
        coefficient_of_variation = 0

    # Time in range
    in_range = [g for g in glucose_values if GLUCOSE_TARGET_MIN <= g <= GLUCOSE_TARGET_MAX]
    time_in_range_pct = (len(in_range) / total_readings) * 100

    # Hypoglycemia (<3.9 mmol/L)
    hypos = [g for g in glucose_values if g < GLUCOSE_LOW_THRESHOLD]
    hypo_frequency = len(hypos)
    hypo_percentage = (hypo_frequency / total_readings) * 100

    # Hyperglycemia (>10.0 mmol/L)
    hypers = [g for g in glucose_values if g > GLUCOSE_TARGET_MAX]
    hyper_frequency = len(hypers)
    hyper_percentage = (hyper_frequency / total_readings) * 100

    # US-22: Carb analytics - FIXED: None instead of none
    entries_with_carbs = [e for e in entries if e.carbs_grams is not None]
    if entries_with_carbs:
        total_carbs = sum(e.carbs_grams for e in entries_with_carbs)
        avg_carbs_per_entry = total_carbs / len(entries_with_carbs)

        # Calculate average daily carbs
        unique_dates = set(e.timestamp.date() for e in entries_with_carbs)
        avg_daily_carbs = total_carbs / len(unique_dates) if unique_dates else 0
    else:
        avg_carbs_per_entry = None
        avg_daily_carbs = None
        total_carbs = 0

    # Determine overall status
    if time_in_range_pct >= 70 and coefficient_of_variation < 36:
        status = 'excellent'
        trend = 'improving'
    elif time_in_range_pct >= 50 and coefficient_of_variation < 50:
        status = 'good'
        trend = 'stable'
    else:
        status = 'needs_attention'
        trend = 'needs_attention'

    return {
        'status': status,
        'trend': trend,

        # Core metrics
        'mean_glucose': round(mean_glucose, 1),
        'std_dev': round(std_dev, 1),
        'coefficient_of_variation': round(coefficient_of_variation, 1),

        # Range metrics
        'time_in_range_pct': round(time_in_range_pct, 1),
        'time_below_range_pct': round(hypo_percentage, 1),
        'time_above_range_pct': round(hyper_percentage, 1),

        # Frequency counts
        'total_readings': total_readings,
        'hypo_events': hypo_frequency,
        'hyper_events': hyper_frequency,

        # Carb metrics (US-22)
        'avg_carbs_per_entry': round(avg_carbs_per_entry, 1) if avg_carbs_per_entry else None,
        'avg_daily_carbs': round(avg_daily_carbs, 1) if avg_daily_carbs else None,
        'total_carbs': total_carbs,
        'entries_with_carbs': len(entries_with_carbs)
    }


def get_metric_explanation(metric_name: str) -> Dict:
    """
    Get user-friendly explanation for each metric.

    US-23: Helps users understand what metrics mean and why they matter.

    Args:
        metric_name: Name of the metric

    Returns:
        Dictionary with title, description, and target range
    """
    explanations = {
        'time_in_range': {
            'title': 'Time in Range',
            'description': 'Percentage of readings between 3.9-10.0 mmol/L. This is the most important metric for diabetes management.',
            'target': '70% or higher',
            'icon': '🎯'
        },
        'coefficient_of_variation': {
            'title': 'Glucose Variability',
            'description': 'Measures how much your glucose levels fluctuate. Lower is better - it means more stable control.',
            'target': 'Below 36%',
            'icon': '📊'
        },
        'hypo_events': {
            'title': 'Low Glucose Events',
            'description': 'Number of readings below 3.9 mmol/L. Important to minimize these for safety.',
            'target': 'Less than 4% of readings',
            'icon': '⚠️'
        },
        'hyper_events': {
            'title': 'High Glucose Events',
            'description': 'Number of readings above 10.0 mmol/L. Reducing these improves long-term health outcomes.',
            'target': 'Less than 25% of readings',
            'icon': '📈'
        },
        'avg_glucose': {
            'title': 'Average Glucose',
            'description': 'Your mean blood glucose level. Useful but doesn\'t show the full picture - variability matters too!',
            'target': '6.0-8.0 mmol/L',
            'icon': '📉'
        },
        'avg_daily_carbs': {
            'title': 'Average Daily Carbs',
            'description': 'How many grams of carbohydrates you consume per day on average. Helps plan insulin doses.',
            'target': 'Varies by individual',
            'icon': '🥖'
        }
    }

    return explanations.get(metric_name, {
        'title': metric_name.replace('_', ' ').title(),
        'description': 'Track this metric to understand your diabetes management.',
        'target': 'Consult your healthcare team',
        'icon': '📊'
    })


# ============================================================================
# EXISTING ANALYTICS FUNCTIONS (UPDATED FOR US-22, US-23)
# ============================================================================

def analyze_weekly_trend(entries: List[LogEntry]) -> Dict:
    """
    Analyze glucose patterns over the past week.
    Updated with advanced metrics from US-23.

    Args:
        entries: List of LogEntry objects from the past 7 days

    Returns:
        Dictionary containing analysis results and encouraging message
    """
    if not entries:
        return {
            'status': 'no_data',
            'message': "Start logging to see your personalized insights!",
            'icon': '📊'
        }

    # Use advanced metrics calculation
    metrics = calculate_advanced_metrics(entries)

    # Generate encouraging message based on metrics
    if metrics['status'] == 'excellent':
        message = '🌟 Amazing work this week! Your glucose levels show great consistency.'
        icon = '🎉'
    elif metrics['status'] == 'good':
        message = '💪 You\'re doing well! Keep up the steady progress.'
        icon = '✨'
    else:
        message = '🤗 We see you\'re working on it. Every log helps you understand patterns better!'
        icon = '💙'

    return {
        'status': metrics['status'],
        'message': message,
        'icon': icon,
        'time_in_range': metrics['time_in_range_pct'],
        'avg_glucose': metrics['mean_glucose'],
        'consistency': 100 - min(metrics['coefficient_of_variation'], 100)  # Inverse of CV
    }


def identify_recurring_patterns(entries: List[LogEntry]) -> List[Dict]:
    """
    Identify recurring high or low glucose patterns by time and meal type.
    Updated to include carb patterns (US-22).

    Args:
        entries: List of LogEntry objects

    Returns:
        List of pattern dictionaries with supportive messaging
    """
    if len(entries) < 3:
        return []

    patterns = []

    # Group by meal type
    meal_groups = defaultdict(list)
    for entry in entries:
        meal_groups[entry.meal_type].append(entry)

    # Analyze each meal type
    for meal_type, meal_entries in meal_groups.items():
        if len(meal_entries) < 2:
            continue

        glucose_values = [e.blood_glucose for e in meal_entries]
        avg = sum(glucose_values) / len(glucose_values)
        high_count = sum(1 for g in glucose_values if g > GLUCOSE_HIGH_THRESHOLD)
        low_count = sum(1 for g in glucose_values if g < GLUCOSE_LOW_THRESHOLD)

        # US-22: Check carb patterns
        entries_with_carbs = [e for e in meal_entries if e.carbs_grams is not None]
        if len(entries_with_carbs) >= 2:
            avg_carbs = sum(e.carbs_grams for e in entries_with_carbs) / len(entries_with_carbs)

            # High carb meals with high glucose
            if avg_carbs > 60 and avg > GLUCOSE_HIGH_THRESHOLD:
                patterns.append({
                    'type': 'high_carb_high_glucose',
                    'context': meal_type,
                    'message': f'🥖 High carb {meal_type}s (avg {round(avg_carbs)}g) often lead to high readings. Consider portion sizes or timing.',
                    'severity': 'info'
                })
                continue

        # Pattern: Consistent highs after a meal
        if high_count >= len(glucose_values) * 0.6:  # 60%+ highs
            patterns.append({
                'type': 'recurring_high',
                'context': meal_type,
                'message': f'📈 You often see higher readings after {meal_type}. Consider checking portion sizes or insulin timing.',
                'severity': 'info'
            })

        # Pattern: Consistent lows
        elif low_count >= len(glucose_values) * 0.5:  # 50%+ lows
            patterns.append({
                'type': 'recurring_low',
                'context': meal_type,
                'message': f'⚠️ You\'ve had some lows around {meal_type} time. Let\'s keep an eye on this pattern together.',
                'severity': 'warning'
            })

        # Pattern: Good consistency
        elif GLUCOSE_TARGET_MIN <= avg <= GLUCOSE_TARGET_MAX:
            patterns.append({
                'type': 'in_range',
                'context': meal_type,
                'message': f'✅ Great job keeping {meal_type} readings in range!',
                'severity': 'success'
            })

    return patterns[:3]  # Return top 3 patterns


def generate_weekly_suggestion(entries: List[LogEntry]) -> Optional[str]:
    """
    Generate a proactive, actionable suggestion based on weekly patterns.
    Updated with carb-aware suggestions (US-22).

    Args:
        entries: List of LogEntry objects

    Returns:
        Suggestion string or None if insufficient data
    """
    if len(entries) < 5:
        return None

    # Analyze time-of-day patterns
    morning_entries = [e for e in entries if 5 <= e.timestamp.hour < 12]
    evening_entries = [e for e in entries if 18 <= e.timestamp.hour < 23]

    # US-22: Carb-aware suggestions
    entries_with_carbs = [e for e in entries if e.carbs_grams is not None]
    if len(entries_with_carbs) < len(entries) * 0.3:  # Less than 30% tracking
        return "🥖 Try tracking carbs more consistently. It really helps identify patterns!"

    # Check for breakfast skipping
    if len(morning_entries) < len(entries) * 0.2:
        return "💡 Try logging breakfast readings more consistently. Morning data helps spot patterns!"

    # Check for late-night highs with high carbs
    if evening_entries:
        evening_avg = sum(e.blood_glucose for e in evening_entries) / len(evening_entries)
        evening_with_carbs = [e for e in evening_entries if e.carbs_grams is not None]
        if evening_with_carbs:
            evening_avg_carbs = sum(e.carbs_grams for e in evening_with_carbs) / len(evening_with_carbs)
            if evening_avg > GLUCOSE_HIGH_THRESHOLD and evening_avg_carbs > 70:
                return "🌙 High carb dinners might be causing evening spikes. Try smaller portions or earlier timing."

    # Check for mood patterns with highs
    stressed_highs = [e for e in entries if e.mood == 'stressed' and e.blood_glucose > GLUCOSE_HIGH_THRESHOLD]
    if len(stressed_highs) >= 3:
        return "💙 Stress might be affecting your glucose. Try some deep breathing when levels spike!"

    # Default encouraging message
    return "⭐ You're building great habits! Keep logging to unlock more personalized insights."


# ============================================================================
# US-21: EXPORT DATA PREPARATION
# ============================================================================

def prepare_export_data(entries: List[LogEntry], days: int = 30) -> Dict:
    """
    Prepare comprehensive data for PDF and CSV exports.

    US-21: Doctor-Ready Export

    Args:
        entries: List of LogEntry objects
        days: Number of days covered in the report

    Returns:
        Dictionary with all data needed for exports
    """
    if not entries:
        return {'status': 'no_data'}

    # Calculate all advanced metrics
    metrics = calculate_advanced_metrics(entries)

    # Organize entries by date for daily summaries
    daily_data = defaultdict(list)
    for entry in entries:
        date_key = entry.timestamp.date()
        daily_data[date_key].append(entry)

    # Calculate daily statistics
    daily_summaries = []
    for date, day_entries in sorted(daily_data.items()):
        glucose_vals = [e.blood_glucose for e in day_entries]
        carb_vals = [e.carbs_grams for e in day_entries if e.carbs_grams is not None]

        daily_summaries.append({
            'date': date,
            'readings': len(day_entries),
            'avg_glucose': round(sum(glucose_vals) / len(glucose_vals), 1),
            'min_glucose': round(min(glucose_vals), 1),
            'max_glucose': round(max(glucose_vals), 1),
            'total_carbs': sum(carb_vals) if carb_vals else None,
            'hypo_events': len([g for g in glucose_vals if g < GLUCOSE_LOW_THRESHOLD]),
            'hyper_events': len([g for g in glucose_vals if g > GLUCOSE_TARGET_MAX])
        })

    return {
        'status': 'success',
        'period_days': days,
        'date_range': {
            'start': min(e.timestamp.date() for e in entries),
            'end': max(e.timestamp.date() for e in entries)
        },
        'metrics': metrics,
        'daily_summaries': daily_summaries,
        'entries': entries
    }