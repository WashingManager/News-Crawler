# YNA_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

result_filename = 'yna_News.json'
today = datetime.now().strftime('%Y년 %m월 %d일 %A').replace('Friday', '금요일')

def get_keywords():
    try:
        result = subprocess.run(
            ['node', '-e', 'const k = require("./keyword.js"); console.log(JSON.stringify(k.getKeywords()));'],
            capture_output=True, text=True, check=True
        )
        keywords = json.loads(result.stdout)
        print(f"Loaded keywords: {keywords}")
        return keywords.get('include', []), keywords.get('exclude', [])
    except Exception as e:
        print(f"키워드 로드 실패: {e}")
        return [], []

keywords, exclude_keywords = get_keywords()

base_urls = [
    'https://www.yna.co.kr/nk/news/politics',
    'https://www.yna.co.kr/nk/news/military',
    'https://www.yna.co.kr/nk/news/diplomacy',
    'https://www.yna.co.kr/nk/news/economy',
    'https://www.yna.co.kr/nk/news/society',
    'https://www.yna.co.kr/nk/news/cooperation',
    'https://www.yna.co.kr/nk/news/correspondents',
    'https://www.yna.co.kr/nk/news/advisory-column'
]

processed_links = set()

def is_relevant_article(full_text):
    if not keywords:
        return True
    text_lower = full_text.lower()
    matching_keywords = [keyword.lower() for keyword in keywords if keyword.lower() in text_lower]
    exclude_match = any(keyword.lower() in text_lower for keyword in exclude_keywords)
    return len(matching_keywords) >= 2 and not exclude_match

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        return set()

def process_article(article, base_url):
    title_element = article.select_one('span.title01')
    title = title_element.text.strip() if title_element else ''
    if not title:
        return None
    
    link_element = article.select_one('a.tit-news')
    href_link = link_element['href'] if link_element else ''
    if not href_link:
        return None
    
    full_link = 'https:' + href_link if href_link.startswith('//') else href_link
    parsed_url = urllib.parse.urlparse(full_link)
    clean_link = urllib.parse.urlunparse(parsed_url._replace(query=''))
    
    if clean_link in processed_links:
        return None
    
    lead_element = article.select_one('p.lead')
    lead = lead_element.text.strip() if lead_element else ''
    full_text = f"{title} {lead}"
    
    if not is_relevant_article(full_text):
        return None
    
    time_element = article.select_one('span.txt-time')
    published_time = ''
    if time_element:
        time_str = time_element.text.strip()
        try:
            current_year = datetime.now().year
            parsed_time = datetime.strptime(f"{current_year}-{time_str}", '%Y-%m-%d %H:%M')
            published_time = parsed_time.isoformat()
        except ValueError:
            return None
    
    img_element = article.select_one('img')
    img_url = img_element.get('src') if img_element else ''
    
    processed_links.add(clean_link)
    return {
        'title': title,
        'time': published_time,
        'img': img_url,
        'url': clean_link,
        'original_url': clean_link
    }

def scrape_page(url, page):
    print(f"Scraping URL: {url}/{page}")
    articles = []
    try:
        full_url = f"{url}/{page}" if page > 1 else url
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('ul.list01 li')
        print(f"Found {len(article_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_article, article, url) for article in article_elements]
            for future in as_completed(futures):
                article = future.result()
                if article:
                    articles.append(article)
        
        return articles
    except Exception as e:
        print(f"페이지 처리 실패 ({full_url}): {e}")
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
    
    for url in base_urls:
        page = 1
        while page <= 5:
            articles = scrape_page(url, page)
            all_articles.extend(articles)
            if not articles:
                break
            page += 1
            time.sleep(2)
    
    if all_articles:
        save_to_json(all_articles)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()
