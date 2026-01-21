"""Generic webhook notifications for Zapier/Make/n8n compatibility."""
import asyncio
import json
import hashlib
import hmac
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    url: str
    secret: Optional[str] = None  # For HMAC signing
    headers: Optional[Dict[str, str]] = None
    retry_count: int = 3
    timeout: int = 30
    events: List[str] = field(default_factory=lambda: ["job.completed", "lead.created"])


class WebhookManager:
    """Manage webhook notifications."""

    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.event_history: List[Dict] = []
        self._initialized = False

    def register_webhook(self, name: str, config: WebhookConfig):
        """Register a webhook endpoint."""
        self.webhooks[name] = config
        logger.info(f"Registered webhook: {name} -> {config.url}")

    def register_from_url(self, name: str, url: str, secret: Optional[str] = None):
        """Register a webhook from URL string."""
        config = WebhookConfig(url=url, secret=secret)
        self.register_webhook(name, config)

    def unregister_webhook(self, name: str):
        """Remove a registered webhook."""
        if name in self.webhooks:
            del self.webhooks[name]
            logger.info(f"Unregistered webhook: {name}")

    def _sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for payload."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    async def send_webhook_async(
        self,
        webhook_name: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Send webhook notification asynchronously."""
        if not HAS_AIOHTTP:
            logger.warning("aiohttp not installed, using sync method")
            return self.send_webhook_sync(webhook_name, event_type, data)

        if webhook_name not in self.webhooks:
            logger.error(f"Webhook not registered: {webhook_name}")
            return False

        config = self.webhooks[webhook_name]

        # Check if event type is in allowed events
        if event_type not in config.events and "*" not in config.events:
            logger.debug(f"Event {event_type} not in allowed events for {webhook_name}")
            return True  # Not an error, just filtered

        # Build payload (Zapier/Make compatible format)
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }

        payload_json = json.dumps(payload)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MapLeads-Pro/2.0",
            "X-Webhook-Event": event_type,
            **(config.headers or {})
        }

        # Add signature if secret is configured
        if config.secret:
            signature = self._sign_payload(payload_json, config.secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Send with retries
        for attempt in range(config.retry_count):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        config.url,
                        data=payload_json,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=config.timeout)
                    ) as response:
                        if response.status in (200, 201, 202, 204):
                            logger.info(f"Webhook sent: {webhook_name} - {event_type}")
                            self._record_event(webhook_name, event_type, True)
                            return True
                        else:
                            body = await response.text()
                            logger.warning(f"Webhook returned {response.status}: {body[:100]}")

            except asyncio.TimeoutError:
                logger.error(f"Webhook timeout attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Webhook attempt {attempt + 1} failed: {e}")

            if attempt < config.retry_count - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        self._record_event(webhook_name, event_type, False)
        return False

    def send_webhook_sync(
        self,
        webhook_name: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Send webhook notification synchronously."""
        if not HAS_REQUESTS:
            logger.error("requests library not installed")
            return False

        if webhook_name not in self.webhooks:
            logger.error(f"Webhook not registered: {webhook_name}")
            return False

        config = self.webhooks[webhook_name]

        # Build payload
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }

        payload_json = json.dumps(payload)

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MapLeads-Pro/2.0",
            "X-Webhook-Event": event_type,
            **(config.headers or {})
        }

        if config.secret:
            signature = self._sign_payload(payload_json, config.secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Send with retries
        for attempt in range(config.retry_count):
            try:
                response = requests.post(
                    config.url,
                    data=payload_json,
                    headers=headers,
                    timeout=config.timeout
                )

                if response.status_code in (200, 201, 202, 204):
                    logger.info(f"Webhook sent: {webhook_name} - {event_type}")
                    self._record_event(webhook_name, event_type, True)
                    return True
                else:
                    logger.warning(f"Webhook returned {response.status_code}")

            except requests.Timeout:
                logger.error(f"Webhook timeout attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Webhook attempt {attempt + 1} failed: {e}")

            if attempt < config.retry_count - 1:
                import time
                time.sleep(2 ** attempt)

        self._record_event(webhook_name, event_type, False)
        return False

    def _record_event(self, webhook: str, event: str, success: bool):
        """Record webhook event for history."""
        self.event_history.append({
            "webhook": webhook,
            "event": event,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        })
        # Keep only last 100 events
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]

    async def send_lead_notification(self, lead: Dict, webhook_name: str = "default"):
        """Send notification when new lead is found."""
        await self.send_webhook_async(
            webhook_name,
            "lead.created",
            {
                "lead": {
                    "name": lead.get("business_name"),
                    "phone": lead.get("phone"),
                    "email": lead.get("email"),
                    "website": lead.get("website"),
                    "address": lead.get("full_address"),
                    "city": lead.get("city"),
                    "state": lead.get("state"),
                    "rating": lead.get("rating"),
                    "review_count": lead.get("review_count"),
                    "category": lead.get("category"),
                    "quality_score": lead.get("data_quality_score"),
                    "place_id": lead.get("place_id"),
                    "maps_url": lead.get("maps_url"),
                }
            }
        )

    async def send_job_notification(
        self,
        job_id: int,
        status: str,
        stats: Dict,
        webhook_name: str = "default"
    ):
        """Send notification when job status changes."""
        await self.send_webhook_async(
            webhook_name,
            f"job.{status}",
            {
                "job_id": job_id,
                "status": status,
                "stats": stats
            }
        )

    def send_lead_notification_sync(self, lead: Dict, webhook_name: str = "default"):
        """Synchronous version of send_lead_notification."""
        return self.send_webhook_sync(
            webhook_name,
            "lead.created",
            {
                "lead": {
                    "name": lead.get("business_name"),
                    "phone": lead.get("phone"),
                    "email": lead.get("email"),
                    "website": lead.get("website"),
                    "address": lead.get("full_address"),
                    "rating": lead.get("rating"),
                    "category": lead.get("category"),
                    "place_id": lead.get("place_id"),
                }
            }
        )

    def send_job_notification_sync(
        self,
        job_id: int,
        status: str,
        stats: Dict,
        webhook_name: str = "default"
    ):
        """Synchronous version of send_job_notification."""
        return self.send_webhook_sync(
            webhook_name,
            f"job.{status}",
            {
                "job_id": job_id,
                "status": status,
                "stats": stats
            }
        )

    def get_registered_webhooks(self) -> List[Dict]:
        """Get list of registered webhooks."""
        return [
            {
                "name": name,
                "url": config.url[:50] + "..." if len(config.url) > 50 else config.url,
                "events": config.events,
                "has_secret": bool(config.secret)
            }
            for name, config in self.webhooks.items()
        ]

    def get_event_history(self, limit: int = 50) -> List[Dict]:
        """Get recent webhook event history."""
        return self.event_history[-limit:]


# Global webhook manager
webhook_manager = WebhookManager()


# Helper functions for sync code
def send_webhook(webhook_name: str, event_type: str, data: Dict) -> bool:
    """Synchronous helper for sending webhooks."""
    return webhook_manager.send_webhook_sync(webhook_name, event_type, data)


def register_default_webhook(url: str, secret: Optional[str] = None):
    """Register the default webhook."""
    webhook_manager.register_from_url("default", url, secret)
