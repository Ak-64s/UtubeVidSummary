from typing import Dict, Optional, List, Any
from datetime import datetime
import threading
from app.utils.cache_manager import cache_manager # Use the global instance

class ProgressTracker:
    def __init__(self):
        self.namespace = "progress" # Define a namespace for progress data in cache

    def initialize_progress(self, task_id: str, total_items: int, description: str = "") -> None:
        """Initialize progress tracking for a task."""
        progress_data: Dict[str, Any] = {
            'task_id': task_id,
            'description': description,
            'total_items': total_items,
            'completed_items': 0,
            'current_item_details': '', # e.g., "Processing video 'Title X'"
            'status': 'pending', # pending, in_progress, completed, failed
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
            # Or log a warning, task might not have been initialized
            return

        progress_data['status'] = 'in_progress'
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

        if progress_data['completed_items'] >= progress_data['total_items'] and progress_data['status'] != 'failed':
            # If all items are done, but no overall result set yet, don't mark completed.
            # The main task function should call mark_task_completed.
            pass
            
        cache_manager.set_cached_data(self.namespace, task_id, progress_data)

    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current progress for a task."""
        return cache_manager.get_cached_data(self.namespace, task_id)

    def _update_task_status(self, task_id: str, status: str, result: Optional[Any] = None, error_message: Optional[str] = None) -> None:
        progress_data = cache_manager.get_cached_data(self.namespace, task_id)
        if not progress_data:
            # Fallback: if not initialized, create a minimal record
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
        self._update_task_status(task_id, 'completed', result=result)

    def mark_task_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        self._update_task_status(task_id, 'failed', error_message=error)

    def cleanup_progress(self, task_id: str) -> None:
        """Clean up progress data for a task."""
        cache_manager.delete_cached_data(self.namespace, task_id)

# Global instance
progress_tracker = ProgressTracker() 