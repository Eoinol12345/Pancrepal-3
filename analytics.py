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
GLUCOSE_LOW_THRESHOLD = 3.9  # Hypo threshold (below 3.9 = low)
GLUCOSE_VERY_LOW_THRESHOLD = 3.3


# ============================================================================
# US-23: ADVANCED ANALYTICS & METRICS (unchanged from Iteration 5)
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
    """
    if not entries:
        return {
            'status': 'no_data',
            'message': 'No data available for analysis'
        }

    glucose_values = [e.blood_glucose for e in entries]
    total_readings = len(glucose_values)

    mean_glucose = statistics.mean(glucose_values)

    if len(glucose_values) > 1:
        std_dev = statistics.stdev(glucose_values)
        coefficient_of_variation = (std_dev / mean_glucose) * 100 if mean_glucose > 0 else 0
    else:
        std_dev = 0
        coefficient_of_variation = 0

    in_range = [g for g in glucose_values if GLUCOSE_TARGET_MIN <= g <= GLUCOSE_TARGET_MAX]
    time_in_range_pct = (len(in_range) / total_readings) * 100

    hypos = [g for g in glucose_values if g < GLUCOSE_LOW_THRESHOLD]
    hypo_frequency = len(hypos)
    hypo_percentage = (hypo_frequency / total_readings) * 100

    hypers = [g for g in glucose_values if g > GLUCOSE_TARGET_MAX]
    hyper_frequency = len(hypers)
    hyper_percentage = (hyper_frequency / total_readings) * 100

    entries_with_carbs = [e for e in entries if e.carbs_grams is not None]
    if entries_with_carbs:
        total_carbs = sum(e.carbs_grams for e in entries_with_carbs)
        avg_carbs_per_entry = total_carbs / len(entries_with_carbs)
        unique_dates = set(e.timestamp.date() for e in entries_with_carbs)
        avg_daily_carbs = total_carbs / len(unique_dates) if unique_dates else 0
    else:
        avg_carbs_per_entry = None
        avg_daily_carbs = None
        total_carbs = 0

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
        'mean_glucose': round(mean_glucose, 1),
        'std_dev': round(std_dev, 1),
        'coefficient_of_variation': round(coefficient_of_variation, 1),
        'time_in_range_pct': round(time_in_range_pct, 1),
        'time_below_range_pct': round(hypo_percentage, 1),
        'time_above_range_pct': round(hyper_percentage, 1),
        'total_readings': total_readings,
        'hypo_events': hypo_frequency,
        'hyper_events': hyper_frequency,
        'avg_carbs_per_entry': round(avg_carbs_per_entry, 1) if avg_carbs_per_entry else None,
        'avg_daily_carbs': round(avg_daily_carbs, 1) if avg_daily_carbs else None,
        'total_carbs': total_carbs,
        'entries_with_carbs': len(entries_with_carbs)
    }


def get_metric_explanation(metric_name: str) -> Dict:
    """Get user-friendly explanation for each metric."""
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
            'description': "Your mean blood glucose level. Useful but doesn't show the full picture - variability matters too!",
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
# EXISTING ANALYTICS FUNCTIONS (unchanged from Iteration 5)
# ============================================================================

def analyze_weekly_trend(entries: List[LogEntry]) -> Dict:
    """Analyze glucose patterns over the past week."""
    if not entries:
        return {
            'status': 'no_data',
            'message': "Start logging to see your personalized insights!",
            'icon': '📊'
        }

    metrics = calculate_advanced_metrics(entries)

    if metrics['status'] == 'excellent':
        message = '🌟 Amazing work this week! Your glucose levels show great consistency.'
        icon = '🎉'
    elif metrics['status'] == 'good':
        message = "💪 You're doing well! Keep up the steady progress."
        icon = '✨'
    else:
        message = "🤗 We see you're working on it. Every log helps you understand patterns better!"
        icon = '💙'

    return {
        'status': metrics['status'],
        'message': message,
        'icon': icon,
        'time_in_range': metrics['time_in_range_pct'],
        'avg_glucose': metrics['mean_glucose'],
        'consistency': 100 - min(metrics['coefficient_of_variation'], 100)
    }


def identify_recurring_patterns(entries: List[LogEntry]) -> List[Dict]:
    """Identify recurring high or low glucose patterns by time and meal type."""
    if len(entries) < 3:
        return []

    patterns = []

    meal_groups = defaultdict(list)
    for entry in entries:
        meal_groups[entry.meal_type].append(entry)

    for meal_type, meal_entries in meal_groups.items():
        if len(meal_entries) < 2:
            continue

        glucose_values = [e.blood_glucose for e in meal_entries]
        avg = sum(glucose_values) / len(glucose_values)
        high_count = sum(1 for g in glucose_values if g > GLUCOSE_HIGH_THRESHOLD)
        low_count = sum(1 for g in glucose_values if g < GLUCOSE_VERY_LOW_THRESHOLD)

        entries_with_carbs = [e for e in meal_entries if e.carbs_grams is not None]
        if len(entries_with_carbs) >= 2:
            avg_carbs = sum(e.carbs_grams for e in entries_with_carbs) / len(entries_with_carbs)
            if avg_carbs > 60 and avg > GLUCOSE_HIGH_THRESHOLD:
                patterns.append({
                    'type': 'high_carb_high_glucose',
                    'context': meal_type,
                    'message': f'🥖 High carb {meal_type}s (avg {round(avg_carbs)}g) often lead to high readings. Consider portion sizes or timing.',
                    'severity': 'info'
                })
                continue

        if high_count >= len(glucose_values) * 0.6:
            patterns.append({
                'type': 'recurring_high',
                'context': meal_type,
                'message': f'📈 You often see higher readings after {meal_type}. Consider checking portion sizes or insulin timing.',
                'severity': 'info'
            })
        elif low_count >= len(glucose_values) * 0.5:
            patterns.append({
                'type': 'recurring_low',
                'context': meal_type,
                'message': f"⚠️ You've had some lows around {meal_type} time. Let's keep an eye on this pattern together.",
                'severity': 'warning'
            })
        elif GLUCOSE_TARGET_MIN <= avg <= GLUCOSE_TARGET_MAX:
            patterns.append({
                'type': 'in_range',
                'context': meal_type,
                'message': f'✅ Great job keeping {meal_type} readings in range!',
                'severity': 'success'
            })

    return patterns[:3]


def generate_weekly_suggestion(entries: List[LogEntry]) -> Optional[str]:
    """Generate a proactive, actionable suggestion based on weekly patterns."""
    if len(entries) < 5:
        return None

    morning_entries = [e for e in entries if 5 <= e.timestamp.hour < 12]
    evening_entries = [e for e in entries if 18 <= e.timestamp.hour < 23]

    entries_with_carbs = [e for e in entries if e.carbs_grams is not None]
    if len(entries_with_carbs) < len(entries) * 0.3:
        return "🥖 Try tracking carbs more consistently. It really helps identify patterns!"

    if len(morning_entries) < len(entries) * 0.2:
        return "💡 Try logging breakfast readings more consistently. Morning data helps spot patterns!"

    if evening_entries:
        evening_avg = sum(e.blood_glucose for e in evening_entries) / len(evening_entries)
        evening_with_carbs = [e for e in evening_entries if e.carbs_grams is not None]
        if evening_with_carbs:
            evening_avg_carbs = sum(e.carbs_grams for e in evening_with_carbs) / len(evening_with_carbs)
            if evening_avg > GLUCOSE_HIGH_THRESHOLD and evening_avg_carbs > 70:
                return "🌙 High carb dinners might be causing evening spikes. Try smaller portions or earlier timing."

    stressed_highs = [e for e in entries if e.mood == 'stressed' and e.blood_glucose > GLUCOSE_HIGH_THRESHOLD]
    if len(stressed_highs) >= 3:
        return "💙 Stress might be affecting your glucose. Try some deep breathing when levels spike!"

    return "⭐ You're building great habits! Keep logging to unlock more personalized insights."


# ============================================================================
# US-21: EXPORT DATA PREPARATION (unchanged from Iteration 5)
# ============================================================================

def prepare_export_data(entries: List[LogEntry], days: int = 30) -> Dict:
    """Prepare comprehensive data for CSV exports."""
    if not entries:
        return {'status': 'no_data'}

    metrics = calculate_advanced_metrics(entries)

    daily_data = defaultdict(list)
    for entry in entries:
        date_key = entry.timestamp.date()
        daily_data[date_key].append(entry)

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


# ============================================================================
# US-27: TIME-OF-DAY ANALYSIS
# ============================================================================

def analyze_time_of_day(entries: List[LogEntry]) -> Dict:
    """
    Categorise entries into morning, afternoon, evening, and night periods,
    then compute key metrics for each period.

    US-27: Time-of-Day Analysis
    - Automatic categorisation by hour of day
    - Per-period TIR, hypo/hyper frequency, avg glucose, avg carbs
    - Used by the Insight Engine for deeper pattern detection

    Time periods:
      Morning:   05:00 – 11:59
      Afternoon: 12:00 – 17:59
      Evening:   18:00 – 22:59
      Night:     23:00 – 04:59

    Args:
        entries: List of LogEntry objects

    Returns:
        Dictionary keyed by period name, each containing metrics
    """
    period_definitions = {
        'morning':   {'label': 'Morning',   'time_range': '5am – 12pm', 'icon': '🌅'},
        'afternoon': {'label': 'Afternoon', 'time_range': '12pm – 6pm', 'icon': '☀️'},
        'evening':   {'label': 'Evening',   'time_range': '6pm – 11pm', 'icon': '🌆'},
        'night':     {'label': 'Night',     'time_range': '11pm – 5am', 'icon': '🌙'},
    }

    # Bucket entries into their period
    bucketed: Dict[str, list] = {k: [] for k in period_definitions}
    for entry in entries:
        hour = entry.timestamp.hour
        if 5 <= hour < 12:
            bucketed['morning'].append(entry)
        elif 12 <= hour < 18:
            bucketed['afternoon'].append(entry)
        elif 18 <= hour < 23:
            bucketed['evening'].append(entry)
        else:
            bucketed['night'].append(entry)

    results = {}
    for period_key, meta in period_definitions.items():
        period_entries = bucketed[period_key]
        base = {
            'label': meta['label'],
            'time_range': meta['time_range'],
            'icon': meta['icon'],
            'count': len(period_entries),
            'avg_glucose': None,
            'time_in_range_pct': None,
            'hypo_pct': None,
            'hyper_pct': None,
            'avg_carbs': None,
            'has_data': False,
        }

        if not period_entries:
            results[period_key] = base
            continue

        glucose_vals = [e.blood_glucose for e in period_entries]
        n = len(glucose_vals)

        in_range  = [g for g in glucose_vals if GLUCOSE_TARGET_MIN <= g <= GLUCOSE_TARGET_MAX]
        hypos     = [g for g in glucose_vals if g < GLUCOSE_LOW_THRESHOLD]
        hypers    = [g for g in glucose_vals if g > GLUCOSE_TARGET_MAX]

        carb_entries = [e for e in period_entries if e.carbs_grams is not None]
        avg_carbs = (
            round(sum(e.carbs_grams for e in carb_entries) / len(carb_entries))
            if carb_entries else None
        )

        results[period_key] = {
            **base,
            'has_data': True,
            'avg_glucose': round(sum(glucose_vals) / n, 1),
            'time_in_range_pct': round((len(in_range) / n) * 100, 1),
            'hypo_pct': round((len(hypos) / n) * 100, 1),
            'hyper_pct': round((len(hypers) / n) * 100, 1),
            'avg_carbs': avg_carbs,
        }

    return results


# ============================================================================
# US-25: INSIGHT ENGINE (Pattern Detection)
# ============================================================================

def generate_insights(entries: List[LogEntry], time_analysis: Dict) -> List[Dict]:
    """
    Rule-based pattern detection that surfaces meaningful trends in
    plain, non-medical language.

    US-25: Insight Engine
    - Checks 8 distinct rule categories
    - Combines time-of-day data (US-27) with carb, mood, and meal patterns
    - Returns up to 5 insights sorted by severity (warnings first)
    - Caller should always display the educational disclaimer alongside insights

    Severity levels:
      'warning'  – something that may benefit from attention
      'info'     – neutral observation or correlating pattern
      'success'  – positive reinforcement

    Args:
        entries: List of LogEntry objects (recommend >= 7 for meaningful output)
        time_analysis: Dict returned by analyze_time_of_day()

    Returns:
        List of insight dictionaries (max 5), empty list if too few entries
    """
    if len(entries) < 7:
        return []

    insights = []

    # ------------------------------------------------------------------
    # Rule 1 – Worst time-of-day period
    # ------------------------------------------------------------------
    periods_with_data = {k: v for k, v in time_analysis.items() if v['has_data'] and v['count'] >= 3}

    if periods_with_data:
        worst = min(periods_with_data.values(), key=lambda x: x['time_in_range_pct'])
        best  = max(periods_with_data.values(), key=lambda x: x['time_in_range_pct'])

        if worst['time_in_range_pct'] < 55:
            insights.append({
                'type': 'worst_period',
                'severity': 'warning',
                'icon': worst['icon'],
                'title': f"{worst['label']} Readings Need Attention",
                'message': (
                    f"Your {worst['label'].lower()} readings ({worst['time_range']}) are in the target "
                    f"range only {worst['time_in_range_pct']}% of the time. "
                    f"This is your most challenging part of the day."
                ),
                'action': (
                    f"Try noting what you eat and do during the {worst['label'].lower()} "
                    f"to help spot what might be causing this."
                ),
            })

        # ------------------------------------------------------------------
        # Rule 2 – Best time-of-day period (positive reinforcement)
        # ------------------------------------------------------------------
        if best['time_in_range_pct'] >= 70 and best != worst:
            insights.append({
                'type': 'best_period',
                'severity': 'success',
                'icon': best['icon'],
                'title': f"Strong {best['label']} Control",
                'message': (
                    f"You're in range {best['time_in_range_pct']}% of the time during the "
                    f"{best['label'].lower()} ({best['time_range']}). "
                    f"Whatever routine you have then is clearly working!"
                ),
                'action': "Keep doing what you're doing during this time.",
            })

    # ------------------------------------------------------------------
    # Rule 3 – High-carb meal correlating with high glucose
    # ------------------------------------------------------------------
    high_carb_entries = [e for e in entries if e.carbs_grams is not None and e.carbs_grams > 60]
    if len(high_carb_entries) >= 3:
        spike_after_high_carb = [e for e in high_carb_entries if e.blood_glucose > GLUCOSE_TARGET_MAX]
        spike_rate = len(spike_after_high_carb) / len(high_carb_entries)
        if spike_rate > 0.55:
            insights.append({
                'type': 'carb_spike',
                'severity': 'info',
                'icon': '🥖',
                'title': 'High-Carb Meals May Cause Spikes',
                'message': (
                    f"When you log meals over 60g of carbs, your glucose is above target "
                    f"{round(spike_rate * 100)}% of the time. "
                    f"Larger portions seem to push your levels higher."
                ),
                'action': (
                    "Try splitting large carb meals into smaller portions, "
                    "or swap some carbs for protein or vegetables."
                ),
            })

    # ------------------------------------------------------------------
    # Rule 4 – Consistent post-meal highs for a specific meal type
    # ------------------------------------------------------------------
    meal_groups: Dict[str, list] = defaultdict(list)
    for entry in entries:
        meal_groups[entry.meal_type].append(entry.blood_glucose)

    for meal_type, glucose_vals in meal_groups.items():
        if meal_type == 'none' or len(glucose_vals) < 5:
            continue
        high_pct = len([g for g in glucose_vals if g > GLUCOSE_TARGET_MAX]) / len(glucose_vals)
        if high_pct >= 0.65:
            insights.append({
                'type': 'meal_pattern',
                'severity': 'warning',
                'icon': '📈',
                'title': f'Consistent Highs After {meal_type.capitalize()}',
                'message': (
                    f"Your readings logged around {meal_type} are above the target range "
                    f"{round(high_pct * 100)}% of the time. This is a repeating pattern."
                ),
                'action': (
                    f"Look at what you usually eat at {meal_type} "
                    f"and consider sharing this pattern with your diabetes team."
                ),
            })
            break  # Only flag the worst meal type to avoid noise

    # ------------------------------------------------------------------
    # Rule 5 – Frequent low glucose events
    # ------------------------------------------------------------------
    hypo_count = len([e for e in entries if e.blood_glucose < GLUCOSE_LOW_THRESHOLD])
    total = len(entries)
    hypo_pct = (hypo_count / total) * 100 if total > 0 else 0

    if hypo_pct >= 5 or hypo_count >= 5:
        insights.append({
            'type': 'hypo_frequency',
            'severity': 'warning',
            'icon': '⚠️',
            'title': 'Frequent Low Glucose Readings',
            'message': (
                f"You've had {hypo_count} readings below 3.9 mmol/L "
                f"({round(hypo_pct, 1)}% of your logs). "
                f"Frequent lows are worth reviewing with your care team."
            ),
            'action': (
                "Always treat lows promptly and note what happened beforehand. "
                "Bring this data to your next diabetes appointment."
            ),
        })

    # ------------------------------------------------------------------
    # Rule 6 – Night-time hypos
    # ------------------------------------------------------------------
    night_entries = time_analysis.get('night', {})
    if night_entries.get('has_data') and night_entries.get('hypo_pct', 0) >= 8:
        insights.append({
            'type': 'night_hypo',
            'severity': 'warning',
            'icon': '🌙',
            'title': 'Night-Time Lows Detected',
            'message': (
                f"Around {night_entries['hypo_pct']}% of your night-time readings "
                f"({night_entries['time_range']}) are below 3.9 mmol/L. "
                f"Night lows can go unnoticed and are important to address."
            ),
            'action': (
                "Consider a small snack before bed and discuss night-time patterns "
                "with your healthcare team."
            ),
        })

    # ------------------------------------------------------------------
    # Rule 7 – Stress correlating with elevated glucose
    # ------------------------------------------------------------------
    stressed_entries = [e for e in entries if e.mood == 'stressed']
    if len(stressed_entries) >= 3:
        stressed_avg = sum(e.blood_glucose for e in stressed_entries) / len(stressed_entries)
        overall_avg  = sum(e.blood_glucose for e in entries) / len(entries)
        if stressed_avg > overall_avg + 0.9:
            insights.append({
                'type': 'stress_correlation',
                'severity': 'info',
                'icon': '💙',
                'title': 'Stress and Glucose May Be Linked',
                'message': (
                    f"On days you log as 'stressed', your average glucose is "
                    f"{round(stressed_avg, 1)} mmol/L — "
                    f"{round(stressed_avg - overall_avg, 1)} mmol/L above your overall average "
                    f"of {round(overall_avg, 1)} mmol/L. "
                    f"Stress is a well-known glucose trigger."
                ),
                'action': (
                    "Short walks, breathing exercises, or even just a few minutes of "
                    "quiet can help lower stress-related spikes."
                ),
            })

    # ------------------------------------------------------------------
    # Rule 8 – Good logging consistency (positive reinforcement)
    # ------------------------------------------------------------------
    if len(entries) >= 14:
        unique_days = set(e.timestamp.date() for e in entries)
        period_days = max((max(unique_days) - min(unique_days)).days + 1, 1)
        logging_rate = len(unique_days) / period_days
        if logging_rate >= 0.80:
            insights.append({
                'type': 'consistency',
                'severity': 'success',
                'icon': '🌟',
                'title': 'Excellent Logging Consistency',
                'message': (
                    f"You've logged on {len(unique_days)} out of {period_days} days — "
                    f"a {round(logging_rate * 100)}% consistency rate. "
                    f"Regular logging is one of the most powerful things you can do."
                ),
                'action': (
                    "Keep it up! The more consistently you log, "
                    "the more reliable and useful these insights become."
                ),
            })

    # ------------------------------------------------------------------
    # Sort: warnings first, then info, then success; cap at 5
    # ------------------------------------------------------------------
    severity_order = {'warning': 0, 'info': 1, 'success': 2}
    insights.sort(key=lambda x: severity_order.get(x['severity'], 3))

    return insights[:5]
