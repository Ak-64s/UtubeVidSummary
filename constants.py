"""
Application-wide constants and configuration values.
"""

CACHE_TTL_TRANSCRIPT = 30 * 24 * 3600
CACHE_TTL_VIDEO_INFO = 24 * 3600
CACHE_TTL_VIDEO_INFO_FALLBACK = 300
CACHE_TTL_HEALTH_CHECK = 60
CACHE_TTL_DEFAULT = 3600

MAX_CUSTOM_PROMPT_LENGTH = 2000
MAX_FILENAME_LENGTH = 100

YOUTUBE_DOMAINS = ["www.youtube.com", "youtube.com", "youtu.be"]
YOUTUBE_URL_PATTERN = r'^https?://(www\.)?(youtube\.com|youtu\.be)/.+'

DEFAULT_TRANSCRIPT_LANGUAGES = ['hi', 'en', 'en-US', 'en-GB']

ERROR_INVALID_URL = "Invalid URL: URL must be a non-empty string."
ERROR_INVALID_PROMPT = "Custom prompt must be a string."
ERROR_PROMPT_TOO_LONG = f"Custom prompt is too long (max {MAX_CUSTOM_PROMPT_LENGTH} characters)."
ERROR_INVALID_YOUTUBE_URL = "Invalid YouTube URL provided."
ERROR_SERVICE_UNAVAILABLE = "Service temporarily unavailable due to initialization issues."
ERROR_NO_DATA_PROVIDED = "No data provided"
ERROR_NO_URL_PROVIDED = "Please provide a YouTube URL"
ERROR_INVALID_VIDEO_ID = "Invalid video ID"
ERROR_INVALID_TIMESTAMP = "Invalid timestamp format"
ERROR_START_BEFORE_END = "Start time must be before end time"

MSG_PAGE_NOT_FOUND = "Page not found"
MSG_INTERNAL_ERROR = "An internal server error occurred. Please try again later."

TASK_STATUS_PENDING = "pending"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1

CACHE_NAMESPACE_TRANSCRIPTS = "transcripts"
CACHE_NAMESPACE_PROGRESS = "progress"
CACHE_NAMESPACE_HEALTH = "health"