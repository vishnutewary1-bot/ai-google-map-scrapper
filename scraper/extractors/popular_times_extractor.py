"""Popular Times data extraction module for Google Maps."""
import re
from typing import Dict, List, Optional
from loguru import logger

try:
    from playwright.sync_api import Page
except ImportError:
    Page = None


class PopularTimesExtractor:
    """Extract Popular Times and Live Occupancy data from Google Maps."""

    DAYS_OF_WEEK = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    HOURS = list(range(6, 24)) + list(range(0, 6))  # 6 AM to 5 AM next day

    def extract_popular_times(self, page: Page) -> Dict:
        """
        Extract Popular Times data from a Google Maps business listing.

        Args:
            page: Playwright page object (on business details page)

        Returns:
            Dict with popular times data by day and hour
        """
        result = {
            "has_popular_times": False,
            "live_busyness": None,
            "live_busyness_text": None,
            "typical_time_spent": None,
            "popular_times": {},  # day -> hour -> busyness %
            "busiest_day": None,
            "busiest_hour": None,
            "quietest_day": None,
            "quietest_hour": None
        }

        try:
            import time
            # Check if Popular Times section exists
            popular_times_section = page.query_selector(
                'div[aria-label*="Popular times"], div[class*="popular-times"]'
            )

            if not popular_times_section:
                # Try alternative selectors
                popular_times_section = page.query_selector(
                    'div[jsaction*="pane.popularTimes"]'
                )

            if not popular_times_section:
                logger.debug("No Popular Times section found")
                return result

            result["has_popular_times"] = True

            # Extract live busyness if available
            self._extract_live_busyness(page, result)

            # Extract typical time spent
            self._extract_time_spent(page, result)

            # Extract hourly data for each day
            self._extract_hourly_data(page, result)

            # Calculate busiest/quietest times
            self._calculate_extremes(result)

        except Exception as e:
            logger.error(f"Error extracting Popular Times: {e}")

        return result

    def _extract_live_busyness(self, page: Page, result: Dict):
        """Extract current live busyness."""
        try:
            # Live busyness indicator
            live_selectors = [
                'div[class*="live"] span',
                'span[aria-label*="busy"]',
                'div[class*="current-popularity"]',
                'span:has-text("Usually")',
                'span:has-text("busy")'
            ]

            for selector in live_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        text = element.inner_text()

                        # Parse busyness level
                        if "not too busy" in text.lower():
                            result["live_busyness"] = 25
                            result["live_busyness_text"] = "Not too busy"
                        elif "not busy" in text.lower():
                            result["live_busyness"] = 10
                            result["live_busyness_text"] = "Not busy"
                        elif "a little busy" in text.lower():
                            result["live_busyness"] = 50
                            result["live_busyness_text"] = "A little busy"
                        elif "as busy as it gets" in text.lower():
                            result["live_busyness"] = 100
                            result["live_busyness_text"] = "As busy as it gets"
                        elif "usually busy" in text.lower():
                            result["live_busyness"] = 75
                            result["live_busyness_text"] = "Usually busy"
                        elif "busy" in text.lower():
                            result["live_busyness"] = 75
                            result["live_busyness_text"] = "Busy"

                        break
                except:
                    continue

            # Try to extract percentage from aria-label
            busyness_bar = page.query_selector('div[role="img"][aria-label*="%"]')
            if busyness_bar:
                aria = busyness_bar.get_attribute("aria-label")
                match = re.search(r"(\d+)\s*%", aria)
                if match:
                    result["live_busyness"] = int(match.group(1))

        except Exception as e:
            logger.debug(f"Error extracting live busyness: {e}")

    def _extract_time_spent(self, page: Page, result: Dict):
        """Extract typical time spent at location."""
        try:
            time_spent_selectors = [
                'span:has-text("People typically spend")',
                'div[class*="time-spent"]',
                'span:has-text("min")'
            ]

            for selector in time_spent_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        text = element.inner_text()

                        # Parse time spent
                        # Examples: "People typically spend 15-30 min", "1-2 hr"
                        time_match = re.search(
                            r"(\d+(?:-\d+)?)\s*(min|hr|hour)",
                            text,
                            re.IGNORECASE
                        )
                        if time_match:
                            result["typical_time_spent"] = text.strip()
                            break
                except:
                    continue

        except Exception as e:
            logger.debug(f"Error extracting time spent: {e}")

    def _extract_hourly_data(self, page: Page, result: Dict):
        """Extract hourly busyness data for each day."""
        try:
            import time as time_module
            # Initialize data structure
            for day in self.DAYS_OF_WEEK:
                result["popular_times"][day] = {}

            # Try to find day tabs/buttons
            day_buttons = page.query_selector_all(
                'button[aria-label*="day"], div[role="tab"]'
            )

            if day_buttons:
                # Click through each day to get data
                for i, day_button in enumerate(day_buttons):
                    if i >= len(self.DAYS_OF_WEEK):
                        break

                    day_name = self.DAYS_OF_WEEK[i]

                    try:
                        day_button.click()
                        time_module.sleep(0.5)

                        # Extract bars for this day
                        bars = page.query_selector_all(
                            'div[role="img"][aria-label*="%"], div[class*="bar"]'
                        )

                        for j, bar in enumerate(bars):
                            if j >= 24:
                                break

                            try:
                                aria = bar.get_attribute("aria-label")
                                if aria:
                                    # Parse "X% busy at Y AM/PM"
                                    match = re.search(
                                        r"(\d+)\s*%.*?(\d+)\s*(AM|PM)",
                                        aria,
                                        re.IGNORECASE
                                    )
                                    if match:
                                        percent = int(match.group(1))
                                        hour = int(match.group(2))
                                        period = match.group(3).upper()

                                        # Convert to 24-hour format
                                        if period == "PM" and hour != 12:
                                            hour += 12
                                        elif period == "AM" and hour == 12:
                                            hour = 0

                                        result["popular_times"][day_name][hour] = percent
                            except:
                                continue

                    except:
                        continue

            else:
                # Alternative: Extract all visible bars
                self._extract_visible_bars(page, result)

        except Exception as e:
            logger.debug(f"Error extracting hourly data: {e}")

    def _extract_visible_bars(self, page: Page, result: Dict):
        """Extract busyness from visible bar graphs."""
        try:
            # Find all bar elements
            bars = page.query_selector_all(
                'div[class*="bar"], div[style*="height"]'
            )

            # Try to determine current day
            current_day = page.evaluate('''
                () => {
                    const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
                    return days[new Date().getDay()];
                }
            ''')

            if not result["popular_times"].get(current_day):
                result["popular_times"][current_day] = {}

            for i, bar in enumerate(bars[:24]):
                try:
                    # Get height percentage from style
                    style = bar.get_attribute("style")
                    if style:
                        height_match = re.search(r"height:\s*(\d+)", style)
                        if height_match:
                            # Normalize to percentage (assuming max height = 100%)
                            height = int(height_match.group(1))
                            result["popular_times"][current_day][6 + i] = min(height, 100)

                    # Try aria-label
                    aria = bar.get_attribute("aria-label")
                    if aria:
                        percent_match = re.search(r"(\d+)\s*%", aria)
                        if percent_match:
                            result["popular_times"][current_day][6 + i] = int(percent_match.group(1))

                except:
                    continue

        except Exception as e:
            logger.debug(f"Error extracting visible bars: {e}")

    def _calculate_extremes(self, result: Dict):
        """Calculate busiest and quietest times."""
        try:
            max_busyness = 0
            min_busyness = 100
            busiest_day = None
            busiest_hour = None
            quietest_day = None
            quietest_hour = None

            for day, hours in result["popular_times"].items():
                for hour, busyness in hours.items():
                    if busyness > max_busyness:
                        max_busyness = busyness
                        busiest_day = day
                        busiest_hour = hour

                    if busyness < min_busyness and busyness > 0:
                        min_busyness = busyness
                        quietest_day = day
                        quietest_hour = hour

            if busiest_hour is not None:
                result["busiest_day"] = busiest_day
                result["busiest_hour"] = self._format_hour(busiest_hour)

            if quietest_hour is not None:
                result["quietest_day"] = quietest_day
                result["quietest_hour"] = self._format_hour(quietest_hour)

        except Exception as e:
            logger.debug(f"Error calculating extremes: {e}")

    def _format_hour(self, hour: int) -> str:
        """Format hour to readable string."""
        if hour == 0:
            return "12 AM"
        elif hour < 12:
            return f"{hour} AM"
        elif hour == 12:
            return "12 PM"
        else:
            return f"{hour - 12} PM"

    def get_best_times_to_visit(self, page: Page) -> Dict:
        """
        Get recommended best times to visit based on Popular Times.

        Returns:
            Dict with recommendations
        """
        popular_times = self.extract_popular_times(page)

        recommendations = {
            "best_times": [],
            "avoid_times": [],
            "summary": None
        }

        if not popular_times["has_popular_times"]:
            recommendations["summary"] = "Popular times data not available"
            return recommendations

        # Find times with low busyness
        for day, hours in popular_times["popular_times"].items():
            for hour, busyness in hours.items():
                if busyness <= 30:
                    recommendations["best_times"].append({
                        "day": day,
                        "time": self._format_hour(hour),
                        "busyness": busyness
                    })
                elif busyness >= 80:
                    recommendations["avoid_times"].append({
                        "day": day,
                        "time": self._format_hour(hour),
                        "busyness": busyness
                    })

        # Sort recommendations
        recommendations["best_times"].sort(key=lambda x: x["busyness"])
        recommendations["avoid_times"].sort(key=lambda x: -x["busyness"])

        # Limit to top 5
        recommendations["best_times"] = recommendations["best_times"][:5]
        recommendations["avoid_times"] = recommendations["avoid_times"][:5]

        # Generate summary
        if popular_times["busiest_day"] and popular_times["quietest_day"]:
            recommendations["summary"] = (
                f"Busiest: {popular_times['busiest_day']} at {popular_times['busiest_hour']}. "
                f"Quietest: {popular_times['quietest_day']} at {popular_times['quietest_hour']}."
            )

        return recommendations


# Singleton instance
_popular_times_extractor = None

def get_popular_times_extractor() -> PopularTimesExtractor:
    """Get or create the Popular Times extractor instance."""
    global _popular_times_extractor
    if _popular_times_extractor is None:
        _popular_times_extractor = PopularTimesExtractor()
    return _popular_times_extractor
