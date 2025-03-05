"""
Configuration module for the Compensation Aggregator application.
Centralizes all configuration settings and provides environment-specific configurations.
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent

# Application environment (development, testing, production)
APP_ENV = os.getenv("APP_ENV", "development")

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": os.path.join(BASE_DIR, "app.log"),
            "mode": "a",
        },
        "error_file": {
            "class": "logging.FileHandler",
            "level": "ERROR",
            "formatter": "detailed",
            "filename": os.path.join(BASE_DIR, "logs", "error.log"),
            "mode": "a",
        },
    },
    "loggers": {
        "": {  # Root logger
            "handlers": ["console", "file", "error_file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "selenium": {  # Selenium logger
            "level": "WARNING",
        },
        "urllib3": {  # Urllib3 logger
            "level": "WARNING",
        },
    },
}

# Streamlit configuration
STREAMLIT_CONFIG = {
    "page_title": "Compensation Aggregator",
    "page_icon": "💼",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# Scraping configuration
SCRAPING_CONFIG = {
    "default_headless": True,
    "default_max_depth": 4,
    "default_max_breadth": 17,
    "default_retry_count": 2,
    "default_timeout": 60,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    "chrome_options": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--ignore-certificate-errors",
        "--allow-insecure-localhost",
    ],
}

# API configuration
API_CONFIG = {
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    "openai_temperature": 0,
    "jina_api_base_url": "https://r.jina.ai/",
    "jina_api_timeout": 60,
}

# Data processing configuration
DATA_PROCESSING_CONFIG = {
    "excel_engine": "xlsxwriter",
    "csv_encoding": "utf-8",
    "max_description_length": 5000,  # Maximum length for description fields
}

# Environment-specific configurations
ENV_CONFIGS = {
    "development": {
        "debug": True,
        "log_level": "DEBUG",
    },
    "testing": {
        "debug": True,
        "log_level": "DEBUG",
    },
    "production": {
        "debug": False,
        "log_level": "INFO",
    },
}

# Get environment-specific configuration
ENV_CONFIG = ENV_CONFIGS.get(APP_ENV, ENV_CONFIGS["development"])

# Create logs directory if it doesn't exist
os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)

def get_config(section: Optional[str] = None) -> Dict[str, Any]:
    """
    Get configuration settings, optionally filtered by section.
    
    Args:
        section: Optional section name to filter configuration
        
    Returns:
        Dictionary of configuration settings
    """
    config = {
        "base_dir": BASE_DIR,
        "app_env": APP_ENV,
        "logging": LOGGING_CONFIG,
        "streamlit": STREAMLIT_CONFIG,
        "scraping": SCRAPING_CONFIG,
        "api": API_CONFIG,
        "data_processing": DATA_PROCESSING_CONFIG,
        "env": ENV_CONFIG,
    }
    
    if section:
        return config.get(section, {})
    
    return config

def configure_logging():
    """Configure logging based on the logging configuration."""
    import logging.config
    logging.config.dictConfig(LOGGING_CONFIG)
