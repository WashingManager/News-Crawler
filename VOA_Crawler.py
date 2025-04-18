# VOA_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'lib')))
from keywords import keywords, exclude_keywords

result_filename = 'voa_News.json'
today = datetime.now().strftime('%Y년 %m월 %d일 %A').replace('Friday', '금요일')

urls = [
    'https://www.voakorea.com/z/2767',
    'https://www.voakorea.com/z/2768',
    'https://www.voakorea.com/z/2769',
    'https://www.voakorea.com/z/2824',
    'https://www.voakorea.com/z/6936',
    'https://www.voakorea.com/z/2698'
]

processed_links = set()

def is_relevant_article(text_content):
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword.lower() for keyword in keywords if keyword.lower() in words]
    exclude_match = any(keyword.lower() in words for keyword in exclude_keywords)
    return len(matching_keywords) >= 2 and not exclude_match

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        return set()

def process_article(element):
    href_link = element.find('a')['href']
    if not href_link.startswith('http'):
        href_link = 'https://www.voakorea.com' + href_link
    
    if href_link in processed_links:
        return None
    
    title_element = element.find('h4', class_='media-block__title')
    text_content = title_element.text.strip() if title_element else ''
    
    if is_relevant_article(text_content):
        time_element = element.find('span', class_='date')
        published_time = time_element.text.strip() if time_element else ''
        try:
            parsed_time = datetime.strptime(published_time, '%Y-%m-%d %H:%M')
            formatted_time = parsed_time.isoformat()
        except ValueError:
            return None
        
        img_element = element.find('img')
        img_url = img_element.get('src') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = 'https://www.voakorea.com' + img_url
        
        processed_links.add(href_link)
        return {
            'title': text_content,
            'time': formatted_time,
            'img': img_url,
            'url': href_link,
            'original_url': href_link
        }
    return None

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('div.media-block')
        print(f"Found {len(relevant_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_article, element) for element in relevant_elements]
            for future in as_completed(futures):
                article = future.result()
                if article:
                    articles.append(article)
        
        return articles
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
        return []

def save_to_json(new_articles):
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        existing_data = []
    
    today_data = next((d for d in existing_data if d['date'] == today), None)
    if today_data:
        today_data['articles'].extend(new_articles)
    else:
        existing_data.append({'date': today, 'articles': new_articles})
    
    with open(result_filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(new_articles)} articles to {result_filename}")

def main():
    global processed_links
    processed_links = get_existing_links()
    all_articles = []
    
    for url in urls:
        articles = scrape_page(url)
        all_articles.extend(articles)
    
    if all_articles:
        save_to_json(all_articles)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()
