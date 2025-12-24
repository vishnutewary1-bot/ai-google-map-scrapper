"""Main entry point for Google Maps Scraper."""
import asyncio
import argparse
from loguru import logger

from database import db_manager
from scraper import GoogleMapsScraper
from utils import DataExporter
from config.settings import settings


async def scrape_command(args):
    """Execute scraping command."""
    scraper = GoogleMapsScraper()

    try:
        # Initialize database
        db_manager.initialize()
        db_manager.create_tables()

        # Initialize scraper
        await scraper.initialize()

        # Run scraping
        results = await scraper.search_and_scrape(
            search_query=args.query,
            location=args.location,
            max_results=args.limit
        )

        logger.info(f"Scraping completed: {len(results)} businesses found")

        # Auto-export if requested
        if args.export:
            exporter = DataExporter()
            export_path = exporter.export_to_csv(data=results)
            logger.info(f"Results exported to: {export_path}")

    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise
    finally:
        await scraper.close()


async def export_command(args):
    """Execute export command."""
    try:
        # Initialize database
        db_manager.initialize()

        exporter = DataExporter()

        # Build filters
        filters = {}
        if args.has_phone:
            filters['has_phone'] = True
        if args.has_website:
            filters['has_website'] = True
        if args.has_email:
            filters['has_email'] = True
        if args.city:
            filters['city'] = args.city
        if args.state:
            filters['state'] = args.state
        if args.category:
            filters['category'] = args.category
        if args.min_quality:
            filters['min_quality_score'] = args.min_quality

        # Export based on format
        if args.format == 'csv':
            filepath = exporter.export_to_csv(filters=filters, filename=args.output)
        elif args.format == 'json':
            filepath = exporter.export_to_json(filters=filters, filename=args.output)
        elif args.format == 'cold_calling':
            filepath = exporter.export_cold_calling_format(filters=filters, filename=args.output)

        if filepath:
            logger.info(f"Export completed: {filepath}")
        else:
            logger.warning("No data to export")

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise


def stats_command(args):
    """Show database statistics."""
    try:
        db_manager.initialize()

        with db_manager.get_session() as session:
            from database.models import BusinessLead, ScrapeJob

            # Total leads
            total_leads = session.query(BusinessLead).count()
            logger.info(f"Total leads in database: {total_leads}")

            # Leads with phone
            leads_with_phone = session.query(BusinessLead).filter(
                BusinessLead.phone.isnot(None)
            ).count()
            logger.info(f"Leads with phone: {leads_with_phone}")

            # Leads with website
            leads_with_website = session.query(BusinessLead).filter(
                BusinessLead.website.isnot(None)
            ).count()
            logger.info(f"Leads with website: {leads_with_website}")

            # Leads with email
            leads_with_email = session.query(BusinessLead).filter(
                BusinessLead.email.isnot(None)
            ).count()
            logger.info(f"Leads with email: {leads_with_email}")

            # Total jobs
            total_jobs = session.query(ScrapeJob).count()
            logger.info(f"Total scrape jobs: {total_jobs}")

            # Completed jobs
            completed_jobs = session.query(ScrapeJob).filter(
                ScrapeJob.status == 'completed'
            ).count()
            logger.info(f"Completed jobs: {completed_jobs}")

            # Average quality score
            from sqlalchemy import func
            avg_quality = session.query(
                func.avg(BusinessLead.data_quality_score)
            ).scalar()
            if avg_quality:
                logger.info(f"Average data quality score: {avg_quality:.1f}%")

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise


def init_db_command(args):
    """Initialize database tables."""
    try:
        logger.info("Initializing database...")
        db_manager.initialize()
        db_manager.create_tables()
        logger.info("Database initialized successfully!")
        logger.info(f"Database URL: {settings.database_url}")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Google Maps Lead Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database
  python main.py init-db

  # Scrape restaurants in Mumbai
  python main.py scrape --query "restaurants" --location "Mumbai" --limit 50

  # Scrape with auto-export
  python main.py scrape --query "doctors" --location "Delhi" --limit 100 --export

  # Export all leads with phone numbers to CSV
  python main.py export --format csv --has-phone --output my_leads.csv

  # Export cold calling format
  python main.py export --format cold_calling --city "Mumbai"

  # Show database statistics
  python main.py stats
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Init DB command
    init_parser = subparsers.add_parser('init-db', help='Initialize database tables')

    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape Google Maps')
    scrape_parser.add_argument('--query', '-q', required=True, help='Search query (e.g., "restaurants", "doctors")')
    scrape_parser.add_argument('--location', '-l', help='Location to search (e.g., "Mumbai", "Delhi NCR")')
    scrape_parser.add_argument('--limit', type=int, default=100, help='Maximum results to scrape (default: 100)')
    scrape_parser.add_argument('--export', action='store_true', help='Auto-export results to CSV')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export scraped data')
    export_parser.add_argument('--format', choices=['csv', 'json', 'cold_calling'], default='csv', help='Export format')
    export_parser.add_argument('--output', '-o', help='Output filename (auto-generated if not specified)')
    export_parser.add_argument('--has-phone', action='store_true', help='Only export leads with phone numbers')
    export_parser.add_argument('--has-website', action='store_true', help='Only export leads with websites')
    export_parser.add_argument('--has-email', action='store_true', help='Only export leads with emails')
    export_parser.add_argument('--city', help='Filter by city')
    export_parser.add_argument('--state', help='Filter by state')
    export_parser.add_argument('--category', help='Filter by category')
    export_parser.add_argument('--min-quality', type=int, help='Minimum data quality score (0-100)')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')

    args = parser.parse_args()

    # Execute command
    if args.command == 'init-db':
        init_db_command(args)

    elif args.command == 'scrape':
        asyncio.run(scrape_command(args))

    elif args.command == 'export':
        asyncio.run(export_command(args))

    elif args.command == 'stats':
        stats_command(args)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
