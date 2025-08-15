import os
from dotenv import load_dotenv

# Load environment variables from .env and .env.local files
load_dotenv()
load_dotenv(dotenv_path=".env.local")

class Config:
    """Application configuration."""
    # Flask settings
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("FLASK_SECRET_KEY environment variable is required but not set. Please set it to a secure random string.")

    # API Keys - Collect all provided keys into a list for rotation
    GEMINI_API_KEYS = [
        key for key in [
            os.getenv('GEMINI_API_KEY'),
            os.getenv('GOOGLE_API_KEY'),
            os.getenv('API_KEY'),
            os.getenv('API_KEY1'),
            os.getenv('API_KEY2')
        ] if key
    ]

    # Logging
    LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO").upper()
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Summarization
    DEFAULT_SUMMARY_PROMPT = """You are an expert academic assistant. Your task is to process the given text and convert it into high-quality notes. Follow these instructions:

Organize the information logically, breaking it down into clear, concise bullet points.

Use simple, accessible language. Avoid jargon and complex phrasing.

Ensure that no major idea or argument is missed. Cover all essential concepts, arguments, and conclusions from the original text.

Structure the output with Markdown formatting, using headings for sections and bold text to emphasize key terms or ideas.

The goal is to create a complete, exam-ready summary that's easy to revisit and understand even after a long time.

Text to summarize:"""

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