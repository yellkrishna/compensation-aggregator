import requests

def convert_to_markdown(url):
    """Convert a URL to markdown using Jina AI’s Reader API."""
    api_url = f"https://r.jina.ai/{url}"
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        return response.text  # Markdown content
    except Exception as e:
        print(f"Error converting {url} to markdown: {e}")
        return f"Error converting {url}"