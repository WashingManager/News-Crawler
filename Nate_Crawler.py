# Nate_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urlunparse
import subprocess

result_filename = 'nate_News.json'
today = datetime.now().strftime('%Y년 %m월 %d일 %A').replace('Friday', '금요일')

def get_keywords():
    try:
        result = subprocess.run(
            ['node', '-e', 'const k = require("./keyword.js"); console.log(JSON.stringify(k.getKeywords()));'],
            capture_output=True, text=True, check=True
        )
        keywords = json.loads(result.stdout)
        print(f"Loaded {len(keywords)} keywords")
        return keywords
    except Exception as e:
        print(f"키워드 로드 실패: {e}")
        return []

keywords = get_keywords()

base_urls = [
    'https://news.nate.com/recent?mid=n0102',
    'https://news.nate.com/recent?mid=n0103',
    'https://news.nate.com/recent?mid=n0104',
    'https://news.nate.com/recent?mid=n0105'
]

processed_links = set()

def get_date_list():
    today = datetime.now()
    return [today.strftime('%Y%m%d')]

def is_relevant_article(text_content):
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword.lower() for keyword in keywords if keyword.lower() in words]
    return len(matching_keywords) >= 2

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        print(f"{result_filename} 파일이 없음. 새로 생성 예정.")
        return set()

def process_article(article, base_url):
    link_element = article.select_one('a.lt1')
    if not link_element:
        return None
    
    href_link = link_element['href']
    full_link = urljoin(base_url, href_link)
    parsed_url = urlparse(full_link)
    clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
    
    if clean_url in processed_links:
        return None
    
    title_element = article.select_one('h2.tit')
    if not title_element:
        return None
    
    text_content = title_element.get_text(strip=True)
    time_element = article.select_one('span.medium em')
    published_time = time_element.get_text(strip=True) if time_element else ''
    try:
        parsed_time = datetime.strptime(published_time, '%Y.%m.%d %H:%M')
        formatted_time = parsed_time.isoformat()
    except ValueError:
        return None
    
    img_element = article.select_one('img')
    img_url = img_element.get('src') if img_element else ''
    
    if is_relevant_article(text_content):
        processed_links.add(clean_url)
        return {
            'title': text_content,
            'time': formatted_time,
            'img': img_url,
            'url': clean_url,
            'original_url': clean_url
        }
    return None

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('div.mlt01')
        print(f"Found {len(article_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_article, article, url) for article in article_elements]
            for future in as_completed(futures):
                article = future.result()
                if article:
                    articles.append(article)
        
        return articles
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
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
        today_data['articles'].extend(new_articles)
    else:
        existing_data.append({'date': today, 'articles': new_articles})
    
    try:
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print(f"{len(new_articles)}개의 기사를 {result_filename}에 저장 완료")
    except Exception as e:
        print(f"JSON 저장 실패: {e}")

def main():
    global processed_links
    processed_links = get_existing_links()
    all_articles = []
    
    for base_url in base_urls:
        for date in get_date_list():
            page = 1
            while page <= 5:
                url = f'{base_url}&type=c&date={date}&page={page}'
                articles = scrape_page(url)
                all_articles.extend(articles)
                if not articles:
                    break
                page += 1
                time.sleep(1)
    
    save_to_json(all_articles)
    if not os.path.exists(result_filename):
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print(f"새로운 기사 없음. 빈 {result_filename} 파일 생성")

if __name__ == "__main__":
    main()
