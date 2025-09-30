"""Video model for handling YouTube video data and processing."""
import os
import time
import random
import logging
import threading
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Optional, Any, Tuple

import requests
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from config import config
from utils.cache_manager import cache_manager
from constants import (
    YOUTUBE_DOMAINS,
    CACHE_TTL_TRANSCRIPT,
    CACHE_TTL_VIDEO_INFO,
    CACHE_TTL_VIDEO_INFO_FALLBACK,
    CACHE_NAMESPACE_TRANSCRIPTS,
    DEFAULT_TRANSCRIPT_LANGUAGES,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    ERROR_INVALID_VIDEO_ID,
)

logger = logging.getLogger(__name__)

class VideoModelError(Exception):
    """Custom exception for Video Model related errors."""
    pass

class VideoModel:
    def __init__(self):
        if not config.GEMINI_API_KEYS:
            raise VideoModelError(
                "No API keys found. Please set at least one of GOOGLE_API_KEY, GEMINI_API_KEY, "
                "API_KEY, API_KEY1, or API_KEY2 in your environment."
            )
        self.api_keys = config.GEMINI_API_KEYS
        self.current_api_key_index = 0
        self.model = None
        self._configure_gemini_api()

        self.cache_namespace_transcripts = CACHE_NAMESPACE_TRANSCRIPTS
        self.preferred_languages: List[str] = list(dict.fromkeys(
            config.TRANSCRIPT_PREFERRED_LANGUAGES or DEFAULT_TRANSCRIPT_LANGUAGES
        ))

    def _get_next_api_key(self):
        """Rotates to the next API key."""
        self.current_api_key_index = (self.current_api_key_index + 1) % len(self.api_keys)
        logger.info(f"Switching to API key index: {self.current_api_key_index}")
        return self.api_keys[self.current_api_key_index]

    def _configure_gemini_api(self) -> None:
        """Configures the Gemini API with the current key."""
        try:
            api_key = self.api_keys[self.current_api_key_index]
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name='gemini-2.5-flash')
            logger.info(f"Gemini API configured successfully with key index: {self.current_api_key_index}")
        except Exception as e:
            logger.error(f"Error configuring Gemini API with key index {self.current_api_key_index}: {str(e)}")
            self.model = None

    def _validate_url(self, url: str) -> bool:
        """Validates if the URL is a valid YouTube URL."""
        if not url or not isinstance(url, str):
            return False
        parsed_url = urlparse(url)
        return parsed_url.netloc in YOUTUBE_DOMAINS

    def extract_video_id(self, url: str) -> str:
        """Extracts video ID from a YouTube URL."""
        if not self._validate_url(url):
            raise VideoModelError("Invalid YouTube URL format")
        try:
            if "youtu.be" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0].split("/")[0]
                if not video_id:
                    raise VideoModelError("Could not extract video ID from youtu.be URL")
                return video_id
            parsed_url = urlparse(url)
            if parsed_url.netloc in ["www.youtube.com", "youtube.com"]:
                if "/live/" in parsed_url.path:
                    video_id = parsed_url.path.split("/live/")[1].split("/")[0]
                    if not video_id:
                        raise VideoModelError("Could not extract video ID from live URL")
                    return video_id
                video_id = parse_qs(parsed_url.query).get('v')
                if not video_id:
                    raise VideoModelError("No video ID found in URL")
                return video_id[0]
            raise VideoModelError("Unsupported YouTube URL format")
        except Exception as e:
            logger.error(f"Error extracting video ID: {str(e)}")
            raise VideoModelError(f"Failed to extract video ID: {str(e)}")

    def extract_playlist_id(self, url: str) -> Optional[str]:
        return None

    def is_valid_youtube_url(self, url: str) -> bool:
        return self._validate_url(url)

    def is_playlist_url(self, url: str) -> bool:
        return False

    def _retry_with_backoff(
        self,
        func,
        max_retries: int = MAX_RETRIES,
        base_delay: float = RETRY_BASE_DELAY,
        errors_to_retry: Tuple = (Exception,)
    ):
        """Retry a function with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return func()
            except errors_to_retry as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Final attempt failed. Error: {str(e)}. No more retries."
                    )
                    raise e
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed with error: {str(e)}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                time.sleep(delay)

    def _time_to_seconds(self, time_str: str) -> float:
        """Converts HH:MM:SS,ms or HH:MM:SS.ms format to seconds."""
        time_str = time_str.strip().replace(',', '.')
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h, m, s_ms = parts
            elif len(parts) == 2:
                h = 0
                m, s_ms = parts
            else:
                return 0.0

            s, ms = (s_ms.split('.') + ['0'])[:2]
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
        except ValueError:
            logger.error(f"Could not parse timestamp: {time_str}")
            return 0.0

    def fetch_transcript_with_info(self, video_id: str, start_time: Optional[float] = None, end_time: Optional[float] = None) -> tuple:
        """Fetches both transcript and video info efficiently, using cache."""
        if not video_id or not isinstance(video_id, str):
            raise VideoModelError("Invalid video ID")

        transcript_cache_key = video_id
        info_cache_key = f"info_{video_id}"
        slice_key = None
        if start_time is not None or end_time is not None:
            start_key = int(start_time) if isinstance(start_time, (int, float)) else None
            end_key = int(end_time) if isinstance(end_time, (int, float)) else None
            slice_key = f"slice_{video_id}_{start_key if start_key is not None else 'None'}_{end_key if end_key is not None else 'None'}"

        cached_transcript = cache_manager.get_cached_data(self.cache_namespace_transcripts, transcript_cache_key)
        cached_info = cache_manager.get_cached_data(self.cache_namespace_transcripts, info_cache_key)
        cached_slice = cache_manager.get_cached_data(self.cache_namespace_transcripts, slice_key) if slice_key else None

        if cached_slice and cached_info:
            logger.info(f"Transcript slice and info for video {video_id} served from cache.")
            return cached_slice, cached_info

        if cached_transcript and cached_info:
            filtered_transcript = self._filter_transcript_by_time(cached_transcript, start_time, end_time)
            if slice_key and filtered_transcript:
                cache_manager.set_cached_data(
                    self.cache_namespace_transcripts,
                    slice_key,
                    filtered_transcript,
                    ttl_seconds=getattr(config, 'TRANSCRIPT_SLICE_TTL_SECONDS', 86400)
                )
            return filtered_transcript, cached_info
        
        transcript_data = cached_transcript
        video_info = cached_info
        info_thread = None
        info_result: Dict[str, Any] = {"value": video_info}
        if not video_info:
            def _fetch_info():
                try:
                    info_result["value"] = self.get_video_info(video_id)
                    cache_manager.set_cached_data(self.cache_namespace_transcripts, info_cache_key, info_result["value"], ttl_seconds=3600*24)
                except Exception as e:
                    logger.warning(f"Failed to fetch video info for {video_id}: {str(e)}")
            info_thread = threading.Thread(target=_fetch_info, daemon=True)
            info_thread.start()

        # Fetch transcript if not cached
        if not transcript_data:
            # Respect config flag to control API-first strategy
            if config.USE_YOUTUBE_TRANSCRIPT_API:
                try:
                    transcript_data = self._retry_with_backoff(lambda: self._fetch_transcript_from_api(video_id))
                    if transcript_data:
                        logger.info(f"Successfully fetched transcript for video {video_id} using YouTube Transcript API.")
                    else:
                        logger.warning(f"YouTube Transcript API returned no data for video {video_id}. Falling back to yt-dlp.")
                except Exception as e:
                    logger.warning(f"YouTube Transcript API failed for video {video_id}: {str(e)}. Falling back to yt-dlp.")
                    transcript_data = None
            else:
                logger.info("USE_YOUTUBE_TRANSCRIPT_API is disabled; attempting yt-dlp for transcripts.")

            # If API path failed, no yt-dlp fallback available anymore
            if not transcript_data:
                raise VideoModelError(f"Failed to fetch transcript for {video_id}")
            
            # Cache transcript for 30 days (including structured subtitles with start times)
            cache_manager.set_cached_data(
                self.cache_namespace_transcripts,
                transcript_cache_key,
                transcript_data,
                ttl_seconds=30 * 24 * 3600
            )
        
        # Wait for video info thread if started
        if info_thread is not None:
            info_thread.join()
            video_info = info_result.get('value')
            if not video_info:
                # Provide fallback info and cache briefly
                video_info = {
                    'id': video_id,
                    'title': f'Video {video_id}',
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'duration': 0
                }
                cache_manager.set_cached_data(self.cache_namespace_transcripts, info_cache_key, video_info, ttl_seconds=300)
        
        filtered_transcript = self._filter_transcript_by_time(transcript_data, start_time, end_time)
        # Cache the slice if interval requested
        if slice_key and filtered_transcript:
            cache_manager.set_cached_data(
                self.cache_namespace_transcripts,
                slice_key,
                filtered_transcript,
                ttl_seconds=getattr(config, 'TRANSCRIPT_SLICE_TTL_SECONDS', 86400)
            )
        return filtered_transcript, video_info

    def fetch_transcript(
        self,
        video_id: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> str:
        """Fetches the transcript for a given YouTube video ID, using cache."""
        transcript, _ = self.fetch_transcript_with_info(video_id, start_time, end_time)
        return transcript

    def _fetch_transcript_from_api(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches and processes transcript using youtube-transcript-api with version fallbacks."""
        
        def process_transcript_data(transcript_data):
            if not transcript_data:
                return None
            processed_data = []
            for entry in transcript_data:
                try:
                    processed_data.append({'text': entry['text'], 'start': entry['start']})
                except Exception:
                    continue
            return processed_data if processed_data else None

        # First try instance API (newer library variants)
        try:
            ytt = YouTubeTranscriptApi()
            fetch_method = getattr(ytt, 'fetch', None)
            if callable(fetch_method):
                try:
                    # Prefer explicit language priorities
                    result = fetch_method(video_id, languages=self.preferred_languages)
                except TypeError:
                    # Some versions don't support languages kwarg
                    result = fetch_method(video_id)

                try:
                    raw_data = result.to_raw_data()  # type: ignore[attr-defined]
                except Exception:
                    raw_data = result

                processed = process_transcript_data(raw_data)
                if processed:
                    return processed
        except Exception as e:
            logger.warning(f"Instance API fetch failed for {video_id}: {e}")

        # Prefer using list_transcripts when available (newer versions)
        try:
            list_method = getattr(YouTubeTranscriptApi, 'list_transcripts', None)
            if callable(list_method):
                transcript_list = list_method(video_id)
                # Prefer configured languages in order
                for lang in self.preferred_languages:
                    try:
                        transcript = transcript_list.find_transcript([lang])
                        return process_transcript_data(transcript.fetch())
                    except (TranscriptsDisabled, NoTranscriptFound):
                        continue

                # Try generated transcript in preferred languages
                for lang in self.preferred_languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        return process_transcript_data(transcript.fetch())
                    except (TranscriptsDisabled, NoTranscriptFound):
                        continue

                # Fallback to any available transcript and translate if possible
                for transcript in transcript_list:
                    try:
                        return process_transcript_data(transcript.fetch())
                    except Exception as e:
                        logger.warning(f"Could not fetch or process transcript for language '{getattr(transcript, 'language_code', '?')}': {e}")
                        continue

                raise VideoModelError("No usable transcripts found via YouTubeTranscriptApi")
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            # Continue to get_transcript fallback below
            logger.warning(f"list_transcripts path failed for {video_id}: {e}")
        except AttributeError:
            # Older version without list_transcripts; fall through to get_transcript
            pass
        except Exception as e:
            # Any other issue, try get_transcript path below
            logger.warning(f"list_transcripts encountered an error for {video_id}: {e}")

        # Fallback path for older versions: try get_transcript with language preferences
        language_attempts: List[List[str]] = [[lang] for lang in self.preferred_languages]
        language_attempts.append(self.preferred_languages)
        for lang_list in language_attempts:
            try:
                data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_list)
                result = process_transcript_data(data)
                if result:
                    return result
            except (TranscriptsDisabled, NoTranscriptFound):
                continue
            except Exception as e:
                logger.warning(f"get_transcript failed for {video_id} with languages {lang_list}: {e}")
                continue

        raise VideoModelError("No usable transcripts found via YouTubeTranscriptApi (fallback path)")

    def _filter_transcript_by_time(self, transcript_data, start_time: Optional[float] = None, end_time: Optional[float] = None) -> str:
        """Filter transcript data based on start and end times, then return as text."""
        if not transcript_data:
            return ""
        
        if isinstance(transcript_data, str):
            logger.warning("Cannot apply timestamp filtering to yt-dlp transcript (no timestamp data available)")
            return transcript_data
        
        filtered_entries = [entry['text'] for entry in transcript_data if (start_time is None or entry.get('start', 0) >= start_time) and (end_time is None or entry.get('start', 0) <= end_time)]
        
        result_text = " ".join(filtered_entries)
        
        if start_time is not None or end_time is not None:
            logger.info(f"Filtered transcript: {len(filtered_entries)} entries out of {len(transcript_data)} total entries")
        
        return result_text

    # yt-dlp transcript fallback removed entirely

    def summarize_text(self, text: str, custom_prompt: Optional[str] = None) -> str:
        """Summarizes text using Gemini API."""
        if not text or not isinstance(text, str):
            raise VideoModelError("Invalid text input for summarization")

        try:
            prompt_to_use = custom_prompt if custom_prompt else config.DEFAULT_SUMMARY_PROMPT
            
            # Ensure the model is available
            if not hasattr(self, 'model') or self.model is None:
                 self._configure_gemini_api() # Attempt to reconfigure if not set
                 if not hasattr(self, 'model') or self.model is None:
                    raise VideoModelError("Gemini model not initialized for summarization.")

            full_prompt = f"{prompt_to_use}\n\n---\n\n{text}"
            
            def generate():
                return self.model.generate_content(full_prompt)
            
            for i in range(len(self.api_keys)):
                try:
                    response = generate()
                    # If successful, break the loop
                    return response.text
                except ResourceExhausted as e:
                    logger.warning(f"API key at index {self.current_api_key_index} is rate-limited. Trying next key.")
                    self._get_next_api_key()
                    self._configure_gemini_api()
                    if i == len(self.api_keys) - 1:
                        logger.error("All API keys are rate-limited.")
                        raise VideoModelError("All available API keys have been exhausted.") from e
                except Exception as gen_e:
                    logger.error(f"An unexpected error occurred with API key at index {self.current_api_key_index}: {gen_e}")
                    raise VideoModelError(f"Failed to generate summary due to an unexpected API error: {gen_e}") from gen_e

            raise VideoModelError("Failed to generate summary after trying all API keys.")
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            if isinstance(e, VideoModelError):
                raise
            raise VideoModelError(f"Failed to generate summary: {str(e)}")

    def get_playlist_info(self, playlist_url: str) -> Dict[str, Any]:
        """Gets all video IDs and title from a YouTube playlist URL."""
        # Playlist support removed with yt-dlp removal
        raise VideoModelError("Playlist support has been removed from this application.")

    def _get_video_info_oembed(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Fallback: Use YouTube oEmbed to get minimal info when yt-dlp fails."""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            resp = requests.get(oembed_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'id': video_id,
                    'title': data.get('title', f'Video {video_id}'),
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'duration': 0,
                    'description': '',
                    'uploader': data.get('author_name', 'Unknown Uploader'),
                    'view_count': 0,
                    'like_count': 0,
                    'upload_date': ''
                }
        except Exception as e:
            logger.warning(f"oEmbed fallback failed for {video_id}: {e}")
        return None

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Fetches complete information about a YouTube video using oEmbed."""
        if not video_id or not isinstance(video_id, str):
            raise VideoModelError(ERROR_INVALID_VIDEO_ID)
        
        # Use oEmbed directly (yt-dlp was removed)
        fallback = self._get_video_info_oembed(video_id)
        if fallback:
            logger.info(f"Using oEmbed for video {video_id}")
            return fallback
        
        raise VideoModelError(f"Failed to fetch video info for {video_id}")
