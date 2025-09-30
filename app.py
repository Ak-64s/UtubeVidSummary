
"""
Main application entry point for the Flask YouTube video summarization app.
"""
import logging
import sys
from flask import Flask, render_template

from config import config
from controllers.video_controller import VideoController, VideoControllerError
from services.queue_manager import create_queue
from middleware.security import configure_security_headers

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure centralized logging for the application."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    logging.basicConfig(
        level=getattr(logging, config.LOGGING_LEVEL),
        format=config.LOGGING_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def _initialize_video_controller(app: Flask) -> None:
    """Initialize the video controller service."""
    try:
        app.video_controller = VideoController()
        app.logger.info("VideoController initialized successfully.")
    except VideoControllerError as e:
        app.logger.error(
            f"CRITICAL: Failed to initialize VideoController: {str(e)}. "
            "Application might not function correctly."
        )
        app.video_controller = None
    except Exception as e:
        app.logger.error(
            f"CRITICAL: Unexpected error initializing VideoController: {str(e)}"
        )
        app.video_controller = None


def _register_error_handlers(app: Flask) -> None:
    """Register custom error handlers."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', error="Page not found"), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Unhandled Internal Server Error: {error}")
        return render_template(
            'error.html',
            error="An internal server error occurred. Please try again later."
        ), 500


def create_app() -> Flask:
    """
    Application factory for creating and configuring the Flask app.
    
    Returns:
        Configured Flask application instance
    """
    _configure_logging()
    
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.queue = create_queue()

    from routes.main_routes import main_bp
    from routes.api_routes import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    _initialize_video_controller(app)
    _register_error_handlers(app)
    configure_security_headers(app)

    return app


def validate_app_readiness(app: Flask) -> None:
    """Validate application readiness and log warnings for any issues."""
    api_key_error = config.validate_api_keys()
    if api_key_error:
        logger.warning(api_key_error)

    if not app.video_controller:
        logger.warning(
            "VideoController failed to initialize. "
            "The application will have limited or no functionality."
        )


try:
    app = create_app()
except Exception as e:
    logger.error(f"Failed to create app: {e}")
    app = Flask(__name__)
    
    @app.route('/')
    def error():
        return f"Application failed to initialize: {str(e)}", 500


def main() -> None:
    """Run the Flask development server."""
    validate_app_readiness(app)
    
    app.run(
        debug=config.FLASK_DEBUG,
        host=config.FLASK_HOST,
        port=config.FLASK_PORT
    )


if __name__ == "__main__":
    main()