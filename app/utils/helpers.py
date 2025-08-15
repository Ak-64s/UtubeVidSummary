from typing import Dict, Any
import re

def validate_form_data(data: Dict[str, Any]) -> tuple:
    """Validates form data and returns (is_valid, error_message)."""
    if not data:
        return False, "No data provided"
    
    url = data.get('link', '').strip()
    if not url:
        return False, "Please provide a YouTube URL"
    
    # Basic URL validation for YouTube
    youtube_pattern = r'^https?://(www\.)?(youtube\.com|youtu\.be)/.+'
    if not re.match(youtube_pattern, url):
        return False, "Please provide a valid YouTube URL (youtube.com or youtu.be)"
    
    custom_prompt = data.get('prompt', '').strip()
    if custom_prompt and len(custom_prompt) > 2000:
        return False, "Custom prompt is too long (max 2000 characters)"
    
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
                return False, "Start time must be before end time"
        except ValueError:
            return False, "Invalid timestamp format"
    
    return True, ""

def _is_valid_timestamp(timestamp: str) -> bool:
    """Check if timestamp is in valid HH:MM:SS format."""
    pattern = r'^([0-9]{1,2}):([0-5]?[0-9]):([0-5]?[0-9])$'
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

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    if not filename:
        return "untitled"
    
    # Remove invalid characters for file systems
    invalid_chars = '<>:"/\\|?*'
    sanitized = ''.join(c for c in filename if c not in invalid_chars)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    return sanitized if sanitized else "untitled" 