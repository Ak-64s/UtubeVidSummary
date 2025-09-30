"""API routes for handling video processing requests."""
import uuid
import logging
from typing import Dict, Any, Tuple

from flask import Blueprint, jsonify, request, session, current_app

from utils.progress_tracker import progress_tracker
from services.task_manager import background_task_runner
from utils.helpers import validate_form_data, convert_time_to_seconds
from constants import (
    ERROR_SERVICE_UNAVAILABLE,
    ERROR_NO_URL_PROVIDED,
    TASK_STATUS_PENDING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
)

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/submit_task', methods=['POST'])
def submit_task() -> Tuple[Dict[str, Any], int]:
    """Submit a video processing task."""
    if not current_app.video_controller:
        return jsonify({"error": ERROR_SERVICE_UNAVAILABLE}), 503

    is_valid, error_message = validate_form_data(request.form)
    if not is_valid:
        return jsonify({"error": error_message}), 400

    url = request.form['link'].strip()
    custom_prompt = request.form.get('prompt', '').strip() or None
    
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    try:
        start_time = convert_time_to_seconds(start_time_str) if start_time_str else None
        end_time = convert_time_to_seconds(end_time_str) if end_time_str else None
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    task_id = str(uuid.uuid4())
    
    current_app.queue.enqueue(
        background_task_runner,
        args=(
            task_id,
            url,
            custom_prompt,
            start_time,
            end_time,
        ),
        job_id=task_id
    )

    # Initialize progress tracking
    progress_tracker.initialize_progress(task_id, total_items=1, description=f"Processing URL: {url}")
    logger.info(f"Task {task_id} submitted for URL: {url}")
    
    session['last_task_id'] = task_id
    session['last_url'] = url
    return jsonify({"task_id": task_id}), 202

@api_bp.route('/task_status/<task_id>', methods=['GET'])
def task_status(task_id: str) -> Tuple[Dict[str, Any], int]:
    """Get the status of a processing task."""
    progress_data = progress_tracker.get_progress(task_id)
    if not progress_data:
        return jsonify({"status": "pending", "message": "Task initializing or not found."}), 202

    response_data = {
        "task_id": task_id,
        "status": progress_data.get('status', 'unknown'),
        "progress_percentage": 0,
        "total_items": progress_data.get('total_items', 0),
        "completed_items": progress_data.get('completed_items', 0),
        "current_item_details": progress_data.get('current_item_details', ''),
        "result": None,
        "errors": progress_data.get('errors', [])
    }

    if progress_data.get('total_items', 0) > 0:
        response_data["progress_percentage"] = int(
            (progress_data.get('completed_items', 0) / progress_data['total_items']) * 100
        )
    
    if response_data["status"] == TASK_STATUS_COMPLETED:
        response_data["result"] = progress_data.get('result')

    return jsonify(response_data)

@api_bp.route('/get_video_info', methods=['GET'])
def get_video_info() -> Tuple[Dict[str, Any], int]:
    """Get video information (duration, title) for a given URL."""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': ERROR_NO_URL_PROVIDED}), 400
    if not current_app.video_controller:
        return jsonify({'error': ERROR_SERVICE_UNAVAILABLE}), 503
    try:
        video_id = current_app.video_controller.video_model.extract_video_id(url)
        from utils.cache_manager import cache_manager
        info_cache_key = f"info_{video_id}"
        cached_info = cache_manager.get_cached_data(
            current_app.video_controller.video_model.cache_namespace_transcripts, 
            info_cache_key
        )
        
        if cached_info:
            logger.info(f"Video info for {video_id} served from cache")
            return jsonify({
                'duration': cached_info.get('duration'), 
                'title': cached_info.get('title')
            })
        
        # If not in cache, fetch fresh data (with internal fallback)
        info = current_app.video_controller.video_model.get_video_info(video_id)
        return jsonify({'duration': info['duration'], 'title': info['title']})
    except Exception as e:
        logger.error(f'Error fetching video info: {str(e)}')
        # Last-resort fallback: try oEmbed directly here as well in case model change regressed
        try:
            from models.video_model import VideoModel
            vm: VideoModel = current_app.video_controller.video_model
            # Ensure video_id is available for fallback
            try:
                video_id = video_id if 'video_id' in locals() else vm.extract_video_id(url)
            except Exception:
                return jsonify({'error': 'Failed to parse video ID'}), 400
            fallback = vm._get_video_info_oembed(video_id)  # type: ignore[attr-defined]
            if fallback:
                # Cache briefly to reduce repeated errors
                cache_manager.set_cached_data(vm.cache_namespace_transcripts, f"info_{video_id}", fallback, ttl_seconds=300)
                return jsonify({'duration': fallback['duration'], 'title': fallback['title']})
        except Exception:
            pass
        return jsonify({'error': 'Failed to fetch video info'}), 500

@api_bp.route('/health', methods=['GET'])
def health_check() -> Tuple[Dict[str, Any], int]:
    """Health check endpoint for Docker and monitoring systems."""
    try:
        # Check if video controller is initialized
        if not current_app.video_controller:
            return jsonify({
                "status": "unhealthy",
                "reason": "VideoController not initialized",
                "timestamp": "now"
            }), 503
        
        # Check if cache manager is working (basic functionality test)
        from utils.cache_manager import cache_manager
        test_key = "health_check_test"
        test_value = "ok"
        cache_manager.set_cached_data("health", test_key, test_value, ttl_seconds=60)
        cached_value = cache_manager.get_cached_data("health", test_key)
        
        if cached_value != test_value:
            return jsonify({
                "status": "unhealthy", 
                "reason": "Cache system not working properly",
                "timestamp": "now"
            }), 503
            
        # Clean up test data
        cache_manager.delete_cached_data("health", test_key)
        
        return jsonify({
            "status": "healthy",
            "components": {
                "video_controller": "ok",
                "cache_manager": "ok",
                "queue_system": "ok"
            },
            "timestamp": "now"
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "reason": f"Health check error: {str(e)}",
            "timestamp": "now"
        }), 503

@api_bp.route('/system_info', methods=['GET'])
def system_info() -> Dict[str, Any]:
    """System information endpoint for debugging and optimization suggestions."""
    import shutil
    import subprocess
    
    info = {
        "status": "ok",
        "features": {
            "transcript_api": True,
            "yt_dlp": False,
            "cache_system": True,
            "ai_summarization": True,
        },
        "optimizations": [],
        "recommendations": []
    }
    
    # Check for ffmpeg
    ffmpeg_available = shutil.which('ffmpeg') is not None
    info["features"]["ffmpeg"] = ffmpeg_available
    
    if not ffmpeg_available:
        info["optimizations"].append({
            "type": "performance",
            "title": "Install FFmpeg",
            "description": "FFmpeg improves video format support and reduces download errors",
            "action": "Install FFmpeg from https://ffmpeg.org/download.html",
            "priority": "medium"
        })
    
    # yt-dlp removed; do not report version
    
    # General recommendations
    info["recommendations"].extend([
        "Use recent YouTube videos for better compatibility",
        "Try shorter videos if experiencing timeout issues",
        "Ensure stable internet connection for large playlists"
    ])
    
    return jsonify(info) 