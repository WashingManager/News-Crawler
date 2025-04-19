# YNA_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib.parse
from keyword import keywords, exclude_keywords  # keyword.py에서 키워드 가져오기

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'yna_News.json')

# 날짜 포맷팅 (모든 요일을 한국어로 변환)
today_dt = datetime.now()
day_map = {
    'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일', 'Thursday': '목요일',
    'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
}
eng_day = today_dt.strftime('%A')
kor_day = day_map.get(eng_day, eng_day)  # 영어 요일을 한국어로 변환
today = today_dt.strftime(f'%Y년 %m월 %d일 {kor_day}')


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
processed_titles = set()

def is_relevant_article(full_text):
    if not keywords:
        return True
    words = set(re.findall(r'\b\w+\b', full_text.lower()))
    matching_keywords = [keyword for keyword in keywords if re.search(re.escape(keyword.lower()), full_text.lower())]
    exclude_match = any(keyword.lower() in words for keyword in exclude_keywords)
    if len(matching_keywords) < 2 or exclude_match:
        return False
    return True

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        print(f"{result_filename} 파일이 없음. 새로 생성 예정.")
        return set()

def process_article(article, base_url):
    title_element = article.select_one('span.title01')
    title = title_element.text.strip() if title_element else ''
    if not title or title in processed_titles:
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
            if '-' in time_str:  # 예: 04-18 20:54
                parsed_time = datetime.strptime(f"{current_year}-{time_str}", '%Y-%m-%d %H:%M')
            else:  # 예: 2025-04-18 20:54
                parsed_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            published_time = parsed_time.isoformat()
        except ValueError as e:
            print(f"Invalid time format: {time_str}, Error: {e}")
            return None
    
    img_element = article.select_one('img')
    img_url = img_element.get('src', '') if img_element else ''
    
    processed_links.add(clean_link)
    processed_titles.add(title)
    print(f"Article processed: {title} ({published_time})")
    return {
        'title': title,
        'time': published_time,
        'img': img_url,
        'url': clean_link,
        'original_url': clean_link,
        'summary': lead
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
    existing_data = []
    if os.path.exists(result_filename):
        try:
            with open(result_filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            print(f"{result_filename} 파일이 손상됨. 새 파일로 초기화.")
    
    today_data = next((d for d in existing_data if d['date'] == today), None)
    if today_data:
        existing_urls = {article['url'] for article in today_data['articles']}
        new_articles = [article for article in new_articles if article['url'] not in existing_urls]
        today_data['articles'].extend(new_articles)
    else:
        existing_data.append({'date': today, 'articles': new_articles})
    
    try:
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(new_articles)} articles to {result_filename}")
    except Exception as e:
        print(f"JSON 저장 실패: {e}")

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
        if not os.path.exists(result_filename):
            with open(result_filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"Empty {result_filename} created")

if __name__ == "__main__":
    main()
