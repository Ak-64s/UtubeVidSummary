"""
Background task runner for processing video tasks asynchronously.
"""
import logging
from typing import Optional

from controllers.video_controller import VideoController, VideoControllerError
from utils.progress_tracker import progress_tracker

logger = logging.getLogger(__name__)


def background_task_runner(
    task_id: str,
    url: str,
    custom_prompt: Optional[str],
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> None:
    """
    The actual function run by the thread to process a video.
    
    Args:
        task_id: Unique identifier for the task
        url: YouTube video URL to process
        custom_prompt: Optional custom prompt for summarization
        start_time: Optional start time for video segment
        end_time: Optional end time for video segment
    """
    logger.info(f"Task {task_id}: Starting processing for URL: {url}")
    
    try:
        video_controller_instance = VideoController()
    except VideoControllerError as e:
        logger.error(f"Task {task_id}: Failed to initialize VideoController in background task: {str(e)}")
        progress_tracker.mark_task_failed(task_id, "Service initialization error.")
        return

    try:
        result = video_controller_instance.process_video_or_playlist(
            url,
            custom_prompt,
            task_id=task_id,
            progress_tracker_instance=progress_tracker,
            start_time=start_time,
            end_time=end_time,
        )

        if "error" in result and result["error"]:
            if progress_tracker.get_progress(task_id).get('status') != 'failed':
                 progress_tracker.mark_task_failed(task_id, result["error"])
        else:
            progress_tracker.mark_task_completed(task_id, result)
        
        final_status = progress_tracker.get_progress(task_id).get('status') if progress_tracker.get_progress(task_id) else 'unknown'
        logger.info(f"Task {task_id}: Finished processing. Final status: {final_status}")

    except VideoControllerError as e:
        logger.error(f"Task {task_id}: VideoControllerError during background processing: {str(e)}")
        progress_tracker.mark_task_failed(task_id, str(e))
    except Exception as e:
        logger.error(f"Task {task_id}: Unexpected error during background processing: {str(e)}")
        progress_tracker.mark_task_failed(task_id, f"An unexpected error occurred: {str(e)}") 