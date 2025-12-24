"""Session management for rotating browser sessions."""
import asyncio
from typing import Optional, Dict
from datetime import datetime, timedelta
from loguru import logger
from playwright.async_api import BrowserContext
import random

from scraper.browser_manager import BrowserManager


class SessionManager:
    """Manages browser sessions with automatic rotation."""

    def __init__(self, max_requests_per_session: int = 50, session_lifetime_minutes: int = 30):
        self.max_requests_per_session = max_requests_per_session
        self.session_lifetime = timedelta(minutes=session_lifetime_minutes)

        self.current_session: Optional[BrowserContext] = None
        self.session_created_at: Optional[datetime] = None
        self.session_request_count = 0

        self.browser_manager: Optional[BrowserManager] = None
        self.total_sessions_created = 0

    async def initialize(self, browser_manager: BrowserManager):
        """Initialize session manager with browser manager."""
        self.browser_manager = browser_manager
        await self.create_new_session()

    async def create_new_session(self) -> BrowserContext:
        """Create a new browser session with fresh fingerprint."""
        logger.info("Creating new browser session...")

        # Close old session if exists
        if self.current_session:
            try:
                await self.current_session.close()
            except Exception as e:
                logger.debug(f"Error closing old session: {e}")

        # Create new context with randomized settings
        self.current_session = await self.browser_manager.launch_browser()
        self.session_created_at = datetime.now()
        self.session_request_count = 0
        self.total_sessions_created += 1

        logger.info(f"New session created (total sessions: {self.total_sessions_created})")

        return self.current_session

    async def get_session(self) -> BrowserContext:
        """Get current session, rotating if necessary."""
        # Check if session needs rotation
        if self._should_rotate_session():
            logger.info("Session rotation triggered")
            await self.create_new_session()

        self.session_request_count += 1
        return self.current_session

    def _should_rotate_session(self) -> bool:
        """Check if session should be rotated."""
        if not self.current_session or not self.session_created_at:
            return True

        # Rotate if too many requests
        if self.session_request_count >= self.max_requests_per_session:
            logger.info(f"Session rotation: Max requests ({self.max_requests_per_session}) reached")
            return True

        # Rotate if session is too old
        if datetime.now() - self.session_created_at > self.session_lifetime:
            logger.info(f"Session rotation: Lifetime ({self.session_lifetime.total_seconds() / 60} min) exceeded")
            return True

        return False

    async def force_rotation(self):
        """Force immediate session rotation."""
        logger.info("Forcing session rotation")
        await self.create_new_session()

    async def close(self):
        """Close current session."""
        if self.current_session:
            try:
                await self.current_session.close()
                logger.info("Session closed")
            except Exception as e:
                logger.debug(f"Error closing session: {e}")

    def get_stats(self) -> Dict:
        """Get session statistics."""
        return {
            'total_sessions_created': self.total_sessions_created,
            'current_session_requests': self.session_request_count,
            'current_session_age_minutes': (datetime.now() - self.session_created_at).total_seconds() / 60 if self.session_created_at else 0,
            'max_requests_per_session': self.max_requests_per_session,
            'session_lifetime_minutes': self.session_lifetime.total_seconds() / 60
        }
