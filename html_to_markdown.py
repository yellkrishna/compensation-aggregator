import requests

def convert_to_markdown(url):
    """
    Convert a URL to markdown using Jina AI’s Reader API with enhanced settings.
    
    Advanced options:
      - Uses streaming mode to wait for complete page rendering.
      - Increases timeout for slower pages.
      - Sets additional headers to control output format.
    """
    api_url = f"https://r.jina.ai/{url}"
    headers = {
        "Accept": "text/event-stream",       # Enable streaming mode for full content
        "x-respond-with": "markdown",        # Ensure markdown output; try "html" if needed
        # Uncomment below to wait for a specific element to appear
        # "x-wait-for-selector": "body",      
        # Uncomment to mimic a browser (if needed)
        # "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.text  # Markdown content
    except Exception as e:
        print(f"Error converting {url} to markdown: {e}")
        return f"Error converting {url}"
