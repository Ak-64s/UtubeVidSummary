"""Video controller for handling video processing operations."""
import logging
from typing import Dict, Optional, Any

from models.video_model import VideoModel, VideoModelError
from utils.progress_tracker import ProgressTracker
from constants import (
    MAX_CUSTOM_PROMPT_LENGTH,
    ERROR_INVALID_URL,
    ERROR_INVALID_PROMPT,
    ERROR_PROMPT_TOO_LONG,
    ERROR_INVALID_YOUTUBE_URL,
)

logger = logging.getLogger(__name__)


class VideoControllerError(Exception):
    """Custom exception for Video Controller related errors."""
    pass

class VideoController:
    def __init__(self):
        try:
            self.video_model = VideoModel()
        except VideoModelError as e: 
            logger.error(f"Error initializing VideoModel: {str(e)}")
            raise VideoControllerError(f"Failed to initialize video services: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error initializing VideoModel: {str(e)}")
            raise VideoControllerError(f"Unexpected error initializing video services: {str(e)}")

    def _build_video_data(self, video_id: str, title: str, url: str, transcript: Optional[str] = None, summary: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "id": video_id,
            "title": title,
            "url": url,
            "transcript": transcript,
            "summary_markdown": summary,
            "error": error
        }

    def _validate_input(self, url: str, custom_prompt: Optional[str] = None) -> None:
        """Validates input parameters."""
        if not url or not isinstance(url, str):
            raise VideoControllerError(ERROR_INVALID_URL)
        
        if custom_prompt is not None:
            if not isinstance(custom_prompt, str):
                raise VideoControllerError(ERROR_INVALID_PROMPT)
            if len(custom_prompt) > MAX_CUSTOM_PROMPT_LENGTH:
                raise VideoControllerError(ERROR_PROMPT_TOO_LONG)

    def process_video(self, video_id: str, custom_prompt: Optional[str] = None, start_time: Optional[float] = None, end_time: Optional[float] = None) -> Dict[str, Any]:
        """Process a single video with optional timestamp filtering."""
        try:
            
            transcript, video_info = self.video_model.fetch_transcript_with_info(video_id, start_time, end_time)
            
            title = video_info.get('title', f"Video {video_id}")
            url = video_info.get('webpage_url', video_info.get('url', f"https://www.youtube.com/watch?v={video_id}"))
            
            summary = None
            if transcript:
                summary = self.video_model.summarize_text(transcript, custom_prompt)
            
            video_data = self._build_video_data(video_id, title, url, transcript, summary)
            
            return {
                "is_playlist": False,
                "playlist_title": None,
                "videos": [video_data]
            }

        except (VideoModelError, VideoControllerError) as e:
            logger.error(f"Error processing video {video_id}: {str(e)}")
            video_data = self._build_video_data(video_id, f"Video {video_id}", f"https://www.youtube.com/watch?v={video_id}", error=str(e))
        
            return {
                "is_playlist": False,
                "playlist_title": None,
                "videos": [video_data]
            }

    def process_video_or_playlist(
        self, 
        url: str, 
        custom_prompt: Optional[str] = None,
        task_id: Optional[str] = None, 
        progress_tracker_instance: Optional[ProgressTracker] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Processes a YouTube video or playlist.
        Returns a structured dictionary with results.
        If task_id and progress_tracker_instance are provided, updates progress.
        """
        try:
            self._validate_input(url, custom_prompt)
            
            if not self.video_model.is_valid_youtube_url(url):
                raise VideoControllerError(ERROR_INVALID_YOUTUBE_URL)
            
            video_id = self.video_model.extract_video_id(url)
            return self.process_video(video_id, custom_prompt, start_time, end_time)
        
        except VideoControllerError as e:
            logger.error(f"Controller error processing URL '{url}': {str(e)}")
            if task_id and progress_tracker_instance:
                progress_tracker_instance.mark_task_failed(task_id, str(e))
            return {"error": str(e), "videos": []}
        except VideoModelError as e: 
            logger.error(f"Video model error processing URL '{url}': {str(e)}")
            if task_id and progress_tracker_instance:
                progress_tracker_instance.mark_task_failed(task_id, str(e))
            return {"error": str(e), "videos": []}
        except Exception as e:
            logger.error(f"Unexpected error processing URL '{url}': {str(e)}")
            if task_id and progress_tracker_instance:
                progress_tracker_instance.mark_task_failed(task_id, f"An unexpected error occurred: {str(e)}")
            return {"error": "An unexpected error occurred during processing.", "videos": []}
