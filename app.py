import os
import logging
from app import create_app
from app.config import config

# Configure logging using settings from config
logging.basicConfig(
    level=config.LOGGING_LEVEL,
    format=config.LOGGING_FORMAT
)
logger = logging.getLogger(__name__)

app = create_app()

if __name__ == "__main__":
    # Verify required environment variables using the config validator
    api_key_error = config.validate_api_keys()
    if api_key_error:
        logger.warning(api_key_error)

    if not app.video_controller:
         logger.warning("VideoController failed to initialize. The application will have limited or no functionality.")

    app.run(debug=True)