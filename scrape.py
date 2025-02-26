import json
import selenium.webdriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import re
from urllib.parse import urlparse, urlunparse
import pandas as pd
from html_to_markdown import convert_to_markdown

from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate

import os
from dotenv import load_dotenv
load_dotenv()  # Loads variables from .env into the environment

# Now get the OPENAI_API_KEY from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")

# Instantiate the OpenAI model (adjust temperature and model_name as needed)
model = ChatOpenAI(temperature=0, model_name="gpt-4o-mini", openai_api_key=openai_api_key)

# --------------------------------------------------------------------------
# 1) LLM-based link classification using OpenAI API
# --------------------------------------------------------------------------

LINK_CLASSIFICATION_TEMPLATE = """
You are a helpful AI assistant. Determine if the following link likely leads to a job posting.
Respond ONLY with 'YES' if it is likely a job, or '' if not.

Here is the link text: "{link_text}"
And here is the link URL: "{link_href}"
""".strip()

def is_job_posting_link(link) -> bool:
    """
    Uses OpenAI's API to determine if a given <a> tag likely leads to a job posting
    by examining both its text and its URL.
    """
    link_text = link.text.strip() or ""
    link_href = link.get_attribute("href") or ""

    # If there's neither text nor href, skip
    if not link_text and not link_href:
        return False

    print(link_text, link_href)
    prompt = ChatPromptTemplate.from_template(LINK_CLASSIFICATION_TEMPLATE)
    chain = LLMChain(llm=model, prompt=prompt)

    response = chain.run({"link_text": link_text, "link_href": link_href})
    print(f"LLM response => {response}, link_text='{link_text}', link_href='{link_href}'")

    return response.strip().upper() == "YES"


# --------------------------------------------------------------------------
# 2) LLM-based job posting extraction using OpenAI API
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

def extract_job_postings(dom_chunks):
    """
    Given a list of DOM (markdown) chunks, uses the OpenAI API to extract job postings
    as a JSON list of objects: [{"title": "...", "location": "...", ...}, ...].
    Returns a concatenated list of job posting dictionaries.
    """
    prompt = ChatPromptTemplate.from_template(JOB_POSTING_EXTRACTION_TEMPLATE)
    chain = LLMChain(llm=model, prompt=prompt)

    all_postings = []
    print("Dom Chunk:\n", dom_chunks)
    for chunk in dom_chunks:
         # 1) Remove anchor references from the markdown chunk.
        preprocessed_chunk = re.sub(LINK_PATTERN, "", chunk)

        print("Chunk:\n", preprocessed_chunk)
        response = chain.run({"dom_content": preprocessed_chunk})
        print("LLM Raw Response:\n", response)

        # Clean the response by removing any extraneous prefixes like "json"
        clean_response = response.strip()
        print(clean_response[:10])
        # Remove starting and ending triple backticks (with optional language tag)
        clean_response = re.sub(r"^```(?:json)?\s*", "", clean_response, flags=re.IGNORECASE)
        clean_response = re.sub(r"\s*```$", "", clean_response)
        try:
            postings = json.loads(clean_response)
            if isinstance(postings, dict):
                postings = [postings]
            if isinstance(postings, list):
                all_postings.extend(postings)
        except Exception as e:
            print("JSON parsing Exception:", e)
            pass

    return all_postings

def random_clicks(driver, clicks=3, wait_time=2):
    """
    Simulates random clicks on the screen to trigger dynamic content loading.
    It selects random coordinates within the viewport and clicks the element at that point.
    """
    try:
        width = driver.execute_script("return window.innerWidth")
        height = driver.execute_script("return window.innerHeight")
        for i in range(clicks):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            try:
                element = driver.execute_script(
                    "return document.elementFromPoint(arguments[0], arguments[1]);", x, y)
                if element:
                    driver.execute_script("arguments[0].click();", element)
                    print(f"Random click {i+1} at coordinates ({x}, {y}) on element {element.tag_name}.")
                else:
                    print(f"Random click {i+1} at ({x}, {y}) found no element.")
            except Exception as e:
                print(f"Random click {i+1} failed at ({x}, {y}): {e}")
            time.sleep(wait_time)
    except Exception as e:
        print("Error during random clicks:", e)

def scrape_website(start_url, max_depth=2, max_breadth=10, headless=True):
    """
    Recursively scrape a website starting from `start_url`, up to `max_depth` levels,
    following at most `max_breadth` links on each page.

    Only follows links within the same domain.
    Excludes any links found inside <footer> elements.
    Optionally runs the browser headless or visible.

    :param start_url: The initial URL to begin scraping.
    :param max_depth: How many levels deep to recurse.
    :param max_breadth: Maximum links to follow from each page.
    :param headless: Boolean indicating whether to run Chrome headless (True) or visible (False).
    :return: A DataFrame containing the scraped job postings.
    """

    print("Launching Chrome browser...")
    chrome_driver_path = "./chromedriver.exe"  # Update path as needed
    options = webdriver.ChromeOptions()

    # Toggle headless mode based on the parameter
    if headless:
        options.add_argument("--headless")
    
    # (Optional) Ignore cert errors if needed:
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-insecure-localhost")

    driver = webdriver.Chrome(service=Service(chrome_driver_path), options=options)

    # Increase the page load timeout for slow or large pages
    driver.set_page_load_timeout(200)

    # We'll use an explicit WebDriverWait for elements on each page
    wait = WebDriverWait(driver, 30)  # Wait up to 30 seconds for specific conditions

    # Keep track of visited URLs to avoid cycles
    visited = set()
    # Parse the domain to ensure we only follow links within the same site
    domain = urlparse(start_url).netloc

    # We'll collect all job postings in a list
    all_job_postings = []

    def remove_fragment(href):
        """
        Remove the URL fragment (#some-anchor) so links like
        'https://example.com/page#section' become 'https://example.com/page'.
        This prevents re-scraping the same page with different anchors.
        """
        parsed = urlparse(href)
        return urlunparse(parsed._replace(fragment=""))

    def repeatedly_scroll(driver, scroll_pause=2, max_scrolls=5):
        """
        A generic approach to handle lazy-loading or infinite-scroll.
        Scroll down multiple times, waiting a bit for content to load.
        Stop early if the page height doesn't change significantly.
        """
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_count = 0

        while scroll_count < max_scrolls:
            # Scroll down to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # No more content loaded
                print("No more new content. Stopping scroll.")
                break

            last_height = new_height
            scroll_count += 1
            print(f"Scroll iteration {scroll_count} done.")

    def recurse_scrape(url, depth):
        """Recursively scrape `url` up to the specified `max_depth`."""
        # Stop if we've reached or exceeded the maximum depth
        if depth >= max_depth:
            return

        try:
            print(f"Scraping {url} at depth {depth}...")
            driver.get(url)

            # Wait for the <body> to be present, indicating the page has (mostly) loaded
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # (Optional) Slight random delay to prevent rapid-fire requests
            time.sleep(8)
            time.sleep(random.uniform(10, 17))

            # Attempt multiple scrolls for lazy-loaded job listings
            repeatedly_scroll(driver, scroll_pause=2, max_scrolls=5)

            # Simulate random clicks to trigger additional dynamic content loading
            random_clicks(driver, clicks=random.randint(1, 3), wait_time=random.uniform(1, 3))
            time.sleep(2)
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
            time.sleep(2)
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
                else:
                    print("apply link not found")

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
