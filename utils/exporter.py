"""Data export utilities for various formats."""
import csv
import json
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger

from database import db_manager, BusinessLead


class DataExporter:
    """Export scraped data to various formats."""

    def __init__(self, output_dir: str = "exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_to_csv(
        self,
        data: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Export data to CSV file.

        Args:
            data: List of business data dictionaries (if None, fetch from DB)
            filters: Database filters to apply when fetching data
            filename: Output filename (auto-generated if None)

        Returns:
            Path to the exported CSV file
        """
        try:
            # Get data from database if not provided
            if data is None:
                data = self._fetch_from_database(filters)

            if not data:
                logger.warning("No data to export")
                return None

            # Generate filename
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"leads_export_{timestamp}.csv"

            filepath = self.output_dir / filename

            # Define CSV columns (core fields)
            fieldnames = [
                'id',
                'business_name',
                'full_address',
                'city',
                'state',
                'pin_code',
                'phone',
                'website',
                'email',
                'category',
                'rating',
                'review_count',
                'maps_url',
                'place_id',
                'latitude',
                'longitude',
                'scraped_at',
                'search_query',
                'data_quality_score',
            ]

            # Write CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')

                writer.writeheader()
                for row in data:
                    # Convert datetime to string if present
                    if isinstance(row.get('scraped_at'), datetime):
                        row['scraped_at'] = row['scraped_at'].isoformat()

                    writer.writerow(row)

            logger.info(f"Exported {len(data)} records to CSV: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise

    def export_to_json(
        self,
        data: Optional[List[Dict]] = None,
        filters: Optional[Dict] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Export data to JSON file.

        Args:
            data: List of business data dictionaries (if None, fetch from DB)
            filters: Database filters to apply when fetching data
            filename: Output filename (auto-generated if None)

        Returns:
            Path to the exported JSON file
        """
        try:
            # Get data from database if not provided
            if data is None:
                data = self._fetch_from_database(filters)

            if not data:
                logger.warning("No data to export")
                return None

            # Generate filename
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"leads_export_{timestamp}.json"

            filepath = self.output_dir / filename

            # Prepare export data
            export_data = {
                'export_date': datetime.now().isoformat(),
                'total_records': len(data),
                'leads': []
            }

            # Convert datetime objects to strings
            for row in data:
                row_copy = row.copy()
                if isinstance(row_copy.get('scraped_at'), datetime):
                    row_copy['scraped_at'] = row_copy['scraped_at'].isoformat()
                if isinstance(row_copy.get('created_at'), datetime):
                    row_copy['created_at'] = row_copy['created_at'].isoformat()
                if isinstance(row_copy.get('updated_at'), datetime):
                    row_copy['updated_at'] = row_copy['updated_at'].isoformat()

                export_data['leads'].append(row_copy)

            # Write JSON
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(data)} records to JSON: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            raise

    def export_cold_calling_format(
        self,
        filters: Optional[Dict] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        Export in cold calling optimized format (only essential fields).

        Args:
            filters: Database filters to apply
            filename: Output filename (auto-generated if None)

        Returns:
            Path to the exported CSV file
        """
        try:
            # Fetch data with phone number filter
            if filters is None:
                filters = {}
            filters['has_phone'] = True

            data = self._fetch_from_database(filters)

            if not data:
                logger.warning("No data with phone numbers to export")
                return None

            # Generate filename
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"cold_calling_leads_{timestamp}.csv"

            filepath = self.output_dir / filename

            # Simplified columns for cold calling
            fieldnames = [
                'business_name',
                'phone',
                'city',
                'state',
                'category',
                'website',
                'full_address',
            ]

            # Write CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')

                writer.writeheader()
                writer.writerows(data)

            logger.info(f"Exported {len(data)} cold calling leads to: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Error exporting cold calling format: {e}")
            raise

    def _fetch_from_database(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Fetch data from database with optional filters."""
        try:
            with db_manager.get_session() as session:
                query = session.query(BusinessLead)

                # Apply filters
                if filters:
                    if filters.get('has_phone'):
                        query = query.filter(BusinessLead.phone.isnot(None))

                    if filters.get('has_website'):
                        query = query.filter(BusinessLead.website.isnot(None))

                    if filters.get('has_email'):
                        query = query.filter(BusinessLead.email.isnot(None))

                    if filters.get('city'):
                        query = query.filter(BusinessLead.city == filters['city'])

                    if filters.get('state'):
                        query = query.filter(BusinessLead.state == filters['state'])

                    if filters.get('category'):
                        query = query.filter(BusinessLead.category == filters['category'])

                    if filters.get('min_quality_score'):
                        query = query.filter(
                            BusinessLead.data_quality_score >= filters['min_quality_score']
                        )

                    if filters.get('search_query'):
                        query = query.filter(BusinessLead.search_query == filters['search_query'])

                # Execute query
                results = query.all()

                # Convert to dictionaries
                data = [lead.to_dict() for lead in results]

                logger.info(f"Fetched {len(data)} records from database")
                return data

        except Exception as e:
            logger.error(f"Error fetching from database: {e}")
            return []

    def get_export_stats(self) -> Dict:
        """Get statistics about exported files."""
        try:
            stats = {
                'total_files': 0,
                'total_size_mb': 0,
                'files': []
            }

            for filepath in self.output_dir.glob('*'):
                if filepath.is_file():
                    size_mb = filepath.stat().st_size / (1024 * 1024)
                    stats['files'].append({
                        'name': filepath.name,
                        'size_mb': round(size_mb, 2),
                        'modified': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat()
                    })
                    stats['total_files'] += 1
                    stats['total_size_mb'] += size_mb

            stats['total_size_mb'] = round(stats['total_size_mb'], 2)

            return stats

        except Exception as e:
            logger.error(f"Error getting export stats: {e}")
            return {}
