"""Webhook notifications module for MapLeads Pro."""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List, Any
from datetime import datetime
from loguru import logger

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from slack_sdk.web.async_client import AsyncWebClient
    from slack_sdk.errors import SlackApiError
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

try:
    from discord_webhook import DiscordWebhook, DiscordEmbed
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False


class NotificationService:
    """
    Unified notification service for Slack, Discord, Email, and custom webhooks.
    """

    def __init__(
        self,
        slack_token: Optional[str] = None,
        slack_channel: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        email_from: Optional[str] = None,
        email_to: Optional[List[str]] = None
    ):
        """
        Initialize notification service.

        Args:
            slack_token: Slack Bot OAuth token
            slack_channel: Default Slack channel ID
            discord_webhook_url: Discord webhook URL
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            email_from: Sender email address
            email_to: Default recipient email addresses
        """
        # Slack configuration
        self.slack_client = None
        self.slack_channel = slack_channel
        if slack_token and SLACK_AVAILABLE:
            self.slack_client = AsyncWebClient(token=slack_token)

        # Discord configuration
        self.discord_webhook_url = discord_webhook_url

        # Email configuration
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.email_from = email_from
        self.email_to = email_to or []

        # Stats
        self.stats = {
            "slack_sent": 0,
            "discord_sent": 0,
            "email_sent": 0,
            "webhook_sent": 0,
            "failed": 0
        }

    async def notify_scrape_complete(
        self,
        job_id: int,
        search_query: str,
        leads_scraped: int,
        duration_seconds: int,
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Send notification when a scrape job completes.

        Args:
            job_id: Scrape job ID
            search_query: The search query used
            leads_scraped: Number of leads scraped
            duration_seconds: Job duration in seconds
            channels: List of channels to notify ("slack", "discord", "email")

        Returns:
            Dict mapping channel to success status
        """
        channels = channels or ["slack", "discord", "email"]
        results = {}

        message = self._format_scrape_complete_message(
            job_id, search_query, leads_scraped, duration_seconds
        )

        if "slack" in channels:
            results["slack"] = await self.send_slack(message["text"], message["blocks"])

        if "discord" in channels:
            results["discord"] = await self.send_discord(
                title=message["title"],
                description=message["text"],
                color=0x00FF00 if leads_scraped > 0 else 0xFFFF00,
                fields=message["fields"]
            )

        if "email" in channels:
            results["email"] = await self.send_email(
                subject=message["title"],
                body=message["html"],
                is_html=True
            )

        return results

    async def notify_scrape_failed(
        self,
        job_id: int,
        search_query: str,
        error: str,
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Send notification when a scrape job fails.

        Args:
            job_id: Scrape job ID
            search_query: The search query used
            error: Error message
            channels: List of channels to notify

        Returns:
            Dict mapping channel to success status
        """
        channels = channels or ["slack", "discord", "email"]
        results = {}

        message = self._format_scrape_failed_message(job_id, search_query, error)

        if "slack" in channels:
            results["slack"] = await self.send_slack(message["text"], message["blocks"])

        if "discord" in channels:
            results["discord"] = await self.send_discord(
                title=message["title"],
                description=message["text"],
                color=0xFF0000,
                fields=message["fields"]
            )

        if "email" in channels:
            results["email"] = await self.send_email(
                subject=message["title"],
                body=message["html"],
                is_html=True
            )

        return results

    async def send_slack(
        self,
        text: str,
        blocks: Optional[List[Dict]] = None,
        channel: Optional[str] = None
    ) -> bool:
        """
        Send a Slack message.

        Args:
            text: Message text (fallback)
            blocks: Slack block kit blocks
            channel: Channel ID (uses default if not specified)

        Returns:
            True if sent successfully
        """
        if not self.slack_client:
            logger.warning("Slack not configured")
            return False

        try:
            target_channel = channel or self.slack_channel
            if not target_channel:
                logger.error("No Slack channel specified")
                return False

            response = await self.slack_client.chat_postMessage(
                channel=target_channel,
                text=text,
                blocks=blocks
            )

            if response["ok"]:
                self.stats["slack_sent"] += 1
                logger.info(f"Slack message sent to {target_channel}")
                return True
            else:
                logger.error(f"Slack error: {response.get('error')}")
                self.stats["failed"] += 1
                return False

        except SlackApiError as e:
            logger.error(f"Slack API error: {e.response['error']}")
            self.stats["failed"] += 1
            return False
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            self.stats["failed"] += 1
            return False

    async def send_discord(
        self,
        title: str,
        description: str,
        color: int = 0x00FF00,
        fields: Optional[List[Dict]] = None,
        webhook_url: Optional[str] = None
    ) -> bool:
        """
        Send a Discord webhook message.

        Args:
            title: Embed title
            description: Embed description
            color: Embed color (hex)
            fields: List of field dicts with name, value, inline
            webhook_url: Webhook URL (uses default if not specified)

        Returns:
            True if sent successfully
        """
        if not DISCORD_AVAILABLE:
            logger.warning("Discord webhook not available")
            return False

        url = webhook_url or self.discord_webhook_url
        if not url:
            logger.warning("Discord webhook URL not configured")
            return False

        try:
            webhook = DiscordWebhook(url=url)

            embed = DiscordEmbed(
                title=title,
                description=description,
                color=color
            )

            embed.set_footer(text="MapLeads Pro")
            embed.set_timestamp()

            if fields:
                for field in fields:
                    embed.add_embed_field(
                        name=field.get("name", ""),
                        value=field.get("value", ""),
                        inline=field.get("inline", False)
                    )

            webhook.add_embed(embed)

            # Execute in thread pool (sync library)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, webhook.execute)

            if response.status_code in [200, 204]:
                self.stats["discord_sent"] += 1
                logger.info("Discord message sent")
                return True
            else:
                logger.error(f"Discord error: {response.status_code}")
                self.stats["failed"] += 1
                return False

        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")
            self.stats["failed"] += 1
            return False

    async def send_email(
        self,
        subject: str,
        body: str,
        to: Optional[List[str]] = None,
        is_html: bool = False
    ) -> bool:
        """
        Send an email notification.

        Args:
            subject: Email subject
            body: Email body
            to: Recipient email addresses
            is_html: Whether body is HTML

        Returns:
            True if sent successfully
        """
        if not all([self.smtp_host, self.smtp_user, self.smtp_password, self.email_from]):
            logger.warning("Email not fully configured")
            return False

        recipients = to or self.email_to
        if not recipients:
            logger.warning("No email recipients specified")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = ', '.join(recipients)

            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email_sync,
                recipients,
                msg
            )

            self.stats["email_sent"] += 1
            logger.info(f"Email sent to {', '.join(recipients)}")
            return True

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            self.stats["failed"] += 1
            return False

    def _send_email_sync(self, recipients: List[str], msg: MIMEMultipart):
        """Synchronous email sending (runs in executor)."""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.sendmail(self.email_from, recipients, msg.as_string())

    async def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Send a custom webhook notification.

        Args:
            url: Webhook URL
            payload: JSON payload
            method: HTTP method
            headers: Custom headers

        Returns:
            True if sent successfully
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available for webhooks")
            return False

        try:
            default_headers = {"Content-Type": "application/json"}
            if headers:
                default_headers.update(headers)

            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    url,
                    json=payload,
                    headers=default_headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status in [200, 201, 204]:
                        self.stats["webhook_sent"] += 1
                        logger.info(f"Webhook sent to {url}")
                        return True
                    else:
                        logger.error(f"Webhook failed: {response.status}")
                        self.stats["failed"] += 1
                        return False

        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            self.stats["failed"] += 1
            return False

    def _format_scrape_complete_message(
        self,
        job_id: int,
        search_query: str,
        leads_scraped: int,
        duration_seconds: int
    ) -> Dict:
        """Format scrape complete notification message."""
        duration_str = f"{duration_seconds // 60}m {duration_seconds % 60}s"

        return {
            "title": f"Scrape Complete: {search_query}",
            "text": f"Job #{job_id} completed! Scraped {leads_scraped} leads in {duration_str}.",
            "html": f"""
            <h2>Scrape Job Completed</h2>
            <p><strong>Job ID:</strong> {job_id}</p>
            <p><strong>Search Query:</strong> {search_query}</p>
            <p><strong>Leads Scraped:</strong> {leads_scraped}</p>
            <p><strong>Duration:</strong> {duration_str}</p>
            <p><strong>Completed:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><a href="http://localhost:8000/dashboard">View Dashboard</a></p>
            """,
            "fields": [
                {"name": "Job ID", "value": str(job_id), "inline": True},
                {"name": "Leads", "value": str(leads_scraped), "inline": True},
                {"name": "Duration", "value": duration_str, "inline": True},
            ],
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Scrape Job Completed"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Job ID:*\n{job_id}"},
                        {"type": "mrkdwn", "text": f"*Search Query:*\n{search_query}"},
                        {"type": "mrkdwn", "text": f"*Leads Scraped:*\n{leads_scraped}"},
                        {"type": "mrkdwn", "text": f"*Duration:*\n{duration_str}"}
                    ]
                }
            ]
        }

    def _format_scrape_failed_message(
        self,
        job_id: int,
        search_query: str,
        error: str
    ) -> Dict:
        """Format scrape failed notification message."""
        return {
            "title": f"Scrape Failed: {search_query}",
            "text": f"Job #{job_id} failed! Error: {error}",
            "html": f"""
            <h2 style="color: red;">Scrape Job Failed</h2>
            <p><strong>Job ID:</strong> {job_id}</p>
            <p><strong>Search Query:</strong> {search_query}</p>
            <p><strong>Error:</strong> {error}</p>
            <p><strong>Failed At:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><a href="http://localhost:8000/dashboard">View Dashboard</a></p>
            """,
            "fields": [
                {"name": "Job ID", "value": str(job_id), "inline": True},
                {"name": "Error", "value": error[:200], "inline": False},
            ],
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Scrape Job Failed",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Job ID:*\n{job_id}"},
                        {"type": "mrkdwn", "text": f"*Search Query:*\n{search_query}"},
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n```{error[:500]}```"
                    }
                }
            ]
        }

    def get_stats(self) -> Dict:
        """Get notification statistics."""
        return {
            **self.stats,
            "total_sent": sum([
                self.stats["slack_sent"],
                self.stats["discord_sent"],
                self.stats["email_sent"],
                self.stats["webhook_sent"]
            ])
        }


# Singleton instance
_notification_service = None

def get_notification_service(**kwargs) -> NotificationService:
    """Get or create the notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService(**kwargs)
    return _notification_service
