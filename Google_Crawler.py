# Google_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import sys
import os
import re
from fuzzywuzzy import fuzz
from fake_useragent import UserAgent
import time
import subprocess
import random # Import random for variable sleep
#from News_keyword import keywords, exclude_keywords  # keyword.py에서 가져오기

NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR,'google_News.json')


def load_keywords():
    with open('News_keyword.js', 'r', encoding='utf-8') as f:
        data = json.load(f)
    keywords = [item for cat in data['keywords'] for item in cat['items']]
    exclude_keywords = [item for cat in data['exclude_keywords'] for item in cat['items']]
    return keywords, exclude_keywords
keywords, exclude_keywords = load_keywords()
# Ensure consistent date formatting - using system locale might vary
# Let's keep your original format, assuming the locale is set correctly for Korean day names.
try:
    # Attempt to set locale for Korean day names if needed, might require OS configuration
    # import locale
    # locale.setlocale(locale.LC_TIME, 'ko_KR.UTF-8') # Example for Linux
    today_dt = datetime.now()
    # Manually replace English day name if locale setting is complex/unreliable in the environment
    day_map = {'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일', 'Thursday': '목요일',
               'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'}
    eng_day = today_dt.strftime('%A')
    kor_day = day_map.get(eng_day, eng_day) # Fallback to English if not found
    today = today_dt.strftime(f'%Y년 %m월 %d일 {kor_day}')

except Exception as e:
    print(f"Warning: Could not set locale or format date reliably. Using default. Error: {e}")
    today = datetime.now().strftime('%Y-%m-%d') # Fallback format

urls = [
    'https://news.google.com/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFp4WkRNU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR%3Ako', # 주요 뉴스
    'https://news.google.com/home?hl=ko&gl=KR&ceid=KR%3Ako', # 홈
    'https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR%3Ako', # 과학/기술
    'https://news.google.com/search?q=%ED%99%94%EC%82%B0&hl=ko&gl=KR&ceid=KR%3Ako', # 화산
    'https://news.google.com/search?q=%EB%B0%A9%EC%82%AC%EB%8A%A5&hl=ko&gl=KR&ceid=KR%3Ako', # 방사능
    'https://news.google.com/search?q=%EC%A0%84%EC%97%BC%EB%B3%91&hl=ko&gl=KR&ceid=KR%3Ako', # 전염병
    'https://news.google.com/search?q=%EC%84%B8%EA%B3%84%EC%9E%AC%EB%82%9C&hl=ko&gl=KR&ceid=KR%3Ako', # 세계재난
    'https://news.google.com/search?q=%EC%A7%80%EC%A7%84&hl=ko&gl=KR&ceid=KR%3Ako'  # 지진
]

processed_links = set()
ua = UserAgent()

def is_similar(title1, title2, threshold=35):
    # Compare titles ignoring case and whitespace
    t1 = re.sub(r'\s+', '', title1).lower()
    t2 = re.sub(r'\s+', '', title2).lower()
    return fuzz.ratio(t1, t2) >= threshold

def is_relevant_article(text_content):
    if not text_content: # Handle empty titles/content
        return False
    text_lower = text_content.lower()
    # Check if at least N include keywords are present
    # Using sum(1 for kw in keywords if kw.lower() in text_lower) is slightly more efficient
    keyword_match_count = sum(1 for keyword in keywords if keyword and keyword.lower() in text_lower)

    # Require at least 2 keywords OR handle case with fewer total keywords
    min_required_keywords = min(2, len(keywords)) if keywords else 0
    has_enough_keywords = keyword_match_count >= min_required_keywords

    # Check if any exclude keywords are present
    exclude_match = any(ex_keyword and ex_keyword.lower() in text_lower for ex_keyword in exclude_keywords)

    # Relevant if enough include keywords are found AND no exclude keywords are found
    # Also ensure keywords list is not empty to avoid matching everything if keywords fail to load
    return keywords and has_enough_keywords and not exclude_match


def parse_google_time(time_str):
    """Parses Google News's datetime string and converts to timezone-aware datetime."""
    try:
        # Google uses ISO 8601 format with 'Z' for UTC
        dt_utc = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        # Convert to KST (UTC+9)
        dt_kst = dt_utc + timedelta(hours=9)
        return dt_kst
    except ValueError:
        print(f"Warning: Could not parse time string: {time_str}")
        return None
    except Exception as e:
        print(f"Error parsing time string {time_str}: {e}")
        return None


def is_within_last_days(article_dt, days=2):
    """Checks if the article datetime is within the last N days from now."""
    if not article_dt:
        return False
    # Make sure we compare timezone-aware with timezone-aware or naive with naive
    # Since article_dt is KST (aware), get current time in KST
    now_kst = datetime.now(article_dt.tzinfo) # Use the same timezone info
    cutoff_dt = now_kst - timedelta(days=days)
    return article_dt >= cutoff_dt


def get_existing_links():
    try:
        # Create the file with an empty structure if it doesn't exist
        if not os.path.exists(result_filename):
             with open(result_filename, 'w', encoding='utf-8') as f:
                 json.dump([], f, ensure_ascii=False, indent=2)
             print(f"Created empty {result_filename}")
             return set()

        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Handle potential empty file or invalid JSON
            if not isinstance(data, list):
                print(f"Warning: {result_filename} does not contain a valid JSON list. Resetting.")
                return set()
        # Extract URLs, handling potential missing 'articles' key or non-list 'articles'
        links = set()
        for day_data in data:
            if isinstance(day_data, dict) and 'articles' in day_data and isinstance(day_data['articles'], list):
                for article in day_data['articles']:
                    if isinstance(article, dict) and 'url' in article:
                        links.add(article['url'])
        return links
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {result_filename}. File might be corrupted. Starting fresh.")
        # Optionally backup corrupted file here
        return set() # Return empty set to start fresh
    except FileNotFoundError:
         # This case is handled by the os.path.exists check now, but kept for safety
        print(f"{result_filename} not found. Will be created.")
        return set()
    except Exception as e:
        print(f"Error reading existing links from {result_filename}: {e}")
        return set() # Return empty set on other errors


def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=20) # Increased timeout
        response.raise_for_status() # Check for HTTP errors
        response.encoding = response.apparent_encoding # Detect encoding

        soup = BeautifulSoup(response.text, 'html.parser')

        # Google News structure can change. Find articles by looking for common patterns.
        # 'c-wiz' often contains article groups. 'article' tag is standard.
        # Selectors might need adjustment if Google changes layout.
        # Prioritize elements containing both a link and a time element nearby.
        potential_articles = soup.find_all('article')
        if not potential_articles:
             # Fallback selector if <article> tag isn't used
             potential_articles = soup.select('div.XlKvRb, div.NiLAwe') # Adjust based on inspection

        print(f"Found {len(potential_articles)} potential article elements.")

        processed_article_links_in_page = set() # Avoid duplicates within the same page scrape

        for item in potential_articles:
            link_element = item.find('a', href=True)
            if not link_element:
                continue

            href_link = link_element['href']
            # Resolve relative URLs
            if href_link.startswith('./'):
                href_link = href_link[1:] # Remove leading '.'
            if href_link.startswith('/'):
                full_link = f'https://news.google.com{href_link}'
            elif href_link.startswith('http'):
                 full_link = href_link # Already absolute (less common for main articles)
            else:
                 # Skip potentially malformed or non-article links
                 # print(f"Skipping non-standard link: {href_link}")
                 continue

            # Normalize URL for comparison
            full_link = full_link.replace('https://news.google.com./', 'https://news.google.com/')

            # Skip if already processed from existing file OR within this page scrape
            if full_link in processed_links or full_link in processed_article_links_in_page:
                continue

            title = link_element.get_text(strip=True)
            if not title: # Try finding title in another element if link text is empty/generic
                h_tag = item.find(['h3', 'h4']) # Common tags for titles
                if h_tag:
                    title = h_tag.get_text(strip=True)

            if not title: # Skip if no title found
                # print(f"Skipping item without title: {full_link}")
                continue

            # Check relevance before proceeding further
            if not is_relevant_article(title):
                # print(f"Skipping irrelevant title: {title}")
                continue

            # Find the timestamp
            time_element = item.find('time', datetime=True)
            if not time_element:
                 # print(f"Skipping article without time element: {title}")
                 continue

            time_str = time_element['datetime']
            published_dt_kst = parse_google_time(time_str)

            if not published_dt_kst:
                 # print(f"Skipping article with unparseable time: {title}")
                 continue # Skip if time couldn't be parsed

            # Check if article is recent enough
            if not is_within_last_days(published_dt_kst, days=2):
                # print(f"Skipping old article: {title} ({published_dt_kst})")
                continue

            # Check for similarity with already added articles *in this run*
            is_dup_title = False
            for existing_article in articles:
                if is_similar(title, existing_article['title']):
                    # print(f"Skipping similar title: '{title}' vs '{existing_article['title']}'")
                    is_dup_title = True
                    break
            if is_dup_title:
                continue

            # Find image URL
            img_element = item.find('img', src=True)
            img_url = img_element['src'] if img_element else ''

            # Format time back to string (ISO 8601 with KST offset)
            formatted_time = published_dt_kst.isoformat()

            print(f"  [+] Relevant Article Found: {title} ({formatted_time})")
            articles.append({
                'title': title,
                'time': formatted_time, # Store as ISO string with offset
                'img': img_url,
                'url': full_link,
                'original_url': full_link # Keep original if needed, though it's the same here
            })
            processed_article_links_in_page.add(full_link) # Mark as processed for this page

        return articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return []
    except Exception as e:
        # Catch other potential errors during parsing
        print(f"Error processing page {url}: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
        return []


def save_to_json(new_articles):
    try:
        # Read existing data
        if os.path.exists(result_filename):
            with open(result_filename, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                         print(f"Warning: {result_filename} is not a list. Initializing fresh.")
                         existing_data = []
                except json.JSONDecodeError:
                    print(f"Warning: Error decoding JSON from {result_filename}. Initializing fresh.")
                    existing_data = [] # Start fresh if file is corrupt
        else:
            existing_data = []

        # Find data for today
        today_entry = None
        for entry in existing_data:
            if isinstance(entry, dict) and entry.get('date') == today:
                today_entry = entry
                break

        added_count = 0
        if new_articles:
            unique_new_articles = []
             # Ensure today's entry exists and has an 'articles' list
            if today_entry:
                 if 'articles' not in today_entry or not isinstance(today_entry['articles'], list):
                     today_entry['articles'] = [] # Fix if 'articles' key is missing/invalid
            else:
                 # Create new entry for today if it doesn't exist
                 today_entry = {'date': today, 'articles': []}
                 existing_data.append(today_entry) # Add to the main list

             # Get existing URLs for today to prevent duplicates within the day's entry
            existing_urls_today = {article.get('url') for article in today_entry['articles'] if isinstance(article, dict)}

            for article in new_articles:
                # Double-check uniqueness based on URL before adding
                if article['url'] not in processed_links and article['url'] not in existing_urls_today:
                    unique_new_articles.append(article)
                    processed_links.add(article['url']) # Update global set
                    existing_urls_today.add(article['url']) # Update today's set
                    added_count += 1

            if unique_new_articles:
                # Add the truly new articles to today's entry
                today_entry['articles'].extend(unique_new_articles)
                # Optional: Sort articles by time (descending)
                today_entry['articles'].sort(key=lambda x: x.get('time', ''), reverse=True)

        # Always write the file back, even if no new articles were added,
        # to ensure the file exists and contains the (potentially updated) structure.
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)

        if added_count > 0:
            print(f"Successfully added {added_count} new articles for {today} to {result_filename}")
        elif new_articles:
            print(f"No *unique* new articles found to add for {today}. {result_filename} updated.")
        else:
            print(f"No new articles were scraped. {result_filename} remains unchanged or initialized.")

    except IOError as e:
        print(f"Error writing to {result_filename}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during save_to_json: {e}")
        import traceback
        traceback.print_exc()


def main():
    global processed_links
    # Load existing links first, ensuring the file exists
    processed_links = get_existing_links()
    print(f"Loaded {len(processed_links)} existing article URLs.")

    all_new_articles = []

    print(f"\n--- Starting Google News Scraping for {today} ---")
    if not keywords:
        print("Warning: No include keywords loaded. Relevance check might not work as expected.")

    for url in urls:
        articles = scrape_page(url)
        if articles: # Only extend if articles were actually found for this URL
             all_new_articles.extend(articles)
        # Use a variable sleep time to be less predictable
        sleep_time = random.uniform(1.5, 4.0)
        print(f"Sleeping for {sleep_time:.1f} seconds...")
        time.sleep(sleep_time)

    print(f"\n--- Scraping Finished ---")
    print(f"Total potential new articles found across all sources: {len(all_new_articles)}")

    # --- This is the key change ---
    # Always call save_to_json.
    # It handles adding new articles if found, and ensures the file exists otherwise.
    save_to_json(all_new_articles)
    # --- End of key change ---

    print(f"--- Process Completed ---")


if __name__ == "__main__":
    main()
