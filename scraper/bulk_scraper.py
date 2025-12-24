"""Bulk scraping for multiple locations."""
import asyncio
from typing import List, Dict
from loguru import logger

from scraper.google_maps_scraper_v2 import EnhancedGoogleMapsScraper
from database import db_manager, ScrapeJob


class BulkLocationScraper:
    """Scrape same business category across multiple locations."""

    def __init__(self, use_proxies: bool = False):
        self.scraper = EnhancedGoogleMapsScraper(use_proxies=use_proxies)
        self.results_by_location = {}

    async def initialize(self):
        """Initialize scraper."""
        await self.scraper.initialize()

    async def scrape_multiple_locations(
        self,
        search_query: str,
        locations: List[str],
        max_results_per_location: int = 50,
        delay_between_locations: int = 300  # 5 minutes
    ) -> Dict[str, List[Dict]]:
        """
        Scrape same query across multiple locations.

        Args:
            search_query: Business category/query
            locations: List of location strings
            max_results_per_location: Max results per location
            delay_between_locations: Delay in seconds between locations

        Returns:
            Dictionary mapping location -> list of results
        """
        logger.info(f"Starting bulk scrape: '{search_query}' across {len(locations)} locations")

        for i, location in enumerate(locations):
            try:
                logger.info(f"Scraping location {i+1}/{len(locations)}: {location}")

                # Scrape this location
                results = await self.scraper.search_and_scrape(
                    search_query=search_query,
                    location=location,
                    max_results=max_results_per_location
                )

                self.results_by_location[location] = results
                logger.success(f"Completed {location}: {len(results)} results")

                # Delay before next location (except for last one)
                if i < len(locations) - 1:
                    logger.info(f"Waiting {delay_between_locations}s before next location...")
                    await asyncio.sleep(delay_between_locations)

            except Exception as e:
                logger.error(f"Error scraping {location}: {e}")
                self.results_by_location[location] = []
                continue

        # Summary
        total_results = sum(len(results) for results in self.results_by_location.values())
        logger.success(f"Bulk scrape complete! Total results: {total_results}")

        return self.results_by_location

    async def scrape_state(
        self,
        search_query: str,
        state: str,
        cities: List[str],
        max_results_per_city: int = 100
    ) -> Dict[str, List[Dict]]:
        """
        Scrape all major cities in a state.

        Args:
            search_query: Business category
            state: State name
            cities: List of cities in the state
            max_results_per_city: Max results per city

        Returns:
            Dictionary mapping city -> results
        """
        logger.info(f"Scraping {state} state: {len(cities)} cities")

        return await self.scrape_multiple_locations(
            search_query=search_query,
            locations=[f"{city}, {state}" for city in cities],
            max_results_per_location=max_results_per_city,
            delay_between_locations=300  # 5 min between cities
        )

    async def scrape_pin_codes(
        self,
        search_query: str,
        pin_codes: List[str],
        max_results_per_pin: int = 20
    ) -> Dict[str, List[Dict]]:
        """
        Scrape multiple pin codes.

        Args:
            search_query: Business category
            pin_codes: List of pin codes
            max_results_per_pin: Max results per pin code

        Returns:
            Dictionary mapping pin code -> results
        """
        logger.info(f"Scraping {len(pin_codes)} pin codes")

        return await self.scrape_multiple_locations(
            search_query=search_query,
            locations=pin_codes,
            max_results_per_location=max_results_per_pin,
            delay_between_locations=180  # 3 min between pin codes
        )

    def get_stats(self) -> Dict:
        """Get scraping statistics."""
        total_results = sum(len(results) for results in self.results_by_location.values())

        return {
            'locations_scraped': len(self.results_by_location),
            'total_results': total_results,
            'results_by_location': {
                loc: len(results)
                for loc, results in self.results_by_location.items()
            }
        }

    async def close(self):
        """Close scraper."""
        await self.scraper.close()


# Predefined location lists
INDIAN_METROS = [
    "Mumbai",
    "Delhi",
    "Bangalore",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Pune",
    "Ahmedabad"
]

MAHARASHTRA_CITIES = [
    "Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad",
    "Solapur", "Thane", "Navi Mumbai", "Kolhapur", "Sangli"
]

KARNATAKA_CITIES = [
    "Bangalore", "Mysore", "Mangalore", "Hubli", "Belgaum",
    "Gulbarga", "Davangere", "Bellary", "Bijapur", "Shimoga"
]

TAMIL_NADU_CITIES = [
    "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem",
    "Tirunelveli", "Tiruppur", "Erode", "Vellore", "Thoothukudi"
]
