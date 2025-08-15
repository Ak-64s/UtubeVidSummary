from flask import Flask
from .config import config
from .controllers.video_controller import VideoController, VideoControllerError
import rq
import os
import logging
import sys
from flask import render_template

# Application Factory

def _configure_logging():
    """Configure centralized logging for the application."""
    # Remove any existing handlers to avoid duplication
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.LOGGING_LEVEL),
        format=config.LOGGING_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('yt_dlp').setLevel(logging.WARNING)

def create_app():
    # Configure logging first
    _configure_logging()
    
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    # Use Redis if configured, otherwise use a simple synchronous queue for local dev
    if os.getenv('USE_REDIS', 'false').lower() == 'true':
        import redis
        app.config['REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379')
        redis_conn = redis.from_url(app.config['REDIS_URL'])
        app.queue = rq.Queue(connection=redis_conn)
        app.logger.info("Using Redis for task queue.")
    else:
        import threading
        class SyncQueue:
            def enqueue(self, func, *args, **kwargs):
                func_args = kwargs.pop('args', args)
                kwargs.pop('job_id', None)
                thread = threading.Thread(target=func, args=func_args, kwargs=kwargs)
                thread.start()
        app.queue = SyncQueue()
        app.logger.info("Using non-blocking synchronous execution for local development.")


    # Register Blueprints
    from .routes.main_routes import main_bp
    from .routes.api_routes import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    # Initialize VideoController
    try:
        app.video_controller = VideoController()
        app.logger.info("VideoController initialized successfully.")
    except VideoControllerError as e:
        app.logger.error(f"CRITICAL: Failed to initialize VideoController: {str(e)}. Application might not function correctly.")
        app.video_controller = None
    except Exception as e:
        app.logger.error(f"CRITICAL: Unexpected error initializing VideoController: {str(e)}")
        app.video_controller = None

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', error="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Unhandled Internal Server Error: {error}")
        return render_template('error.html', error="An internal server error occurred. Please try again later."), 500

    return app 