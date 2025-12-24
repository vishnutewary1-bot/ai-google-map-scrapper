"""Error handling and retry logic for scraping operations."""
import asyncio
from typing import Callable, Any, Optional
from functools import wraps
from loguru import logger
import traceback


class RetryableError(Exception):
    """Exception that should trigger a retry."""
    pass


class FatalError(Exception):
    """Exception that should not be retried."""
    pass


async def retry_async(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 5.0,
    exponential_backoff: bool = True,
    on_error: Optional[Callable] = None,
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        exponential_backoff: Use exponential backoff
        on_error: Callback function to call on error
        *args, **kwargs: Arguments to pass to func

    Returns:
        Result of func if successful

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if attempt > 0:
                logger.success(f"Retry succeeded on attempt {attempt + 1}")
            return result

        except FatalError as e:
            logger.error(f"Fatal error encountered, not retrying: {e}")
            raise

        except Exception as e:
            last_exception = e

            if attempt < max_retries:
                # Calculate delay with exponential backoff
                if exponential_backoff:
                    delay = base_delay * (2 ** attempt)
                else:
                    delay = base_delay

                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )

                # Call error callback if provided
                if on_error:
                    try:
                        await on_error(e, attempt)
                    except Exception as callback_error:
                        logger.error(f"Error callback failed: {callback_error}")

                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")

    # All retries exhausted
    if last_exception:
        raise last_exception


def async_retry(max_retries: int = 3, base_delay: float = 5.0, exponential_backoff: bool = True):
    """
    Decorator for retrying async functions.

    Usage:
        @async_retry(max_retries=3, base_delay=5.0)
        async def my_function():
            # Your code here
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                exponential_backoff=exponential_backoff,
                **kwargs
            )
        return wrapper
    return decorator


class ErrorRecovery:
    """Handles error recovery strategies for scraping."""

    def __init__(self):
        self.error_counts = {}
        self.recovery_strategies = {}

    def register_strategy(self, error_type: type, strategy: Callable):
        """Register a recovery strategy for a specific error type."""
        self.recovery_strategies[error_type] = strategy
        logger.info(f"Registered recovery strategy for {error_type.__name__}")

    async def handle_error(self, error: Exception, context: dict = None) -> bool:
        """
        Handle an error with registered recovery strategy.

        Returns:
            True if recovery was successful, False otherwise
        """
        error_type = type(error)
        error_name = error_type.__name__

        # Track error count
        self.error_counts[error_name] = self.error_counts.get(error_name, 0) + 1

        logger.error(f"Handling error: {error_name} (count: {self.error_counts[error_name]})")
        logger.debug(f"Error details: {error}")
        logger.debug(f"Traceback: {traceback.format_exc()}")

        # Try specific recovery strategy
        if error_type in self.recovery_strategies:
            try:
                logger.info(f"Attempting recovery with strategy for {error_name}")
                success = await self.recovery_strategies[error_type](error, context)
                if success:
                    logger.success(f"Recovery successful for {error_name}")
                    return True
                else:
                    logger.warning(f"Recovery failed for {error_name}")
                    return False
            except Exception as recovery_error:
                logger.error(f"Recovery strategy failed: {recovery_error}")
                return False

        # Try parent class strategies
        for registered_type, strategy in self.recovery_strategies.items():
            if isinstance(error, registered_type):
                try:
                    logger.info(f"Attempting recovery with parent strategy: {registered_type.__name__}")
                    success = await strategy(error, context)
                    if success:
                        logger.success(f"Recovery successful with parent strategy")
                        return True
                except Exception as recovery_error:
                    logger.error(f"Parent recovery strategy failed: {recovery_error}")

        logger.warning(f"No recovery strategy available for {error_name}")
        return False

    def get_error_stats(self) -> dict:
        """Get error statistics."""
        return {
            'error_counts': self.error_counts.copy(),
            'total_errors': sum(self.error_counts.values()),
            'registered_strategies': [t.__name__ for t in self.recovery_strategies.keys()]
        }

    def reset_stats(self):
        """Reset error statistics."""
        self.error_counts.clear()
        logger.info("Error statistics reset")


# Global error recovery instance
error_recovery = ErrorRecovery()


# Common recovery strategies
async def timeout_recovery(error: Exception, context: dict = None):
    """Recovery strategy for timeout errors."""
    logger.info("Timeout recovery: waiting 30 seconds before retry")
    await asyncio.sleep(30)
    return True


async def connection_recovery(error: Exception, context: dict = None):
    """Recovery strategy for connection errors."""
    logger.info("Connection recovery: waiting 60 seconds before retry")
    await asyncio.sleep(60)
    return True


async def captcha_recovery(error: Exception, context: dict = None):
    """Recovery strategy for CAPTCHA detection."""
    logger.error("CAPTCHA detected! Manual intervention may be required.")
    logger.info("Entering extended cooldown (5 minutes)")
    await asyncio.sleep(300)  # 5 minutes
    return True


# Register default strategies
error_recovery.register_strategy(asyncio.TimeoutError, timeout_recovery)
error_recovery.register_strategy(ConnectionError, connection_recovery)
