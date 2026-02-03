"""Business hours analysis for optimal contact timing.

This module analyzes business hours to determine:
- Best time to call/contact
- If business is currently open
- Weekly availability patterns
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
import re
from loguru import logger


class HoursAnalyzer:
    """
    Analyzes business hours to determine:
    - Best time to call/contact
    - If business is currently open
    - Weekly availability patterns
    """

    DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    DAY_ABBREVIATIONS = {
        'mon': 'monday', 'tue': 'tuesday', 'wed': 'wednesday',
        'thu': 'thursday', 'fri': 'friday', 'sat': 'saturday', 'sun': 'sunday'
    }

    def __init__(self, timezone_offset: int = 0):
        """
        Initialize the analyzer.

        Args:
            timezone_offset: Hours offset from UTC (e.g., +5.5 for IST)
        """
        self.timezone_offset = timezone_offset

    def parse_hours_string(self, hours_str: str) -> Optional[Tuple[time, time]]:
        """
        Parse hours string like "9:00 AM - 5:00 PM" into time objects.
        Returns (open_time, close_time) or None if closed.
        """
        if not hours_str:
            return None

        hours_str = hours_str.lower().strip()

        # Handle closed variations
        closed_patterns = ['closed', 'fermé', 'cerrado', 'geschlossen', 'chiuso', 'fechado', 'n/a', '-']
        if hours_str in closed_patterns or hours_str.startswith('closed'):
            return None

        # Handle 24 hours variations
        if '24' in hours_str or 'open 24' in hours_str or 'always open' in hours_str:
            return (time(0, 0), time(23, 59))

        # Try different parsing patterns
        patterns = [
            # "9:00 AM - 5:00 PM" or "9:00AM-5:00PM"
            r'(\d{1,2}):(\d{2})\s*(am|pm)?\s*[-–—to]+\s*(\d{1,2}):(\d{2})\s*(am|pm)?',
            # "9 AM - 5 PM" or "9AM-5PM"
            r'(\d{1,2})\s*(am|pm)\s*[-–—to]+\s*(\d{1,2})\s*(am|pm)',
            # "9:00 - 17:00" (24 hour format)
            r'(\d{1,2}):(\d{2})\s*[-–—to]+\s*(\d{1,2}):(\d{2})',
            # "9 - 5" simple format
            r'(\d{1,2})\s*[-–—to]+\s*(\d{1,2})',
        ]

        for i, pattern in enumerate(patterns):
            match = re.search(pattern, hours_str, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if i == 0:  # Full format with optional AM/PM
                        open_time = self._parse_time_components(
                            int(groups[0]), int(groups[1]), groups[2]
                        )
                        close_time = self._parse_time_components(
                            int(groups[3]), int(groups[4]), groups[5]
                        )
                    elif i == 1:  # Hour only with AM/PM
                        open_time = self._parse_time_components(
                            int(groups[0]), 0, groups[1]
                        )
                        close_time = self._parse_time_components(
                            int(groups[2]), 0, groups[3]
                        )
                    elif i == 2:  # 24-hour format
                        open_time = time(int(groups[0]) % 24, int(groups[1]))
                        close_time = time(int(groups[2]) % 24, int(groups[3]))
                    else:  # Simple format - assume AM for open, PM for close
                        open_hour = int(groups[0])
                        close_hour = int(groups[1])
                        # Heuristic: if open < 12 and close < 12 and close > open, both AM
                        # If close <= open or both small numbers, assume close is PM
                        if close_hour <= open_hour and close_hour < 12:
                            close_hour += 12
                        open_time = time(open_hour, 0)
                        close_time = time(close_hour, 0)

                    return (open_time, close_time)
                except (ValueError, TypeError) as e:
                    logger.debug(f"Error parsing time '{hours_str}': {e}")
                    continue

        return None

    def _parse_time_components(self, hour: int, minute: int, period: Optional[str]) -> time:
        """Parse time components into time object."""
        if period:
            period = period.lower()
            if period == 'pm' and hour != 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

        return time(hour % 24, minute)

    def analyze_hours(self, hours_data: Dict[str, str]) -> Dict:
        """
        Analyze business hours from dict like:
        {'monday': '9:00 AM - 5:00 PM', 'tuesday': '...', ...}

        Can also accept:
        {'hours_monday': '9:00 AM - 5:00 PM', ...}

        Returns analysis with best contact times, patterns, etc.
        """
        result = {
            'is_open_now': False,
            'best_call_times': [],
            'total_hours_per_week': 0,
            'open_days': [],
            'closed_days': [],
            'opening_pattern': 'unknown',  # regular, extended, limited, 24/7
            'earliest_opening': None,
            'latest_closing': None,
            'weekend_hours': False,
            'parsed_hours': {}
        }

        if not hours_data:
            return result

        parsed_hours = {}
        total_minutes = 0

        for day in self.DAYS:
            # Try different key formats
            hours_str = None
            for key_format in [day, f'hours_{day}', day[:3], day.capitalize()]:
                if key_format in hours_data:
                    hours_str = hours_data[key_format]
                    break

            times = self.parse_hours_string(hours_str) if hours_str else None
            parsed_hours[day] = times

            if times:
                result['open_days'].append(day.capitalize())

                # Calculate hours for this day
                open_time, close_time = times
                minutes = self._calculate_minutes(open_time, close_time)
                total_minutes += minutes

                # Track earliest/latest
                open_str = open_time.strftime('%I:%M %p').lstrip('0')
                close_str = close_time.strftime('%I:%M %p').lstrip('0')

                if not result['earliest_opening'] or open_time < self._str_to_time(result['earliest_opening']):
                    result['earliest_opening'] = open_str
                if not result['latest_closing'] or close_time > self._str_to_time(result['latest_closing']):
                    result['latest_closing'] = close_str

                result['parsed_hours'][day] = {
                    'open': open_str,
                    'close': close_str,
                    'hours': round(minutes / 60, 1)
                }
            else:
                result['closed_days'].append(day.capitalize())

        # Calculate total hours
        result['total_hours_per_week'] = round(total_minutes / 60, 1)

        # Check weekend hours
        if parsed_hours.get('saturday') or parsed_hours.get('sunday'):
            result['weekend_hours'] = True

        # Determine pattern
        if result['total_hours_per_week'] >= 140:  # ~20 hours/day
            result['opening_pattern'] = '24/7'
        elif result['total_hours_per_week'] >= 70:  # ~10 hours/day, 7 days
            result['opening_pattern'] = 'extended'
        elif result['total_hours_per_week'] >= 40:  # Standard work week
            result['opening_pattern'] = 'regular'
        elif result['total_hours_per_week'] > 0:
            result['opening_pattern'] = 'limited'

        # Generate best call times
        result['best_call_times'] = self._calculate_best_call_times(parsed_hours)

        # Check if currently open
        result['is_open_now'] = self._is_currently_open(parsed_hours)

        return result

    def _calculate_minutes(self, open_time: time, close_time: time) -> int:
        """Calculate minutes between open and close time."""
        open_minutes = open_time.hour * 60 + open_time.minute
        close_minutes = close_time.hour * 60 + close_time.minute

        if close_minutes > open_minutes:
            return close_minutes - open_minutes
        else:
            # Crosses midnight
            return (24 * 60 - open_minutes) + close_minutes

    def _str_to_time(self, time_str: str) -> time:
        """Convert time string to time object."""
        try:
            # Try 12-hour format
            return datetime.strptime(time_str.strip(), '%I:%M %p').time()
        except ValueError:
            try:
                # Try 24-hour format
                return datetime.strptime(time_str.strip(), '%H:%M').time()
            except ValueError:
                return time(0, 0)

    def _calculate_best_call_times(self, parsed_hours: Dict) -> List[Dict]:
        """Calculate the best times to call based on typical business patterns."""
        best_times = []

        # Prioritize mid-week days (Tuesday, Wednesday, Thursday)
        priority_days = ['tuesday', 'wednesday', 'thursday', 'monday', 'friday']

        for day in priority_days:
            times = parsed_hours.get(day)
            if times:
                open_time, close_time = times

                # Mid-morning (10-11 AM) - after opening rush
                mid_morning = time(10, 30)
                if open_time <= mid_morning and close_time > time(11, 0):
                    best_times.append({
                        'day': day.capitalize(),
                        'time': '10:30 AM',
                        'window': '10:00 AM - 11:30 AM',
                        'reason': 'Mid-morning, settled after opening rush',
                        'priority': 1
                    })

                # Early afternoon (2-3 PM) - after lunch
                afternoon = time(14, 30)
                if open_time <= afternoon and close_time > time(15, 0):
                    best_times.append({
                        'day': day.capitalize(),
                        'time': '2:30 PM',
                        'window': '2:00 PM - 3:30 PM',
                        'reason': 'Early afternoon, after lunch rush',
                        'priority': 2
                    })

        # Sort by priority and return top 3
        best_times.sort(key=lambda x: x['priority'])
        return best_times[:3]

    def _is_currently_open(self, parsed_hours: Dict) -> bool:
        """Check if business is currently open."""
        now = datetime.now()
        day_name = self.DAYS[now.weekday()]
        current_time = now.time()

        times = parsed_hours.get(day_name)
        if times:
            open_time, close_time = times
            if close_time > open_time:
                return open_time <= current_time <= close_time
            else:
                # Crosses midnight
                return current_time >= open_time or current_time <= close_time

        return False

    def get_next_open_time(self, hours_data: Dict[str, str]) -> Optional[Dict]:
        """
        Get the next time the business will be open.

        Returns dict with 'day', 'time', 'in_hours' or None if unknown.
        """
        analysis = self.analyze_hours(hours_data)

        if analysis['is_open_now']:
            return {'status': 'open_now', 'day': None, 'time': None, 'in_hours': 0}

        now = datetime.now()
        current_day_idx = now.weekday()

        # Check each day starting from tomorrow
        for days_ahead in range(1, 8):
            check_day_idx = (current_day_idx + days_ahead) % 7
            day_name = self.DAYS[check_day_idx]

            if day_name.capitalize() in analysis['open_days']:
                open_time = analysis['parsed_hours'].get(day_name, {}).get('open')
                if open_time:
                    return {
                        'status': 'closed',
                        'day': day_name.capitalize(),
                        'time': open_time,
                        'in_days': days_ahead
                    }

        return None


# Convenience function
def analyze_business_hours(hours_dict: Dict[str, str]) -> Dict:
    """
    Analyze business hours and return insights.

    Args:
        hours_dict: Dictionary with day names as keys and hours strings as values
                   e.g., {'monday': '9:00 AM - 5:00 PM', ...}

    Returns:
        Dict with analysis results including best call times, total hours, etc.
    """
    analyzer = HoursAnalyzer()
    return analyzer.analyze_hours(hours_dict)


def get_best_contact_times(hours_dict: Dict[str, str]) -> List[Dict]:
    """
    Get the best times to contact a business.

    Args:
        hours_dict: Dictionary with day names as keys and hours strings as values

    Returns:
        List of best contact times with day, time, and reason
    """
    analyzer = HoursAnalyzer()
    analysis = analyzer.analyze_hours(hours_dict)
    return analysis.get('best_call_times', [])


def is_business_open_now(hours_dict: Dict[str, str]) -> bool:
    """
    Check if a business is currently open.

    Args:
        hours_dict: Dictionary with day names as keys and hours strings as values

    Returns:
        True if currently open, False otherwise
    """
    analyzer = HoursAnalyzer()
    analysis = analyzer.analyze_hours(hours_dict)
    return analysis.get('is_open_now', False)


# Alias for backward compatibility
BusinessHoursAnalyzer = HoursAnalyzer
