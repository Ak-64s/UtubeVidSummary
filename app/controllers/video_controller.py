from app.models.video_model import VideoModel, VideoModelError
import logging
from typing import Dict, Optional, List, Any
from app.utils.progress_tracker import ProgressTracker 

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
            raise VideoControllerError("Invalid URL: URL must be a non-empty string.")
        
        if custom_prompt is not None:
            if not isinstance(custom_prompt, str):
                raise VideoControllerError("Custom prompt must be a string.")
            if len(custom_prompt) > 2000:
                raise VideoControllerError("Custom prompt is too long (max 2000 characters).")

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
                raise VideoControllerError("Invalid YouTube URL provided.")

            if self.video_model.is_playlist_url(url):
                return self._process_playlist(url, custom_prompt, task_id, progress_tracker_instance, start_time, end_time)
            
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


    def _process_playlist(
        self, 
        url: str, 
        custom_prompt: Optional[str] = None,
        task_id: Optional[str] = None,
        progress_tracker_instance: Optional[ProgressTracker] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        """Processes a YouTube playlist and returns structured data using sequential processing."""
        playlist_results: List[Dict[str, Any]] = []
        
        try:
            playlist_info = self.video_model.get_playlist_info(url)
            video_ids = playlist_info["video_ids"]
            playlist_title = playlist_info["playlist_title"]

            if not video_ids:
                raise VideoControllerError("No videos found in the playlist.")

            if task_id and progress_tracker_instance:
                progress_tracker_instance.initialize_progress(task_id, total_items=len(video_ids), description=f"Processing playlist: {playlist_title} ({len(video_ids)} videos)")

            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            
            max_workers = min(3, len(video_ids))  
            
            def process_single_video(video_id, index):
                try:
                    result = self.process_video(video_id, custom_prompt, start_time, end_time)
                    video_data = result["videos"][0]
                    logger.info(f"Successfully processed video {index+1}/{len(video_ids)}: {video_data.get('title', video_id)}")
                    return index, video_data
                except Exception as e:
                 
                    video_data = self._build_video_data(video_id, f"Video {video_id}", f"https://www.youtube.com/watch?v={video_id}", error=str(e))
                    logger.error(f"Failed to process video {index+1}/{len(video_ids)} ({video_id}): {str(e)}")
                    return index, video_data
            
            playlist_results = [None] * len(video_ids)
            completed_count = 0
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
           
                future_to_index = {
                    executor.submit(process_single_video, video_id, i): i 
                    for i, video_id in enumerate(video_ids)
                }
                
                for future in as_completed(future_to_index):
                    try:
                        index, video_data = future.result()
                        playlist_results[index] = video_data
                        completed_count += 1
                        
                        if task_id and progress_tracker_instance:
                            progress_tracker_instance.update_progress(
                                task_id, 
                                completed_increment=1, 
                                current_item_details=f"Processed {completed_count}/{len(video_ids)} videos", 
                                item_error=video_data.get("error")
                            )
                    except Exception as e:
                        logger.error(f"Error in parallel processing: {str(e)}")
                        continue
            
            return {
                "is_playlist": True,
                "playlist_title": playlist_title,
                "videos": playlist_results
            }

        except VideoModelError as e: 
            logger.error(f"Error processing playlist '{url}': {str(e)}")
            if task_id and progress_tracker_instance:
                progress_tracker_instance.mark_task_failed(task_id, str(e)) 
            return {"is_playlist": True, "playlist_title": playlist_title, "videos": [], "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error processing playlist '{url}': {str(e)}")
            if task_id and progress_tracker_instance:
                progress_tracker_instance.mark_task_failed(task_id, "An unexpected error occurred with the playlist.")
            return {"is_playlist": True, "playlist_title": playlist_title, "videos": [], "error": "An unexpected error occurred with the playlist."} 
