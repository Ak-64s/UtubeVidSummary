import os
from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path=".env.local")

class Config:
    """Application configuration."""
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    if SECRET_KEY == "dev-secret-key-change-in-production":
        import warnings
        warnings.warn(
            "Using default SECRET_KEY. Set FLASK_SECRET_KEY environment variable in production!",
            RuntimeWarning
        )
    
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))

    GEMINI_API_KEYS = [
        key for key in [
            os.getenv('GEMINI_API_KEY'),
            os.getenv('GOOGLE_API_KEY'),
            os.getenv('API_KEY'),
            os.getenv('API_KEY1'),
            os.getenv('API_KEY2')
        ] if key
    ]

    LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO").upper()
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    USE_YOUTUBE_TRANSCRIPT_API = os.getenv("USE_YOUTUBE_TRANSCRIPT_API", "true").lower() == "true"
    TRANSCRIPT_PREFERRED_LANGUAGES = [
        lang.strip() for lang in os.getenv("TRANSCRIPT_LANGUAGES", "hi,en,en-US,en-GB").split(",") if lang.strip()
    ]
    TRANSCRIPT_SLICE_TTL_SECONDS = int(os.getenv("TRANSCRIPT_SLICE_TTL_SECONDS", "86400"))
    
    DEFAULT_SUMMARY_PROMPT = """Process the given text and convert it into organized notes. Follow these instructions:

Organize the information logically, breaking it down into clear, concise bullet points.

Use simple, accessible language. Avoid jargon and complex phrasing.

Ensure that no major idea or argument is missed. Cover all essential concepts, arguments, and conclusions from the original text.

Structure the output with Markdown formatting, using headings for sections and bold text to emphasize key terms or ideas.

Provide the notes directly without any introductory text or preamble.

Text to process:"""

    @staticmethod
    def validate_api_keys():
        """Returns an error message if the API key is not found."""
        if not Config.GEMINI_API_KEYS:
            return (
                "No Gemini API key found (tried GOOGLE_API_KEY, GEMINI_API_KEY, API_KEY, API_KEY1, API_KEY2). "
                "The application may not function correctly if an API key is required by the model. "
                "You can get an API key from https://ai.google.dev/gemini-api"
            )
        return None

config = Config() 