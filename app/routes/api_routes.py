from flask import Blueprint, jsonify, request, session, current_app
from app.utils.progress_tracker import progress_tracker
from app.services.task_manager import background_task_runner
from app.utils.helpers import validate_form_data, _convert_time_to_seconds
import uuid
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/submit_task', methods=['POST'])
def submit_task():
    if not current_app.video_controller:
        return jsonify({"error": "Service temporarily unavailable due to initialization issues."}), 503

    is_valid, error_message = validate_form_data(request.form)
    if not is_valid:
        return jsonify({"error": error_message}), 400

    url = request.form['link'].strip()
    custom_prompt = request.form.get('prompt', '').strip() or None
    
    # Get timestamp parameters if provided
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    
    # Convert timestamps to seconds if provided
    try:
        start_time = _convert_time_to_seconds(start_time_str) if start_time_str else None
        end_time = _convert_time_to_seconds(end_time_str) if end_time_str else None
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
    return jsonify({"task_id": task_id}), 202

@api_bp.route('/task_status/<task_id>', methods=['GET'])
def task_status(task_id: str):
    progress_data = progress_tracker.get_progress(task_id)
    if not progress_data:
        # Task not found or expired
        return jsonify({"status": "pending", "message": "Task initializing or not found."}), 202 # Still accepted, but not actively tracked

    response_data = {
        "task_id": task_id,
        "status": progress_data.get('status', 'unknown'),
        "progress_percentage": 0,
        "current_item_details": progress_data.get('current_item_details', ''),
        "result": None,
        "errors": progress_data.get('errors', [])
    }

    if progress_data.get('total_items', 0) > 0:
        response_data["progress_percentage"] = int(
            (progress_data.get('completed_items', 0) / progress_data['total_items']) * 100
        )
    
    if response_data["status"] == "completed":
        response_data["result"] = progress_data.get('result')
    elif response_data["status"] == "failed":
        # Errors are already in response_data["errors"]
        pass

    return jsonify(response_data)

@api_bp.route('/get_video_info', methods=['GET'])
def get_video_info():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    if not current_app.video_controller:
        return jsonify({'error': 'Service unavailable'}), 503
    try:
        if current_app.video_controller.video_model.is_playlist_url(url):
            return jsonify({'error': 'Duration fetch not supported for playlists'}), 400
        
        video_id = current_app.video_controller.video_model.extract_video_id(url)
        
        # Check cache first to avoid redundant yt-dlp calls
        from app.utils.cache_manager import cache_manager
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
        
        # If not in cache, fetch fresh data
        info = current_app.video_controller.video_model.get_video_info(video_id)
        return jsonify({'duration': info['duration'], 'title': info['title']})
    except Exception as e:
        logger.error(f'Error fetching video info: {str(e)}')
        return jsonify({'error': 'Failed to fetch video info'}), 500

@api_bp.route('/health', methods=['GET'])
def health_check():
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
        from app.utils.cache_manager import cache_manager
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
def system_info():
    """System information endpoint for debugging and optimization suggestions."""
    import shutil
    import subprocess
    
    info = {
        "status": "ok",
        "features": {
            "transcript_api": True,
            "yt_dlp": True,
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
    
    # Check yt-dlp version
    try:
        import yt_dlp
        yt_dlp_version = yt_dlp.version.__version__
        info["versions"] = {"yt_dlp": yt_dlp_version}
        
        # Suggest updating if version is old
        major_version = int(yt_dlp_version.split('.')[0])
        if major_version < 2024:
            info["optimizations"].append({
                "type": "compatibility",
                "title": "Update yt-dlp",
                "description": "Newer versions have better YouTube compatibility",
                "action": "pip install --upgrade yt-dlp",
                "priority": "high"
            })
    except Exception:
        info["optimizations"].append({
            "type": "error",
            "title": "yt-dlp Issue",
            "description": "Unable to determine yt-dlp version",
            "priority": "high"
        })
    
    # General recommendations
    info["recommendations"].extend([
        "Use recent YouTube videos for better compatibility",
        "Try shorter videos if experiencing timeout issues",
        "Ensure stable internet connection for large playlists"
    ])
    
    return jsonify(info) 