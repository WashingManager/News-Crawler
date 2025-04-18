# Naver_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys
import os
import re

result_filename = 'naver_News.json'
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

urls = [
    'https://news.naver.com/section/100',
    'https://news.naver.com/section/101',
    'https://news.naver.com/section/103',
    'https://news.naver.com/section/104',
    'https://news.naver.com/section/105',
    'https://news.naver.com/breakingnews/section/104/231',
    'https://news.naver.com/breakingnews/section/104/232',
    'https://news.naver.com/breakingnews/section/104/233',
    'https://news.naver.com/breakingnews/section/104/234',
    'https://news.naver.com/breakingnews/section/104/322'
]

processed_links = set()

def is_relevant_article(text_content):
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword for keyword in keywords if re.search(re.escape(keyword.lower()), text_content.lower())]
    exclude_match = any(keyword.lower() in words for keyword in exclude_keywords)
    return len(matching_keywords) >= 1 and not exclude_match

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        return set()

def extract_article_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        time_element = soup.select_one('span[class*="ARTICLE_DATE_TIME"]')
        published_time = ''
        if time_element:
            published_time_data = time_element.get('data-date-time', '')
            if published_time_data:
                dt = datetime.strptime(published_time_data, '%Y-%m-%d %H:%M:%S')
                published_time = dt.isoformat()
        
        img_element = soup.select_one('img#img1')
        img_url = img_element.get('data-src') if img_element else ''
        return published_time, img_url
    except Exception as e:
        print(f"데이터 추출 실패 ({url}): {e}")
        return '', ''

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('div.section_latest_article ul li')
        
        for element in article_elements:
            title_element = element.select_one('div.sa_text a strong')
            if title_element:
                text_content = title_element.get_text(strip=True)
                href_link = title_element.parent['href']
                full_link = href_link if href_link.startswith('http') else f'https://news.naver.com{href_link}'
                
                if full_link not in processed_links and is_relevant_article(text_content):
                    published_time, img_url = extract_article_details(full_link)
                    if published_time:
                        processed_links.add(full_link)
                        articles.append({
                            'title': text_content,
                            'time': published_time,
                            'img': img_url,
                            'url': full_link,
                            'original_url': full_link
                        })
                        print(f"추출된 기사: {text_content} ({published_time})")
                        break  # 한 페이지당 한 기사
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
    return articles

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
