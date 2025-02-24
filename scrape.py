import selenium.webdriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
from urllib.parse import urlparse, urlunparse

from html_to_markdown import convert_to_markdown
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
 


def scrape_website(start_url, max_depth=2, max_breadth=10, headless=True):
    """
    Recursively scrape a website starting from start_url, up to max_depth levels,
    following at most max_breadth links on each page.

    Only follows links within the same domain.
    Excludes any links found inside <footer> elements.
    Optionally runs the browser headless or visible.

    :param start_url: The initial URL to begin scraping.
    :param max_depth: How many levels deep to recurse.
    :param max_breadth: Maximum links to follow from each page.
    :param headless: Boolean indicating whether to run Chrome headless (True) or visible (False).
    :return: A list of page titles (or other extracted data).
    """

    print("Launching Chrome browser...")
    chrome_driver_path = "./chromedriver.exe"  # Update path as needed
    options = webdriver.ChromeOptions()

    # Toggle headless mode based on the parameter
    if headless:
        options.add_argument("--headless")
    
    # (Optional) Ignore cert errors if needed:
    # options.add_argument("--ignore-certificate-errors")
    # options.add_argument("--allow-insecure-localhost")

    driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)

    # Increase the page load timeout for slow or large pages
    driver.set_page_load_timeout(120)

    # We'll use an explicit WebDriverWait for elements on each page
    wait = WebDriverWait(driver, 30)  # Wait up to 30 seconds for specific conditions

    # Keep track of visited URLs to avoid cycles
    visited = set()
    # Parse the domain to ensure we only follow links within the same site
    domain = urlparse(start_url).netloc

    # This list will hold the scraping results (page titles, or any data you collect)
    results = []

    def remove_fragment(href):
        """
        Remove the URL fragment (#some-anchor) so links like
        'https://example.com/page#section' become 'https://example.com/page'.
        This prevents re-scraping the same page with different anchors.
        """
        parsed = urlparse(href)
        return urlunparse(parsed._replace(fragment=""))

    def recurse_scrape(url, depth):
        """Recursively scrape url up to the specified max_depth."""
        # Stop if we've reached or exceeded the maximum depth
        if depth >= max_depth:
            return

        try:
            print(f"Scraping {url} at depth {depth}...")
            driver.get(url)

            # Wait for the <body> to be present, indicating the page has (mostly) loaded
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # (Optional) Slight random delay to prevent rapid-fire requests
            time.sleep(random.uniform(1.0, 3.0))

            # Get all links in footer so we can exclude them
            footer_links = set()
            footers = driver.find_elements(By.TAG_NAME, "footer")
            for footer in footers:
                links_in_footer = footer.find_elements(By.TAG_NAME, "a")
                for lf in links_in_footer:
                    href = lf.get_attribute("href")
                    if href:
                        footer_links.add(href)

            # Gather and filter page links
            page_links = driver.find_elements(By.TAG_NAME, "a")
            valid_links = []
            for link in page_links:
                href = link.get_attribute("href")
                if not href:
                    continue

                # Strip out #fragment so we don't treat anchors as new pages
                clean_href = remove_fragment(href)

                # Restrict to same domain and exclude footer links
                parsed_href = urlparse(clean_href)
                if parsed_href.netloc == domain and clean_href not in footer_links:
                    # Skip mailto:, tel:, javascript:, or repeated visits
                    if clean_href.startswith("http") and clean_href not in visited:
                        valid_links.append(clean_href)

            # Limit the number of links we follow from this page
            valid_links = valid_links[:max_breadth]

            # Convert the current page to markdown using Jina API
            markdown_content = convert_to_markdown(url)
            results.append(markdown_content)

            # Mark these links visited and recurse
            for link_url in valid_links:
                visited.add(link_url)
                recurse_scrape(link_url, depth + 1)

        except Exception as e:
            print(f"Error scraping {url}: {e}")

    try:
        # Start recursion
        visited.add(start_url)
        recurse_scrape(start_url, 0)
        return results
    finally:
        print("Closing Chrome browser.")
        driver.quit()