"""Proxy management for rotating free proxies."""
import aiohttp
import asyncio
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime, timedelta
import random


class ProxyManager:
    """Manages free proxy rotation with health checking."""

    def __init__(self):
        self.proxies: List[Dict] = []
        self.working_proxies: List[Dict] = []
        self.failed_proxies: set = set()
        self.last_refresh: Optional[datetime] = None
        self.current_proxy_index = 0

    async def fetch_free_proxies(self) -> List[Dict]:
        """Fetch free proxies from public sources."""
        logger.info("Fetching free proxies...")
        all_proxies = []

        # Source 1: Free Proxy List API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        proxies_list = text.strip().split('\n')
                        for proxy in proxies_list[:50]:  # Limit to 50
                            if proxy.strip():
                                all_proxies.append({
                                    'url': f'http://{proxy.strip()}',
                                    'ip': proxy.strip().split(':')[0],
                                    'source': 'proxyscrape'
                                })
                        logger.info(f"Fetched {len(all_proxies)} proxies from ProxyScrape")
        except Exception as e:
            logger.warning(f"Failed to fetch from ProxyScrape: {e}")

        # Source 2: Backup source
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        proxies_list = text.strip().split('\n')
                        for proxy in proxies_list[:50]:
                            if proxy.strip() and proxy.strip() not in [p['url'].replace('http://', '') for p in all_proxies]:
                                all_proxies.append({
                                    'url': f'http://{proxy.strip()}',
                                    'ip': proxy.strip().split(':')[0],
                                    'source': 'github'
                                })
                        logger.info(f"Total proxies: {len(all_proxies)}")
        except Exception as e:
            logger.warning(f"Failed to fetch from GitHub: {e}")

        self.proxies = all_proxies
        self.last_refresh = datetime.now()
        return all_proxies

    async def test_proxy(self, proxy: Dict) -> bool:
        """Test if a proxy is working."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://www.google.com',
                    proxy=proxy['url'],
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    if response.status == 200:
                        logger.debug(f"Proxy {proxy['ip']} is working")
                        return True
                    else:
                        logger.debug(f"Proxy {proxy['ip']} returned status {response.status}")
                        return False
        except Exception as e:
            logger.debug(f"Proxy {proxy['ip']} failed: {e}")
            return False

    async def refresh_working_proxies(self, max_test: int = 20):
        """Refresh the list of working proxies."""
        logger.info("Testing proxies for availability...")

        if not self.proxies or (self.last_refresh and datetime.now() - self.last_refresh > timedelta(hours=1)):
            await self.fetch_free_proxies()

        # Test random sample of proxies
        test_proxies = random.sample(self.proxies, min(max_test, len(self.proxies)))

        # Test proxies concurrently
        tasks = [self.test_proxy(proxy) for proxy in test_proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter working proxies
        self.working_proxies = [
            proxy for proxy, result in zip(test_proxies, results)
            if isinstance(result, bool) and result
        ]

        logger.info(f"Found {len(self.working_proxies)} working proxies out of {max_test} tested")

        if len(self.working_proxies) == 0:
            logger.warning("No working proxies found! Will use direct connection.")

    def get_next_proxy(self) -> Optional[Dict]:
        """Get next proxy from rotation."""
        if not self.working_proxies:
            return None

        proxy = self.working_proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.working_proxies)

        return proxy

    def mark_proxy_failed(self, proxy: Dict):
        """Mark a proxy as failed and remove from working list."""
        self.failed_proxies.add(proxy['url'])

        if proxy in self.working_proxies:
            self.working_proxies.remove(proxy)
            logger.warning(f"Removed failed proxy: {proxy['ip']}")

    def get_random_proxy(self) -> Optional[Dict]:
        """Get a random working proxy."""
        if not self.working_proxies:
            return None
        return random.choice(self.working_proxies)

    async def initialize(self):
        """Initialize proxy manager with working proxies."""
        await self.fetch_free_proxies()
        await self.refresh_working_proxies()

    def get_stats(self) -> Dict:
        """Get proxy statistics."""
        return {
            'total_proxies': len(self.proxies),
            'working_proxies': len(self.working_proxies),
            'failed_proxies': len(self.failed_proxies),
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None
        }


# Global proxy manager instance
proxy_manager = ProxyManager()
