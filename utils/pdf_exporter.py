"""PDF export functionality using reportlab.

This module exports leads as professional PDF documents
with lead cards and summary tables.
"""

from typing import List, Dict, Optional
from datetime import datetime
import io
import os
from loguru import logger

# Check for reportlab availability
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, PageBreak, Image
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFExporter:
    """
    Exports leads to PDF format with professional formatting.
    """

    def __init__(self, page_size=None):
        """
        Initialize the PDF exporter.

        Args:
            page_size: Page size (default: letter). Options: letter, A4
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "reportlab is required for PDF export. "
                "Install with: pip install reportlab"
            )

        self.page_size = page_size or letter
        self.styles = getSampleStyleSheet()

        # Add custom styles
        self.styles.add(ParagraphStyle(
            name='LeadTitle',
            fontSize=14,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            textColor=colors.HexColor('#1a73e8')
        ))

        self.styles.add(ParagraphStyle(
            name='LeadSubtitle',
            fontSize=10,
            fontName='Helvetica-Oblique',
            spaceAfter=4,
            textColor=colors.HexColor('#666666')
        ))

        self.styles.add(ParagraphStyle(
            name='LeadInfo',
            fontSize=10,
            fontName='Helvetica',
            spaceAfter=3
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            fontSize=12,
            fontName='Helvetica-Bold',
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor('#333333')
        ))

        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            fontSize=24,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.HexColor('#1a73e8')
        ))

        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            fontSize=12,
            fontName='Helvetica',
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.HexColor('#666666')
        ))

    def export_leads(
        self,
        leads: List[Dict],
        title: str = "Business Leads Report",
        output_path: str = None,
        include_summary: bool = True
    ) -> bytes:
        """
        Export leads to PDF.

        Args:
            leads: List of lead dictionaries
            title: Report title
            output_path: Optional file path to save
            include_summary: Include summary statistics

        Returns:
            PDF bytes if no output_path, otherwise saves to file
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        story = []

        # Title page content
        story.append(Paragraph(title, self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Total Leads: {len(leads)}",
            self.styles['ReportSubtitle']
        ))
        story.append(Spacer(1, 20))

        # Summary statistics
        if include_summary and leads:
            story.extend(self._create_summary(leads))
            story.append(Spacer(1, 30))

        # Lead cards
        for i, lead in enumerate(leads, 1):
            story.extend(self._create_lead_card(lead, i))

            # Page break every 3 leads
            if i % 3 == 0 and i < len(leads):
                story.append(PageBreak())
            else:
                story.append(Spacer(1, 20))

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            logger.info(f"PDF exported to: {output_path}")

        return pdf_bytes

    def _create_summary(self, leads: List[Dict]) -> list:
        """Create summary statistics section."""
        elements = []

        elements.append(Paragraph("Summary Statistics", self.styles['SectionHeader']))

        # Calculate statistics
        total = len(leads)
        with_phone = sum(1 for l in leads if l.get('phone'))
        with_email = sum(1 for l in leads if l.get('email'))
        with_website = sum(1 for l in leads if l.get('website'))

        ratings = [l.get('rating') for l in leads if l.get('rating')]
        avg_rating = sum(ratings) / len(ratings) if ratings else 0

        quality_scores = [
            l.get('data_quality_score') or l.get('quality_score') or 0
            for l in leads
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        # Summary table
        summary_data = [
            ['Metric', 'Value', 'Percentage'],
            ['Total Leads', str(total), '100%'],
            ['With Phone', str(with_phone), f'{with_phone/total*100:.1f}%' if total else '0%'],
            ['With Email', str(with_email), f'{with_email/total*100:.1f}%' if total else '0%'],
            ['With Website', str(with_website), f'{with_website/total*100:.1f}%' if total else '0%'],
            ['Average Rating', f'{avg_rating:.2f}' if avg_rating else 'N/A', '-'],
            ['Average Quality Score', f'{avg_quality:.0f}' if avg_quality else 'N/A', '-'],
        ]

        summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),

            # Body
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),

            # Alternating rows
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))

        elements.append(summary_table)
        return elements

    def _create_lead_card(self, lead: Dict, index: int) -> list:
        """Create a lead card with all information."""
        elements = []

        # Business name and category
        name = lead.get('business_name', 'Unknown Business')
        category = lead.get('category', '')

        elements.append(Paragraph(
            f"{index}. {self._escape_html(name)}",
            self.styles['LeadTitle']
        ))

        if category:
            elements.append(Paragraph(
                f"Category: {self._escape_html(category)}",
                self.styles['LeadSubtitle']
            ))

        # Contact information table
        contact_data = []

        if lead.get('phone'):
            contact_data.append(['Phone:', lead['phone']])
        if lead.get('email'):
            contact_data.append(['Email:', lead['email']])
        if lead.get('website'):
            website = lead['website']
            if len(website) > 50:
                website = website[:47] + '...'
            contact_data.append(['Website:', website])

        if contact_data:
            elements.append(Paragraph("Contact Information", self.styles['SectionHeader']))
            contact_table = Table(contact_data, colWidths=[1.2*inch, 4*inch])
            contact_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(contact_table)

        # Address
        if lead.get('full_address') or lead.get('address'):
            elements.append(Paragraph("Address", self.styles['SectionHeader']))
            address = lead.get('full_address') or lead.get('address')
            elements.append(Paragraph(self._escape_html(address), self.styles['LeadInfo']))

        # Ratings and reviews
        rating = lead.get('rating')
        review_count = lead.get('review_count', 0)
        if rating or review_count:
            elements.append(Paragraph("Reviews", self.styles['SectionHeader']))
            stars = '★' * int(rating or 0) + '☆' * (5 - int(rating or 0)) if rating else 'N/A'
            rating_text = f"Rating: {rating or 'N/A'} {stars} | Reviews: {review_count or 0}"
            elements.append(Paragraph(rating_text, self.styles['LeadInfo']))

        # Social media
        social_links = []
        for platform in ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube']:
            key = f'social_{platform}'
            if lead.get(key):
                social_links.append(platform.capitalize())

        if social_links:
            elements.append(Paragraph("Social Media", self.styles['SectionHeader']))
            elements.append(Paragraph(', '.join(social_links), self.styles['LeadInfo']))

        # Lead score and quality
        score_info = []
        if lead.get('lead_score'):
            score_info.append(f"Lead Score: {lead['lead_score']}")
        if lead.get('data_quality_score') or lead.get('quality_score'):
            quality = lead.get('data_quality_score') or lead.get('quality_score')
            score_info.append(f"Quality: {quality}%")

        if score_info:
            elements.append(Paragraph(' | '.join(score_info), self.styles['LeadInfo']))

        # Horizontal line
        line_data = [['─' * 80]]
        line_table = Table(line_data, colWidths=[7*inch])
        line_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#cccccc')),
        ]))
        elements.append(Spacer(1, 10))
        elements.append(line_table)

        return elements

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ''
        return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))

    def export_summary_table(
        self,
        leads: List[Dict],
        columns: List[str] = None,
        title: str = "Leads Summary"
    ) -> bytes:
        """
        Export leads as a summary table PDF.

        Args:
            leads: List of lead dictionaries
            columns: Columns to include (default: basic info)
            title: Report title

        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.3*inch,
            leftMargin=0.3*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch
        )

        # Default columns
        if not columns:
            columns = ['business_name', 'phone', 'email', 'city', 'rating']

        story = []

        # Title
        story.append(Paragraph(title, self.styles['ReportTitle']))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(leads)} Records",
            self.styles['ReportSubtitle']
        ))
        story.append(Spacer(1, 20))

        # Table header
        header = [col.replace('_', ' ').title() for col in columns]
        table_data = [header]

        # Table rows
        for lead in leads:
            row = []
            for col in columns:
                value = lead.get(col, '')
                if value is None:
                    value = ''
                # Truncate long values
                if isinstance(value, str) and len(value) > 30:
                    value = value[:27] + '...'
                row.append(str(value))
            table_data.append(row)

        # Create table
        col_width = (doc.width - 0.5*inch) / len(columns)
        table = Table(table_data, colWidths=[col_width] * len(columns))

        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Body style
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 5),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table)

        doc.build(story)

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes


# Convenience functions
def export_leads_to_pdf(
    leads: List[Dict],
    output_path: str = None,
    title: str = "Business Leads Report"
) -> bytes:
    """
    Quick function to export leads to PDF.

    Args:
        leads: List of lead dictionaries
        output_path: Optional file path to save
        title: Report title

    Returns:
        PDF bytes
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required. Install with: pip install reportlab")

    exporter = PDFExporter()
    return exporter.export_leads(leads, title=title, output_path=output_path)


def export_leads_table_to_pdf(
    leads: List[Dict],
    output_path: str = None,
    columns: List[str] = None
) -> bytes:
    """
    Quick function to export leads as a table PDF.

    Args:
        leads: List of lead dictionaries
        output_path: Optional file path
        columns: Columns to include

    Returns:
        PDF bytes
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required. Install with: pip install reportlab")

    exporter = PDFExporter()
    pdf_bytes = exporter.export_summary_table(leads, columns=columns)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
        logger.info(f"PDF table exported to: {output_path}")

    return pdf_bytes


# Check availability
def is_pdf_export_available() -> bool:
    """Check if PDF export is available."""
    return REPORTLAB_AVAILABLE
