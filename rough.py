from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import time
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

def convert_webpage_to_markdown(url, headless=True):
    """
    Opens a single webpage, waits for it to load completely,
    and converts its content to markdown using the provided 
    convert_to_markdown function.

    :param url: The URL of the webpage to convert.
    :param headless: Boolean indicating whether to run Chrome headless.
    :return: A string containing the markdown-converted content.
    """
    print(f"Launching Chrome browser for {url}...")
    chrome_driver_path = "./chromedriver.exe"  # Update the path as needed
    options = webdriver.ChromeOptions()
    
    if headless:
        options.add_argument("--headless")
    
    # Optional: ignore certificate errors
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-insecure-localhost")

    driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)
    driver.set_page_load_timeout(200)
    wait = WebDriverWait(driver, 30)
    
    try:
        print(f"Opening {url}...")
        time.sleep(5)
        driver.get(url)
        # Wait until the page is fully loaded
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        # Optional delay to ensure all dynamic content has rendered
        time.sleep(13)
        
        # Convert the current webpage to markdown using your function
        markdown_content = convert_to_markdown(url)
        print("Conversion complete.")
    except Exception as e:
        print(f"Error converting page: {e}")
        markdown_content = None
    finally:
        driver.quit()
    
    return markdown_content

# Example usage:
markdown = convert_webpage_to_markdown("https://www.acadian-asset.com/careers/open-positions?gh_jid=4435605006")
print(markdown)
