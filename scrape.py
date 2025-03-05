import json
import selenium.webdriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException
)
import time
import random
import re
from urllib.parse import urlparse, urlunparse
import pandas as pd
from html_to_markdown import convert_to_markdown
import logging
import traceback
from typing import List, Dict, Any, Optional, Tuple, Set
import socket
import requests
from requests.exceptions import RequestException
from functools import wraps
import backoff

from openai import OpenAI

import os
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
try:
    load_dotenv()  # Loads variables from .env into the environment
except Exception as e:
    logger.error(f"Error loading .env file: {str(e)}")

# Now get the OPENAI_API_KEY from environment variables
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Retry decorator for network operations
def retry_with_backoff(max_tries=3, backoff_factor=2):
    """Retry decorator with exponential backoff for network operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_tries):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, socket.error, TimeoutException) as e:
                    if attempt == max_tries - 1:
                        logger.error(f"Failed after {max_tries} attempts: {str(e)}")
                        raise
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Attempt {attempt+1} failed: {str(e)}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        return wrapper
    return decorator

# --------------------------------------------------------------------------
# 1) Link classification using OpenAI API with fallback to heuristics
# --------------------------------------------------------------------------

LINK_CLASSIFICATION_TEMPLATE = """
You are a helpful AI assistant. Determine if the following link likely leads to a job posting.
Respond ONLY with 'YES' if it is likely a job, or '' if not.

Here is the link text: "{link_text}"
And here is the link URL: "{link_href}"
""".strip()

def call_openai_api(prompt_text, model_name="gpt-3.5-turbo", temperature=0):
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error calling OpenAI ChatCompletion: {str(e)}")
        return ""

@retry_with_backoff(max_tries=2, backoff_factor=1)
def is_job_posting_link(link) -> bool:
    """
    Uses OpenAI's API to determine if a given <a> tag likely leads to a job posting
    by examining both its text and its URL. Falls back to heuristics if LLM is unavailable.
    """
    try:
        link_text = link.text.strip() or ""
        link_href = link.get_attribute("href") or ""

        # If there's neither text nor href, skip
        if not link_text and not link_href:
            return False

        logger.debug(f"Evaluating link: text='{link_text}', href='{link_href}'")
        

        # Build the prompt
        prompt = LINK_CLASSIFICATION_TEMPLATE.format(
            link_text=link_text,
            link_href=link_href
        )
        response = call_openai_api(prompt_text=prompt, model_name="gpt-4", temperature=0)
        logger.debug(f"OpenAI response => {response}")
        return response.strip().upper() == "YES"
    except StaleElementReferenceException:
        logger.warning("Stale element reference when evaluating link")
        return False
    except Exception as e:
        logger.error(f"Error evaluating link: {str(e)}")
        return False


# --------------------------------------------------------------------------
# 2) Job posting extraction using OpenAI API with fallback to regex
# --------------------------------------------------------------------------

JOB_POSTING_EXTRACTION_TEMPLATE = r"""
You are an expert job posting extractor.

Extract the job posting details from the text below. Only extract the following details:
- Job Title (key: "title")
- Job Description (key: "description")
- Salary Range (key: "salary_range")
- Responsibilities (key: "responsibilities")
- Location (key: "location")
- Qualification (key: "qualification")

For each job posting, if any of the above details are not present, include the key in the JSON with an empty string as its value.

Ignore any partial job details that exist only in a hyperlink.
Return only job postings that are fully described in the visible text.

Return the job postings as a valid JSON list, where each posting is a JSON object with the keys specified above.

If there is only one job posting, return a list with exactly one JSON object.
If there are multiple postings, return a list containing multiple JSON objects.
If no job posting is found, return an empty list: [].

Output format: valid JSON only, without triple backticks or any extra text.

Text:
{dom_content}
""".strip()

# Example pattern to remove anchor text + URL:
LINK_PATTERN = r"\[.*?\]\(.*?\)"

@retry_with_backoff(max_tries=2, backoff_factor=1)
def extract_job_postings(dom_chunks: List[str]) -> List[Dict[str, str]]:
    """
    Given a list of DOM (markdown) chunks, extracts job postings using OpenAI API
    with fallback to regex-based extraction.
    Returns a concatenated list of job posting dictionaries.
    """
    all_postings = []
    logger.debug(f"Processing {len(dom_chunks)} DOM chunks")
    
    for chunk in dom_chunks:
        try:
            # 1) Remove anchor references from the markdown chunk
            preprocessed_chunk = re.sub(LINK_PATTERN, "", chunk)
            

            prompt = JOB_POSTING_EXTRACTION_TEMPLATE.format(dom_content=preprocessed_chunk)
            response_text = call_openai_api(prompt_text=prompt, model_name="gpt-4", temperature=0)
            logger.debug("OpenAI extraction completed")
                
            # Clean the response
            clean_response = response_text.strip()
            clean_response = re.sub(r"^(?:json)?\s*", "", clean_response, flags=re.IGNORECASE)
            clean_response = re.sub(r"\s*$", "", clean_response)
                
            try:
                postings = json.loads(clean_response)
                if isinstance(postings, dict):
                    postings = [postings]
                if isinstance(postings, list):
                    all_postings.extend(postings)
                    logger.info(f"Extracted {len(postings)} job postings using OpenAI")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing error: {str(e)}, falling back to regex extraction")
        except Exception as e:
            logger.error(f"Error processing chunk: {str(e)}")
            logger.debug(traceback.format_exc())
    
    return all_postings

def safe_random_clicks(driver, clicks=3, wait_time=2):
    """
    Safely simulates random clicks on the screen to trigger dynamic content loading.
    Includes error handling and recovery for failed clicks.
    """
    successful_clicks = 0
    try:
        width = driver.execute_script("return window.innerWidth")
        height = driver.execute_script("return window.innerHeight")
        
        for i in range(clicks):
            try:
                # Generate random coordinates within the viewport
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                
                # Find element at coordinates
                element = driver.execute_script(
                    "return document.elementFromPoint(arguments[0], arguments[1]);", x, y)
                
                if element:
                    # Skip clicking on certain elements that might navigate away
                    tag_name = element.tag_name.lower()
                    if tag_name in ['a', 'button']:
                        href = element.get_attribute('href') if tag_name == 'a' else None
                        if href and ('logout' in href.lower() or 'sign-out' in href.lower()):
                            logger.debug(f"Skipping click on logout/sign-out element at ({x}, {y})")
                            continue
                    
                    # Try to click the element
                    try:
                        driver.execute_script("arguments[0].click();", element)
                        logger.debug(f"Random click {i+1} at coordinates ({x}, {y}) on element {element.tag_name}")
                        successful_clicks += 1
                    except ElementClickInterceptedException:
                        # If click is intercepted, try scrolling a bit and retry
                        driver.execute_script("window.scrollBy(0, 100);")
                        time.sleep(0.5)
                        try:
                            driver.execute_script("arguments[0].click();", element)
                            logger.debug(f"Random click {i+1} succeeded after scrolling")
                            successful_clicks += 1
                        except Exception:
                            logger.debug(f"Random click {i+1} failed even after scrolling")
                else:
                    logger.debug(f"Random click {i+1} at ({x}, {y}) found no element")
            except Exception as e:
                logger.warning(f"Random click {i+1} failed at ({x}, {y}): {str(e)}")
            
            # Wait between clicks
            time.sleep(wait_time)
    except Exception as e:
        logger.error(f"Error during random clicks: {str(e)}")
    
    return successful_clicks

def scrape_website(start_url, max_depth=2, max_breadth=10, headless=True, timeout=60):
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
    :param timeout: Page load timeout in seconds.
    :return: A DataFrame containing the scraped job postings.
    """
    logger.info(f"Starting scrape of {start_url} (depth={max_depth}, breadth={max_breadth})")
    
    # Initialize Chrome options with error handling
    try:
        logger.info("Launching Chrome browser...")
        chrome_driver_path = "./chromedriver.exe"  # Update path as needed
        options = webdriver.ChromeOptions()

        # Toggle headless mode based on the parameter
        if headless:
            options.add_argument("--headless")
        
        # Ignore certificate errors
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-insecure-localhost")
        
        # Add additional stability options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        
        # Set user agent to avoid detection
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        
        # Create service with error handling
        try:
            service = Service(chrome_driver_path)
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.error(f"Error creating Chrome service: {str(e)}")
            # Try alternative approach without explicit service
            driver = webdriver.Chrome(options=options)
        
        # Set page load timeout
        driver.set_page_load_timeout(timeout)
        
        # Create WebDriverWait with appropriate timeout
        wait = WebDriverWait(driver, min(30, timeout/2))  # Wait up to 30 seconds or half the timeout
    except Exception as e:
        logger.critical(f"Failed to initialize Chrome browser: {str(e)}")
        logger.debug(traceback.format_exc())
        # Return empty DataFrame on browser initialization failure
        return pd.DataFrame()

    # Keep track of visited URLs to avoid cycles
    visited = set()
    # Parse the domain to ensure we only follow links within the same site
    try:
        domain = urlparse(start_url).netloc
    except Exception as e:
        logger.error(f"Error parsing URL {start_url}: {str(e)}")
        domain = ""  # Default to empty string if parsing fails

    # We'll collect all job postings in a list
    all_job_postings = []
    
    # Track errors for reporting
    errors = []

    def remove_fragment(href):
        """
        Remove the URL fragment (#some-anchor) so links like
        'https://example.com/page#section' become 'https://example.com/page'.
        This prevents re-scraping the same page with different anchors.
        """
        try:
            parsed = urlparse(href)
            return urlunparse(parsed._replace(fragment=""))
        except Exception as e:
            logger.warning(f"Error removing fragment from URL {href}: {str(e)}")
            return href  # Return original URL if parsing fails

    def safe_repeatedly_scroll(driver, scroll_pause=2, max_scrolls=5):
        """
        Safely handle lazy-loading or infinite-scroll with error recovery.
        Scroll down multiple times, waiting for content to load.
        Stop early if the page height doesn't change significantly.
        """
        try:
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count = 0
            successful_scrolls = 0

            while scroll_count < max_scrolls:
                try:
                    # Scroll down to bottom
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause)

                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        # No more content loaded
                        logger.debug("No more new content. Stopping scroll.")
                        break

                    last_height = new_height
                    scroll_count += 1
                    successful_scrolls += 1
                    logger.debug(f"Scroll iteration {scroll_count} done.")
                except Exception as e:
                    logger.warning(f"Error during scroll iteration {scroll_count}: {str(e)}")
                    scroll_count += 1
                    # Short pause before continuing
                    time.sleep(1)
            
            return successful_scrolls
        except Exception as e:
            logger.error(f"Critical error during scrolling: {str(e)}")
            return 0

    def recurse_scrape(url, depth):
        """Recursively scrape url up to the specified max_depth."""
        # Stop if we've reached or exceeded the maximum depth
        if depth >= max_depth:
            return

        try:
            print(f"Scraping {url} at depth {depth}...")
            driver.get(url)
            time.sleep(5)
            # Wait for the <body> to be present, indicating the page has (mostly) loaded
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # (Optional) Slight random delay to prevent rapid-fire requests
            time.sleep(5)
            time.sleep(random.uniform(10, 17))

            # Attempt multiple scrolls for lazy-loaded job listings
            safe_repeatedly_scroll(driver, scroll_pause=2, max_scrolls=5)

            # Simulate random clicks to trigger additional dynamic content loading
            safe_random_clicks(driver, clicks=random.randint(1, 3), wait_time=random.uniform(1, 3))
            time.sleep(5)
            valid_job_posting_links = []
            # --- Process iframes ---
            iframe_elements = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframe_elements:
                src = iframe.get_attribute("src")
                if src and src not in visited:
                    visited.add(src)
                    try:
                        driver.switch_to.frame(iframe)
                        print(f"Scraping iframe with src: {src}")
                        # Convert the iframe content to markdown using its src URL and extract job postings
                        markdown_content = convert_to_markdown(src)
                        job_data = extract_job_postings([markdown_content])
                        if job_data:
                            all_job_postings.extend(job_data)
                        # Also, extract links from the iframe's document
                        iframe_links = driver.find_elements(By.TAG_NAME, "a")
                        for link in iframe_links:
                            href = link.get_attribute("href")
                            link_text = link.text.strip().lower()
                            if not href:
                                continue
                            clean_href = remove_fragment(href)
                            parsed_href = urlparse(clean_href)
                            if (parsed_href.netloc == domain and clean_href not in visited and 
                                clean_href.startswith("http")):
                                if is_job_posting_link(link):
                                    valid_job_posting_links.append(clean_href)
                        driver.switch_to.default_content()
                    except Exception as e:
                        print(f"Error processing iframe with src {src}: {e}")
                        driver.switch_to.default_content()

            # Process main document links
            # Get all links in footer so we can exclude them
            footer_links = set()
            footers = driver.find_elements(By.TAG_NAME, "footer")
            for footer in footers:
                links_in_footer = footer.find_elements(By.TAG_NAME, "a")
                for lf in links_in_footer:
                    href = lf.get_attribute("href")
                    if href:
                        footer_links.add(href)

            # Get all links in header so we can exclude them
            header_links = set()
            headers = driver.find_elements(By.TAG_NAME, "header")
            for header in headers:
                links_in_header = header.find_elements(By.TAG_NAME, "a")
                for lh in links_in_header:
                    href = lh.get_attribute("href")
                    if href:
                        header_links.add(href)

            # Get all links in nav so we can exclude them
            nav_links = set()
            navs = driver.find_elements(By.TAG_NAME, "nav")
            for nav in navs:
                links_in_nav = nav.find_elements(By.TAG_NAME, "a")
                for nl in links_in_nav:
                    href = nl.get_attribute("href")
                    if href:
                        nav_links.add(href)

            # Combine all ignored links from footer, header, and nav
            ignored_links = footer_links.union(header_links, nav_links)

            # Gather and filter page links
            page_links = driver.find_elements(By.TAG_NAME, "a")
            
            apply_link_found = False
            for link in page_links:
                href = link.get_attribute("href")
                link_text = link.text.strip().lower()
                
                if not href:
                    continue

                # Strip out #fragment so we don't treat anchors as new pages
                clean_href = remove_fragment(href)

                # Restrict to same domain and exclude footer links and skip mailto:, tel:, javascript:, or repeated visits
                parsed_href = urlparse(clean_href)

                if any(keyword in link_text for keyword in ["apply", "submit"]):
                    apply_link_found = True
                    print(f"Apply link found: {clean_href}")

                if parsed_href.netloc == domain and clean_href not in ignored_links and clean_href.startswith("http") and clean_href not in visited:
                    if is_job_posting_link(link):
                        valid_job_posting_links.append(clean_href)

            # Limit the number of links we follow from this page
            valid_job_posting_links = valid_job_posting_links[:max_breadth]
            print("valid postings: \n", valid_job_posting_links)
            print(f"Depth {depth} => Found {len(valid_job_posting_links)} valid job links")

            # If no valid job links are found on this page, skip further processing.
            if not valid_job_posting_links and not apply_link_found:
                print("No valid job links found on this page; skipping further processing at this depth.")
                return

            if apply_link_found:
                # Convert the current page to markdown using Jina API
                time.sleep(5)
                markdown_content = convert_to_markdown(url)
                print("Markdown:\n", markdown_content)

                # Use LLM to extract job postings from this page’s markdown
                job_data = extract_job_postings([markdown_content])
                print("Job Content:\n", job_data)
                if job_data:
                    # If we found job postings, add them to the global list
                    all_job_postings.extend(job_data)
            else:
                # If there's no apply link, skip extracting from this page
                # (It's presumably just a listing page with partial details)
                pass

            # Mark these links visited and recurse
            for link_url in valid_job_posting_links:
                visited.add(link_url)
                recurse_scrape(link_url, depth + 1)

        except Exception as e:
            print(f"Error scraping {url}: {e}")

    try:
        # Start recursion
        visited.add(start_url)
        recurse_scrape(start_url, 0)

        # Convert all job postings to a DataFrame
        df = pd.DataFrame(all_job_postings)
        return df
    finally:
        print("Closing Chrome browser.")
        driver.quit()


def scrape_websites(url_list, max_depth=2, max_breadth=10, headless=True):
    """
    Scrapes multiple websites from a list of URLs.
    For each URL, it calls the scrape_website function and aggregates the results.
    
    :param url_list: A list of URLs to scrape.
    :param max_depth: Maximum recursion depth for each site.
    :param max_breadth: Maximum number of links to follow on each page.
    :param headless: Boolean indicating whether Chrome should run headless.
    :return: A DataFrame containing all job postings from the provided URLs.
    """
    all_dfs = []
    for url in url_list:
        print(f"Starting scrape for {url}...")
        df = scrape_website(url, max_depth=max_depth, max_breadth=max_breadth, headless=headless)
        if not df.empty:
            all_dfs.append(df)
        else:
            print(f"No job postings found for {url}.")
    
    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    else:
        return pd.DataFrame()
    