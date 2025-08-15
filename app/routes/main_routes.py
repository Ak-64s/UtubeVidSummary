from flask import Blueprint, render_template, request, session, redirect, url_for
from app.utils.progress_tracker import progress_tracker
import logging

main_bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@main_bp.route('/')
def welcome():
    """Renders the home page."""
    return render_template('index.html')

@main_bp.route('/results')
def display_results():
    """Renders the result page. Expects result data to be passed or fetched."""
    task_id = request.args.get('task_id') or session.get('last_task_id')
    if not task_id:
        logger.warning("Access to /results without task_id.")
        return redirect(url_for('main.welcome'))

    progress_data = progress_tracker.get_progress(task_id)
    
    if not progress_data or progress_data.get('status') != 'completed':
        logger.info(f"Access to /results for task {task_id}, but not completed. Status: {progress_data.get('status') if progress_data else 'not_found'}")
        if progress_data and progress_data.get('status') == 'failed':
            error_msg = "Processing failed. " + (progress_data['errors'][0]['error'] if progress_data['errors'] else "Unknown error.")
            return render_template('error.html', error=error_msg)
        # Redirect to welcome and the frontend will pick up the task from session and start polling.
        return redirect(url_for('main.welcome'))

    return render_template('result.html', result_data=progress_data.get('result')) 