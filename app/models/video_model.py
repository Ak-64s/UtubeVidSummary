from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import google.generativeai as genai
from ..config import config # Use the centralized config
import os
from typing import List, Dict, Union, Optional, Any
import re
import logging
import requests
import yt_dlp
from app.utils.cache_manager import cache_manager # For caching

import time
import random
from google.api_core.exceptions import ResourceExhausted


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

        self.cache_namespace_transcripts = "transcripts"
        # Enhanced yt-dlp configuration to handle YouTube restrictions better
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'socket_timeout': 60,  # Increased timeout
            'retries': 3,  # Reduced retries to avoid triggering rate limits
            'fragment_retries': 3,
            'extractor_retries': 2,
            'sleep_interval': 2,  # Increased sleep intervals
            'max_sleep_interval': 10,
            'sleep_interval_requests': 2,  # Add delay between requests
            'cookiefile': 'cookies.txt',  # Use cookies for better auth
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            },
            # Additional YouTube-specific options
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],  # Use multiple clients
                    'player_skip': ['configs'],
                    'comment_sort': ['top'],
                    'max_comments': ['0'],  # Don't fetch comments
                }
            }
        }

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
        valid_domains = ["www.youtube.com", "youtube.com", "youtu.be"]
        return parsed_url.netloc in valid_domains

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
                # Handle YouTube live URLs: /live/{video_id}
                if "/live/" in parsed_url.path:
                    video_id = parsed_url.path.split("/live/")[1].split("/")[0]
                    if not video_id:
                        raise VideoModelError("Could not extract video ID from live URL")
                    return video_id
                # Handle standard YouTube URLs: /watch?v={video_id}
                video_id = parse_qs(parsed_url.query).get('v')
                if not video_id:
                    raise VideoModelError("No video ID found in URL")
                return video_id[0]
            raise VideoModelError("Unsupported YouTube URL format")
        except Exception as e:
            logger.error(f"Error extracting video ID: {str(e)}")
            raise VideoModelError(f"Failed to extract video ID: {str(e)}")

    def extract_playlist_id(self, url: str) -> Optional[str]:
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'forcejson': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and info.get('_type') == 'playlist':
                    return info.get('id')
        except Exception as e:
            logger.warning(f"Could not extract playlist ID for URL '{url}'. Error: {str(e)}")
        
        return None

    def is_valid_youtube_url(self, url: str) -> bool:
        return self._validate_url(url)

    def is_playlist_url(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'forcejson': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info is not None and info.get('_type') == 'playlist'
        except Exception:
             return "playlist" in url.lower() or "list=" in url.lower()

    def _retry_with_backoff(self, func, max_retries=3, base_delay=1, errors_to_retry=(Exception,)):
        """Retry a function with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return func()
            except errors_to_retry as e:
                if attempt == max_retries - 1:
                    logger.error(f"Final attempt failed. Error: {str(e)}. No more retries.")
                    raise e
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed with error: {str(e)}. Retrying in {delay:.2f} seconds...")
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

        # Check transcript cache
        transcript_cache_key = video_id
        cached_transcript = cache_manager.get_cached_data(self.cache_namespace_transcripts, transcript_cache_key)
        
        # Check video info cache
        info_cache_key = f"info_{video_id}"
        cached_info = cache_manager.get_cached_data(self.cache_namespace_transcripts, info_cache_key)
        
        # If both are cached, return immediately
        if cached_transcript and cached_info:
            logger.info(f"Both transcript and info for video {video_id} found in cache.")
            filtered_transcript = self._filter_transcript_by_time(cached_transcript, start_time, end_time)
            return filtered_transcript, cached_info
        
        # Fetch missing data
        transcript_data = cached_transcript
        video_info = cached_info
        
        # Fetch transcript if not cached
        if not transcript_data:
            try:
                transcript_data = self._retry_with_backoff(lambda: self._fetch_transcript_from_api(video_id))
                if transcript_data:
                    logger.info(f"Successfully fetched transcript for video {video_id} using YouTube Transcript API.")
                else:
                    logger.warning(f"YouTube Transcript API returned no data for video {video_id}. Falling back to yt-dlp.")
            except Exception as e:
                logger.warning(f"YouTube Transcript API failed for video {video_id}: {str(e)}. Falling back to yt-dlp.")
                transcript_data = None

            if not transcript_data:
                try:
                    transcript_data = self._retry_with_backoff(lambda: self._fetch_transcript_from_yt_dlp(video_id))
                    if transcript_data:
                        logger.info(f"Successfully fetched transcript for video {video_id} using yt-dlp.")
                    else:
                        raise VideoModelError(f"yt-dlp returned no transcript data for {video_id}")
                except Exception as e:
                    logger.error(f"All transcript fetching methods failed for video {video_id}: {str(e)}")
                    raise VideoModelError(f"Failed to fetch transcript for {video_id}") from e
            
            # Cache transcript
            cache_manager.set_cached_data(self.cache_namespace_transcripts, transcript_cache_key, transcript_data)
        
        # Fetch video info if not cached
        if not video_info:
            try:
                video_info = self.get_video_info(video_id)
                # Cache video info
                cache_manager.set_cached_data(self.cache_namespace_transcripts, info_cache_key, video_info, ttl_seconds=3600*24)  # Cache for 24 hours
            except Exception as e:
                logger.warning(f"Failed to fetch video info for {video_id}: {str(e)}")
                # Provide fallback info
                video_info = {
                    'id': video_id,
                    'title': f'Video {video_id}',
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'duration': 0
                }
                # Cache the error result briefly to avoid repeated API calls
                cache_manager.set_cached_data(self.cache_namespace_transcripts, info_cache_key, video_info, ttl_seconds=300)
        
        filtered_transcript = self._filter_transcript_by_time(transcript_data, start_time, end_time)
        return filtered_transcript, video_info

    def fetch_transcript(self, video_id: str, start_time: Optional[float] = None, end_time: Optional[float] = None) -> str:
        """Fetches the transcript for a given YouTube video ID, using cache."""
        transcript, _ = self.fetch_transcript_with_info(video_id, start_time, end_time)
        return transcript

    def _fetch_transcript_from_api(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches and processes transcript using youtube-transcript-api."""
        
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

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Prefer English transcripts
        for lang in ['en', 'en-US', 'en-GB']:
            try:
                transcript = transcript_list.find_transcript([lang])
                return process_transcript_data(transcript.fetch())
            except (TranscriptsDisabled, NoTranscriptFound):
                continue
        
        # Try generated English transcript
        try:
            transcript = transcript_list.find_generated_transcript(['en'])
            return process_transcript_data(transcript.fetch())
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.warning(f"No English transcript found for {video_id}. Checking other languages.")

        # Fallback to any available transcript and translate if possible
        for transcript in transcript_list:
            try:
                if transcript.is_translatable:
                    return process_transcript_data(transcript.translate('en').fetch())
                return process_transcript_data(transcript.fetch())
            except Exception as e:
                logger.warning(f"Could not fetch or process transcript for language '{transcript.language_code}': {e}")
                continue
        
        raise VideoModelError("No usable transcripts found via YouTubeTranscriptApi")

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

    def _fetch_transcript_from_yt_dlp(self, video_id: str) -> List[Dict[str, Any]]:
        """Try to fetch transcript using yt-dlp as fallback, parsing timestamps."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as temp_dir:
            # Enhanced headers to avoid 403 errors
            http_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
            
            # Use base configuration and enhance for subtitle extraction
            ydl_opts = self.ydl_opts.copy()
            ydl_opts.update({
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'hi', 'en-US', 'en-GB'],
                'subtitlesformat': 'best',
                'skip_download': True,
                'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
                'sleep_interval_subtitles': 2,
                # Override headers specifically for subtitle extraction
                'http_headers': http_headers,
            })
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Try downloading subtitles with error handling
                    try:
                        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                    except Exception as download_error:
                        logger.warning(f"yt-dlp download had issues for {video_id}: {str(download_error)}")
                        # Continue to check if any subtitles were still downloaded
                    
                    subtitle_file_path = None
                    for ext in ['vtt', 'ttml', 'srt']:
                        for lang_code in ['en', 'hi', 'en-US', 'en-GB']:
                            potential_file = os.path.join(temp_dir, f"{video_id}.{lang_code}.{ext}")
                            if os.path.exists(potential_file):
                                subtitle_file_path = potential_file
                                logger.info(f"Found subtitle file: {potential_file}")
                                break
                        if subtitle_file_path:
                            break
            except Exception as setup_error:
                logger.error(f"Failed to set up yt-dlp for subtitle extraction: {str(setup_error)}")
                raise VideoModelError(f"yt-dlp setup failed: {str(setup_error)}")
            
            if subtitle_file_path:
                with open(subtitle_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                lines = content.strip().split('\n')
                transcript_data = []
                time_pattern = re.compile(r'(\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{3})')
                
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    match = time_pattern.search(line)
                    if match:
                        start_time_str = match.group(1)
                        start_time = self._time_to_seconds(start_time_str)
                        
                        text_lines = []
                        i += 1
                        while i < len(lines) and lines[i].strip() != '':
                            text_lines.append(lines[i].strip())
                            i += 1
                        
                        if text_lines:
                            text = ' '.join(text_lines)
                            text = re.sub(r'<[^>]+>', '', text).strip()
                            if text:
                                transcript_data.append({'text': text, 'start': start_time})
                    else:
                        i += 1

                if not transcript_data:
                    raise VideoModelError("No valid subtitle content could be extracted from the file.")
                
                logger.info(f"Successfully parsed transcript with {len(transcript_data)} entries from yt-dlp.")
                return transcript_data
            else:
                raise VideoModelError("yt-dlp failed to download a subtitle file.")

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
        if not self._validate_url(playlist_url):
            raise VideoModelError("Invalid YouTube URL format")
        try:
            ydl_opts = self.ydl_opts.copy()
            ydl_opts['noplaylist'] = False
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                playlist_info = ydl.extract_info(playlist_url, download=False)
                if not playlist_info or 'entries' not in playlist_info:
                    raise VideoModelError("Could not extract playlist entries using yt-dlp.")
                
                video_ids = [entry['id'] for entry in playlist_info['entries'] if entry and entry.get('id')]
                if not video_ids:
                    raise VideoModelError("No valid video IDs found in playlist entries.")
                
                return {
                    "video_ids": video_ids,
                    "playlist_title": playlist_info.get('title', 'YouTube Playlist')
                }
        except Exception as e:
            logger.error(f"Error getting playlist video IDs with yt-dlp: {str(e)}.")
            raise VideoModelError(f"Failed to get playlist video IDs: {str(e)}")

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Fetches complete information about a YouTube video."""
        if not video_id or not isinstance(video_id, str):
            raise VideoModelError("Invalid video ID")
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                video_info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if not video_info:
                    raise VideoModelError("Could not fetch video information")

                return {
                    'id': video_id,
                    'title': video_info.get('title', 'Unknown Title'),
                    'url': video_info.get('webpage_url', f'https://www.youtube.com/watch?v={video_id}'),
                    'duration': video_info.get('duration', 0),
                    'description': video_info.get('description', ''),
                    'uploader': video_info.get('uploader', 'Unknown Uploader'),
                    'view_count': video_info.get('view_count', 0),
                    'like_count': video_info.get('like_count', 0),
                    'upload_date': video_info.get('upload_date', '')
                }
        except Exception as e:
            logger.error(f"Error fetching video info: {str(e)}")
            raise VideoModelError(f"yt-dlp error: {str(e)}") 