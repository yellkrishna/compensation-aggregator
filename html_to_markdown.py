import requests
import logging
import time
import re
from bs4 import BeautifulSoup
from functools import wraps
from typing import Optional, Dict, Any
import traceback

# Configure logging
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
BACKOFF_FACTOR = 2
DEFAULT_TIMEOUT = 60
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"

def retry_with_backoff(max_tries=3, backoff_factor=2):
    """Retry decorator with exponential backoff for network operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_tries):
                try:
                    return func(*args, **kwargs)
                except requests.RequestException as e:
                    if attempt == max_tries - 1:
                        logger.error(f"Failed after {max_tries} attempts: {str(e)}")
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt+1} failed: {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        return wrapper
    return decorator

def convert_to_markdown(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Convert a URL to markdown using Jina AI's Reader API with enhanced settings.
    Includes retry logic, error handling, and fallback mechanisms.
    
    Args:
        url: The URL to convert to markdown
        timeout: Request timeout in seconds
        
    Returns:
        Markdown content as a string
    
    Advanced options:
      - Uses streaming mode to wait for complete page rendering
      - Includes retry logic with exponential backoff
      - Provides fallback to direct HTML scraping if Jina API fails
    """
    logger.info(f"Converting URL to markdown: {url}")
    
    # First try using Jina AI's Reader API
    try:
        api_url = f"https://r.jina.ai/{url}"
        headers = {
            "Accept": "text/event-stream",       # Enable streaming mode for full content
            "x-respond-with": "markdown",        # Ensure markdown output
            "x-wait-for-selector": "body",       # Wait for body to be loaded
            "User-Agent": USER_AGENT             # Mimic a browser
        }
        
        # Use retry_with_backoff as a function rather than a decorator
        @retry_with_backoff(max_tries=MAX_RETRIES, backoff_factor=BACKOFF_FACTOR)
        def _get_with_retry():
            resp = requests.get(api_url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        
        try:
            response = _get_with_retry()
            
            # Check if we got valid markdown content
            content = response.text
            if content and not content.startswith("Error:"):
                logger.info(f"Successfully converted {url} using Jina API")
                return content
            else:
                logger.warning(f"Jina API returned error content, falling back to direct scraping")
                # Fall through to fallback method
        except requests.RequestException as e:
            logger.warning(f"Jina API request failed after retries: {str(e)}")
            # Fall through to fallback method
    except Exception as e:
        logger.error(f"Unexpected error with Jina API: {str(e)}")
        logger.debug(traceback.format_exc())
    
    # Fallback: Direct HTML scraping
    return fallback_html_to_markdown(url, timeout)

def fallback_html_to_markdown(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    Fallback method to directly scrape HTML and convert to simplified markdown.
    
    Args:
        url: The URL to scrape
        timeout: Request timeout in seconds
        
    Returns:
        Simplified markdown content
    """
    try:
        logger.info(f"Using fallback HTML scraping for {url}")
        headers = {"User-Agent": USER_AGENT}
        
        # Use retry_with_backoff as a function rather than a decorator
        @retry_with_backoff(max_tries=MAX_RETRIES, backoff_factor=BACKOFF_FACTOR)
        def _get_with_retry():
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        
        try:
            response = _get_with_retry()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.extract()
            
            # Extract text content
            text = soup.get_text(separator='\n')
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Add basic markdown formatting
            # Find potential headers (short lines that end with colon)
            lines = text.splitlines()
            formatted_lines = []
            
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    formatted_lines.append('')
                    continue
                    
                # Format potential headers (short lines that might be titles)
                if len(line) < 80 and not line.endswith(':') and not re.match(r'^[\d.]+\s', line):
                    if len(line) < 30:  # Very short lines might be headers
                        formatted_lines.append(f"## {line}")
                    else:
                        formatted_lines.append(f"### {line}")
                # Format potential list items
                elif re.match(r'^[\d.]+\s', line) or re.match(r'^[-•*]\s', line):
                    formatted_lines.append(line)  # Already formatted as a list
                # Format potential section headers (lines ending with colon)
                elif line.endswith(':'):
                    formatted_lines.append(f"### {line}")
                else:
                    formatted_lines.append(line)
            
            markdown = '\n'.join(formatted_lines)
            logger.info(f"Successfully converted {url} using fallback method")
            return markdown
        except requests.RequestException as e:
            logger.error(f"Fallback HTML scraping failed after retries: {str(e)}")
            return f"Error converting {url}: {str(e)}"
    except Exception as e:
        logger.error(f"Fallback HTML scraping failed: {str(e)}")
        logger.debug(traceback.format_exc())
        return f"Error converting {url}: {str(e)}"
