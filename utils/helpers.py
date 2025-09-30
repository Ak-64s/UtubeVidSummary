"""Helper utilities for validation and data processing."""
import re
from typing import Dict, Any, Tuple

from constants import (
    MAX_CUSTOM_PROMPT_LENGTH,
    MAX_FILENAME_LENGTH,
    YOUTUBE_URL_PATTERN,
    ERROR_NO_DATA_PROVIDED,
    ERROR_NO_URL_PROVIDED,
    ERROR_INVALID_TIMESTAMP,
    ERROR_START_BEFORE_END,
)


def validate_form_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validates form data and returns (is_valid, error_message)."""
    if not data:
        return False, ERROR_NO_DATA_PROVIDED
    
    url = data.get('link', '').strip()
    if not url:
        return False, ERROR_NO_URL_PROVIDED
    
    # Basic URL validation for YouTube
    if not re.match(YOUTUBE_URL_PATTERN, url):
        return False, "Please provide a valid YouTube URL (youtube.com or youtu.be)"
    
    custom_prompt = data.get('prompt', '').strip()
    if custom_prompt and len(custom_prompt) > MAX_CUSTOM_PROMPT_LENGTH:
        return False, f"Custom prompt is too long (max {MAX_CUSTOM_PROMPT_LENGTH} characters)"
    
    # Validate timestamp format if provided
    start_time_str = data.get('start_time', '').strip()
    end_time_str = data.get('end_time', '').strip()
    
    if start_time_str:
        if not _is_valid_timestamp(start_time_str):
            return False, "Start time must be in HH:MM:SS format"
    
    if end_time_str:
        if not _is_valid_timestamp(end_time_str):
            return False, "End time must be in HH:MM:SS format"
    
    # Check if start time is before end time
    if start_time_str and end_time_str:
        try:
            start_seconds = _convert_time_to_seconds(start_time_str)
            end_seconds = _convert_time_to_seconds(end_time_str)
            if start_seconds >= end_seconds:
                return False, ERROR_START_BEFORE_END
        except ValueError:
            return False, ERROR_INVALID_TIMESTAMP
    
    return True, ""

def _is_valid_timestamp(timestamp: str) -> bool:
    """Check if timestamp is in valid H+:MM:SS format with unlimited hours."""
    pattern = r'^(\d+):([0-5]?[0-9]):([0-5]?[0-9])$'
    return bool(re.match(pattern, timestamp))

def _convert_time_to_seconds(time_str: str) -> float:
    """Convert time string in HH:MM:SS format to seconds."""
    if not time_str or not isinstance(time_str, str):
        raise ValueError("Time string cannot be empty")
    
    try:
        parts = time_str.split(':')
        if len(parts) != 3:
            raise ValueError("Timestamp must be in HH:MM:SS format")
        
        hours, minutes, seconds = map(int, parts)
        
        if hours < 0 or minutes < 0 or seconds < 0:
            raise ValueError("Time values cannot be negative")
        if minutes > 59 or seconds > 59:
            raise ValueError("Minutes and seconds must be less than 60")
        
        return hours * 3600 + minutes * 60 + seconds
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid timestamp format: {str(e)}")

def convert_time_to_seconds(time_str: str) -> float:
    """Public wrapper for converting HH:MM:SS to seconds.

    Exposed for import by routes and other modules without relying on a
    "private" function name. Raises ValueError on invalid input.
    """
    return _convert_time_to_seconds(time_str)

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    if not filename:
        return "untitled"
    
    invalid_chars = '<>:"/\\|?*'
    sanitized = ''.join(c for c in filename if c not in invalid_chars)
    sanitized = sanitized.strip(' .')
    
    if len(sanitized) > MAX_FILENAME_LENGTH:
        sanitized = sanitized[:MAX_FILENAME_LENGTH]
    
    return sanitized if sanitized else "untitled" 