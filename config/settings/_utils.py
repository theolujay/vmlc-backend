"""
Shared utilities for settings files.
"""

import os
from dotenv import load_dotenv

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


def read_secret(secret_name, default=""):
    """Read secret from file if SECRET_NAME_FILE env var exists, else from env."""
    file_path = os.getenv(f"{secret_name}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as f:
            return f.read().strip()
    return os.getenv(secret_name, default)
