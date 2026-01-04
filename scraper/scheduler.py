"""Scheduled/Automated scraping module using APScheduler."""
import asyncio
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta
from loguru import logger

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.executors.asyncio import AsyncIOExecutor
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

from database import db_manager, ScrapeJob


class ScheduledTask:
    """Represents a scheduled scraping task."""

    def __init__(
        self,
        task_id: str,
        search_query: str,
        location: Optional[str] = None,
        max_results: int = 100,
        schedule_type: str = "interval",  # "interval", "cron", "once"
        interval_hours: int = 24,
        cron_expression: Optional[str] = None,
        run_at: Optional[datetime] = None,
        enabled: bool = True,
        extract_emails: bool = False,
        notify_on_complete: bool = True,
        webhook_url: Optional[str] = None
    ):
        self.task_id = task_id
        self.search_query = search_query
        self.location = location
        self.max_results = max_results
        self.schedule_type = schedule_type
        self.interval_hours = interval_hours
        self.cron_expression = cron_expression
        self.run_at = run_at
        self.enabled = enabled
        self.extract_emails = extract_emails
        self.notify_on_complete = notify_on_complete
        self.webhook_url = webhook_url
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.last_result = None

    def to_dict(self) -> Dict:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "search_query": self.search_query,
            "location": self.location,
            "max_results": self.max_results,
            "schedule_type": self.schedule_type,
            "interval_hours": self.interval_hours,
            "cron_expression": self.cron_expression,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "enabled": self.enabled,
            "extract_emails": self.extract_emails,
            "notify_on_complete": self.notify_on_complete,
            "webhook_url": self.webhook_url,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "last_result": self.last_result
        }


class ScrapeScheduler:
    """
    Scheduler for automated scraping tasks.
    Supports interval-based, cron-based, and one-time scheduled tasks.
    """

    def __init__(self):
        if not SCHEDULER_AVAILABLE:
            raise ImportError("APScheduler is required. Install with: pip install apscheduler")

        self.scheduler = AsyncIOScheduler(
            jobstores={'default': MemoryJobStore()},
            executors={'default': AsyncIOExecutor()},
            job_defaults={
                'coalesce': True,  # Combine missed runs
                'max_instances': 1,  # Only one instance at a time
                'misfire_grace_time': 3600  # 1 hour grace period
            }
        )

        self.tasks: Dict[str, ScheduledTask] = {}
        self.scrape_callback: Optional[Callable] = None
        self.notification_callback: Optional[Callable] = None
        self._running = False

    def set_scrape_callback(self, callback: Callable):
        """Set the callback function for executing scrapes."""
        self.scrape_callback = callback

    def set_notification_callback(self, callback: Callable):
        """Set the callback function for notifications."""
        self.notification_callback = callback

    def start(self):
        """Start the scheduler."""
        if not self._running:
            self.scheduler.start()
            self._running = True
            logger.info("Scrape scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scrape scheduler stopped")

    def add_task(self, task: ScheduledTask) -> bool:
        """
        Add a scheduled scraping task.

        Args:
            task: ScheduledTask configuration

        Returns:
            True if task was added successfully
        """
        try:
            if task.task_id in self.tasks:
                logger.warning(f"Task {task.task_id} already exists. Use update_task() instead.")
                return False

            # Create the appropriate trigger
            if task.schedule_type == "interval":
                trigger = IntervalTrigger(hours=task.interval_hours)
            elif task.schedule_type == "cron":
                if not task.cron_expression:
                    logger.error("Cron expression required for cron schedule type")
                    return False
                trigger = CronTrigger.from_crontab(task.cron_expression)
            elif task.schedule_type == "once":
                if not task.run_at:
                    logger.error("run_at datetime required for one-time schedule")
                    return False
                trigger = DateTrigger(run_date=task.run_at)
            else:
                logger.error(f"Invalid schedule type: {task.schedule_type}")
                return False

            # Add job to scheduler
            job = self.scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=task.task_id,
                name=f"Scrape: {task.search_query}",
                args=[task.task_id],
                replace_existing=True
            )

            # Store task
            self.tasks[task.task_id] = task
            task.next_run = job.next_run_time

            logger.info(f"Added scheduled task: {task.task_id} (next run: {task.next_run})")
            return True

        except Exception as e:
            logger.error(f"Error adding scheduled task: {e}")
            return False

    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        try:
            if task_id not in self.tasks:
                logger.warning(f"Task {task_id} not found")
                return False

            self.scheduler.remove_job(task_id)
            del self.tasks[task_id]
            logger.info(f"Removed scheduled task: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing task: {e}")
            return False

    def update_task(self, task_id: str, updates: Dict) -> bool:
        """Update a scheduled task."""
        try:
            if task_id not in self.tasks:
                logger.warning(f"Task {task_id} not found")
                return False

            task = self.tasks[task_id]

            # Update task properties
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)

            # Remove and re-add to apply schedule changes
            self.scheduler.remove_job(task_id)
            self.tasks.pop(task_id)
            self.add_task(task)

            logger.info(f"Updated scheduled task: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating task: {e}")
            return False

    def pause_task(self, task_id: str) -> bool:
        """Pause a scheduled task."""
        try:
            if task_id not in self.tasks:
                return False

            self.scheduler.pause_job(task_id)
            self.tasks[task_id].enabled = False
            logger.info(f"Paused task: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error pausing task: {e}")
            return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        try:
            if task_id not in self.tasks:
                return False

            self.scheduler.resume_job(task_id)
            self.tasks[task_id].enabled = True

            # Update next run time
            job = self.scheduler.get_job(task_id)
            if job:
                self.tasks[task_id].next_run = job.next_run_time

            logger.info(f"Resumed task: {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error resuming task: {e}")
            return False

    def run_task_now(self, task_id: str) -> bool:
        """Execute a task immediately (in addition to its schedule)."""
        try:
            if task_id not in self.tasks:
                return False

            # Trigger job immediately
            job = self.scheduler.get_job(task_id)
            if job:
                asyncio.create_task(self._execute_task(task_id))
                logger.info(f"Triggered immediate run of task: {task_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error running task: {e}")
            return False

    async def _execute_task(self, task_id: str):
        """Execute a scheduled scraping task."""
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        logger.info(f"Executing scheduled task: {task_id}")
        task.last_run = datetime.now()
        task.run_count += 1

        try:
            if self.scrape_callback:
                # Execute the scrape
                result = await self.scrape_callback(
                    search_query=task.search_query,
                    location=task.location,
                    max_results=task.max_results,
                    extract_emails=task.extract_emails
                )

                task.last_result = {
                    "success": True,
                    "leads_scraped": result.get("leads_scraped", 0),
                    "timestamp": datetime.now().isoformat()
                }

                logger.success(f"Task {task_id} completed: {result.get('leads_scraped', 0)} leads")

                # Send notification if enabled
                if task.notify_on_complete and self.notification_callback:
                    await self.notification_callback(
                        task=task,
                        result=result,
                        webhook_url=task.webhook_url
                    )

            else:
                logger.warning("No scrape callback set")
                task.last_result = {"success": False, "error": "No callback configured"}

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            task.last_result = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

        # Update next run time
        job = self.scheduler.get_job(task_id)
        if job:
            task.next_run = job.next_run_time

    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a task by ID."""
        task = self.tasks.get(task_id)
        return task.to_dict() if task else None

    def list_tasks(self) -> List[Dict]:
        """List all scheduled tasks."""
        return [task.to_dict() for task in self.tasks.values()]

    def get_status(self) -> Dict:
        """Get scheduler status."""
        running_jobs = [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in self.scheduler.get_jobs()
        ]

        return {
            "running": self._running,
            "total_tasks": len(self.tasks),
            "active_tasks": len([t for t in self.tasks.values() if t.enabled]),
            "paused_tasks": len([t for t in self.tasks.values() if not t.enabled]),
            "jobs": running_jobs
        }

    def create_daily_task(
        self,
        task_id: str,
        search_query: str,
        location: Optional[str] = None,
        max_results: int = 100,
        hour: int = 9,
        minute: int = 0,
        **kwargs
    ) -> bool:
        """
        Convenience method to create a daily task.

        Args:
            task_id: Unique task identifier
            search_query: Search query for Google Maps
            location: Location to search in
            max_results: Maximum results per run
            hour: Hour to run (24-hour format)
            minute: Minute to run
        """
        cron_expr = f"{minute} {hour} * * *"
        task = ScheduledTask(
            task_id=task_id,
            search_query=search_query,
            location=location,
            max_results=max_results,
            schedule_type="cron",
            cron_expression=cron_expr,
            **kwargs
        )
        return self.add_task(task)

    def create_weekly_task(
        self,
        task_id: str,
        search_query: str,
        location: Optional[str] = None,
        max_results: int = 100,
        day_of_week: str = "mon",  # mon, tue, wed, thu, fri, sat, sun
        hour: int = 9,
        minute: int = 0,
        **kwargs
    ) -> bool:
        """
        Convenience method to create a weekly task.

        Args:
            task_id: Unique task identifier
            search_query: Search query for Google Maps
            location: Location to search in
            max_results: Maximum results per run
            day_of_week: Day of week to run (mon, tue, wed, etc.)
            hour: Hour to run (24-hour format)
            minute: Minute to run
        """
        cron_expr = f"{minute} {hour} * * {day_of_week}"
        task = ScheduledTask(
            task_id=task_id,
            search_query=search_query,
            location=location,
            max_results=max_results,
            schedule_type="cron",
            cron_expression=cron_expr,
            **kwargs
        )
        return self.add_task(task)

    def create_hourly_task(
        self,
        task_id: str,
        search_query: str,
        location: Optional[str] = None,
        max_results: int = 50,
        interval_hours: int = 1,
        **kwargs
    ) -> bool:
        """
        Convenience method to create an hourly/interval task.

        Args:
            task_id: Unique task identifier
            search_query: Search query
            location: Location to search
            max_results: Maximum results
            interval_hours: Hours between runs
        """
        task = ScheduledTask(
            task_id=task_id,
            search_query=search_query,
            location=location,
            max_results=max_results,
            schedule_type="interval",
            interval_hours=interval_hours,
            **kwargs
        )
        return self.add_task(task)


# Singleton instance
_scheduler = None

def get_scheduler() -> ScrapeScheduler:
    """Get or create the scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ScrapeScheduler()
    return _scheduler
