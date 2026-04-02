import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class Config:
    """Set Flask configuration variables from .env file."""

    # General Config
    # IMPORTANT: Set SECRET_KEY in Render's Environment Variables panel.
    # Fallback is provided so the app doesn't crash if env var is missing.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sbtp-render-fallback-secret-key-2024-do-not-use-in-prod')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1']