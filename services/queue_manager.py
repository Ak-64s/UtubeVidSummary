"""
Queue manager for handling background task processing.
Supports both Redis-based queuing and synchronous threading for local development.
"""
import os
import threading
import logging
from typing import Any, Callable
try:
    import rq  # type: ignore
    _rq_available = True
except ImportError:
    rq = None  # type: ignore
    _rq_available = False

logger = logging.getLogger(__name__)


class SyncQueue:
    """
    Synchronous queue implementation using threading for local development.
    Falls back when Redis is not available.
    """
    
    def enqueue(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        """
        Enqueue a function to run in a separate thread.
        
        Args:
            func: The function to execute
            *args: Positional arguments (captured from kwargs['args'] if present)
            **kwargs: Keyword arguments (job_id is ignored for sync execution)
        """
        func_args = kwargs.pop('args', args)
        kwargs.pop('job_id', None)  # Not used in sync mode
        thread = threading.Thread(target=func, args=func_args, kwargs=kwargs)
        thread.start()


def create_queue() -> Any:
    """
    Create and return the appropriate queue instance based on environment configuration.
    
    Returns:
        rq.Queue instance if Redis is configured, otherwise SyncQueue instance
    """
    use_redis = os.getenv('USE_REDIS', 'false').lower() == 'true'
    
    if use_redis:
        if not _rq_available:
            logger.warning(
                "USE_REDIS is enabled but the 'rq' package is not installed. "
                "Falling back to synchronous execution. Add 'rq' to requirements if Redis queues are required."
            )
            use_redis = False

    if use_redis:
        try:
            import redis
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            redis_conn = redis.from_url(redis_url)
            queue = rq.Queue(connection=redis_conn)
            logger.info(f"Using Redis for task queue at {redis_url}")
            return queue
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis: {e}. "
                "Falling back to synchronous execution."
            )
    
    logger.info("Using non-blocking synchronous execution for local development.")
    return SyncQueue()
