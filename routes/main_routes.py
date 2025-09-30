"""Main routes for rendering web pages."""
import logging
from typing import Any
from flask import Blueprint, render_template, request, session, redirect, url_for, Response, send_from_directory
import os

from utils.progress_tracker import progress_tracker
from constants import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)


@main_bp.route('/')
def welcome() -> str:
    """Renders the home page."""
    last_url = session.get('last_url', '')
    return render_template('index.html', last_url=last_url)


@main_bp.route('/results')
def display_results() -> Any:
    """Renders the result page. Expects result data to be passed or fetched."""
    task_id = request.args.get('task_id') or session.get('last_task_id')
    if not task_id:
        logger.warning("Access to /results without task_id.")
        return redirect(url_for('main.welcome'))

    progress_data = progress_tracker.get_progress(task_id)
    
    if not progress_data or progress_data.get('status') != TASK_STATUS_COMPLETED:
        logger.info(
            f"Access to /results for task {task_id}, but not completed. "
            f"Status: {progress_data.get('status') if progress_data else 'not_found'}"
        )
        if progress_data and progress_data.get('status') == TASK_STATUS_FAILED:
            error_msg = "Processing failed. " + (
                progress_data['errors'][0]['error']
                if progress_data['errors']
                else "Unknown error."
            )
            return render_template('error.html', error=error_msg)
        return redirect(url_for('main.welcome'))

    return render_template('result.html', result_data=progress_data.get('result'))


@main_bp.route('/favicon.ico')
def favicon() -> Response:
    """Serve favicon or return empty response to prevent 404 errors."""
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    favicon_path = os.path.join(static_folder, 'favicon.ico')
    
    if os.path.exists(favicon_path):
        return send_from_directory(static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    else:
        return Response(status=204) 