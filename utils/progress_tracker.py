"""Progress tracking for background tasks."""
from typing import Dict, Optional, Any
from datetime import datetime

from utils.cache_manager import cache_manager
from constants import (
    CACHE_NAMESPACE_PROGRESS,
    TASK_STATUS_PENDING,
    TASK_STATUS_IN_PROGRESS,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)


class ProgressTracker:
    """Tracks progress of background tasks using cache manager."""
    
    def __init__(self):
        self.namespace = CACHE_NAMESPACE_PROGRESS

    def initialize_progress(self, task_id: str, total_items: int, description: str = "") -> None:
        """Initialize progress tracking for a task."""
        progress_data: Dict[str, Any] = {
            'task_id': task_id,
            'description': description,
            'total_items': total_items,
            'completed_items': 0,
            'current_item_details': '',  # e.g., "Processing video 'Title X'"
            'status': TASK_STATUS_PENDING,
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'errors': [], # List of errors encountered
            'result': None # To store final result upon completion
        }
        cache_manager.set_cached_data(self.namespace, task_id, progress_data)

    def update_progress(self, task_id: str, completed_increment: int = 1, current_item_details: Optional[str] = None, item_error: Optional[str] = None) -> None:
        """Update progress for a task."""
        progress_data = cache_manager.get_cached_data(self.namespace, task_id)
        if not progress_data:
            return

        progress_data['status'] = TASK_STATUS_IN_PROGRESS
        progress_data['completed_items'] += completed_increment
        
        if current_item_details is not None:
            progress_data['current_item_details'] = current_item_details
        
        progress_data['last_update'] = datetime.now().isoformat()
        
        if item_error:
            progress_data['errors'].append({
                'item_details': current_item_details or "Unknown item",
                'error': item_error,
                'timestamp': datetime.now().isoformat()
            })
            
        cache_manager.set_cached_data(self.namespace, task_id, progress_data)

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a task."""
        return cache_manager.get_cached_data(self.namespace, task_id)

    def _update_task_status(self, task_id: str, status: str, result: Optional[Any] = None, error_message: Optional[str] = None) -> None:
        progress_data = cache_manager.get_cached_data(self.namespace, task_id)
        if not progress_data:
            progress_data = {
                'task_id': task_id, 'status': status, 'last_update': datetime.now().isoformat(),
                'errors': [], 'total_items': 0, 'completed_items': 0
            }

        progress_data['status'] = status
        progress_data['last_update'] = datetime.now().isoformat()
        
        if result is not None:
            progress_data['result'] = result
        
        if error_message:
             progress_data['errors'].append({
                'item_details': "Overall task",
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            })
        
        cache_manager.set_cached_data(self.namespace, task_id, progress_data)

    def mark_task_completed(self, task_id: str, result: Any) -> None:
        """Mark a task as completed and store its result."""
        self._update_task_status(task_id, TASK_STATUS_COMPLETED, result=result)

    def mark_task_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        self._update_task_status(task_id, TASK_STATUS_FAILED, error_message=error)

    def cleanup_progress(self, task_id: str) -> None:
        """Clean up progress data for a task."""
        cache_manager.delete_cached_data(self.namespace, task_id)

progress_tracker = ProgressTracker() 