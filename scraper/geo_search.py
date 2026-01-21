"""Geo-coordinate based search for Google Maps."""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import math
from loguru import logger


@dataclass
class GeoSearchConfig:
    """Configuration for geo-based search."""
    latitude: float
    longitude: float
    radius_km: float = 5.0
    search_query: str = ""
    grid_size: int = 3  # 3x3 grid for coverage


class GeoSearchManager:
    """Manage geo-coordinate based searches."""

    EARTH_RADIUS_KM = 6371.0

    def __init__(self):
        self.searched_areas: List[Tuple[float, float]] = []

    def generate_search_url(
        self,
        query: str,
        lat: float,
        lng: float,
        zoom: int = 15
    ) -> str:
        """Generate Google Maps search URL with coordinates."""
        encoded_query = query.replace(' ', '+')
        return f"https://www.google.com/maps/search/{encoded_query}/@{lat},{lng},{zoom}z"

    def generate_grid_points(
        self,
        center_lat: float,
        center_lng: float,
        radius_km: float,
        grid_size: int = 3
    ) -> List[Dict]:
        """Generate grid of search points to cover area."""
        points = []

        # Calculate the distance between grid points
        step = (radius_km * 2) / grid_size

        for i in range(grid_size):
            for j in range(grid_size):
                # Calculate offset from center
                offset_km_lat = (i - grid_size // 2) * step
                offset_km_lng = (j - grid_size // 2) * step

                # Convert km offset to lat/lng offset
                lat_offset = offset_km_lat / 111.0  # ~111km per degree latitude
                lng_offset = offset_km_lng / (111.0 * math.cos(math.radians(center_lat)))

                new_lat = center_lat + lat_offset
                new_lng = center_lng + lng_offset

                points.append({
                    "latitude": round(new_lat, 6),
                    "longitude": round(new_lng, 6),
                    "grid_position": f"{i},{j}"
                })

        return points

    def calculate_distance(
        self,
        lat1: float, lng1: float,
        lat2: float, lng2: float
    ) -> float:
        """Calculate distance between two coordinates in km (Haversine)."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat/2)**2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        return self.EARTH_RADIUS_KM * c

    def filter_by_radius(
        self,
        leads: List[Dict],
        center_lat: float,
        center_lng: float,
        radius_km: float
    ) -> List[Dict]:
        """Filter leads to only include those within radius."""
        filtered = []

        for lead in leads:
            lead_lat = lead.get("latitude")
            lead_lng = lead.get("longitude")

            if lead_lat and lead_lng:
                distance = self.calculate_distance(
                    center_lat, center_lng, lead_lat, lead_lng
                )
                if distance <= radius_km:
                    lead["distance_km"] = round(distance, 2)
                    filtered.append(lead)
            else:
                # Include leads without coordinates (can't verify distance)
                filtered.append(lead)

        return filtered

    def get_zoom_level_for_radius(self, radius_km: float) -> int:
        """Calculate appropriate zoom level for a given radius."""
        # Approximate zoom levels for different radii
        if radius_km <= 0.5:
            return 17
        elif radius_km <= 1:
            return 16
        elif radius_km <= 2:
            return 15
        elif radius_km <= 5:
            return 14
        elif radius_km <= 10:
            return 13
        elif radius_km <= 20:
            return 12
        elif radius_km <= 50:
            return 11
        else:
            return 10

    def get_bounding_box(
        self,
        center_lat: float,
        center_lng: float,
        radius_km: float
    ) -> Dict:
        """Calculate bounding box for a center point and radius."""
        # Approximate degrees per km
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)))

        return {
            "north": center_lat + lat_delta,
            "south": center_lat - lat_delta,
            "east": center_lng + lng_delta,
            "west": center_lng - lng_delta,
        }


# Singleton instance
geo_search_manager = GeoSearchManager()
