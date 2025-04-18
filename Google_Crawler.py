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


result_filename = 'google_News.json'
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
    'https://news.google.com/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFp4WkRNU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/home?hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/search?q=%ED%99%94%EC%82%B0&hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/search?q=%EB%B0%A9%EC%82%AC%EB%8A%A5&hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/search?q=%EC%A0%84%EC%97%BC%EB%B3%91&hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/search?q=%EC%84%B8%EA%B3%84%EC%9E%AC%EB%82%9C&hl=ko&gl=KR&ceid=KR%3Ako',
    'https://news.google.com/search?q=%EC%A7%80%EC%A7%84&hl=ko&gl=KR&ceid=KR%3Ako'
]

processed_links = set()
ua = UserAgent()

def is_similar(title1, title2, threshold=35):
    return fuzz.ratio(title1, title2) >= threshold

def is_relevant_article(text_content):
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    keyword_match = sum(keyword.lower() in words for keyword in keywords) >= 2
    exclude_match = any(keyword.lower() in words for keyword in exclude_keywords)
    return keyword_match and not exclude_match

def is_within_last_two_days(published_time):
    if not published_time:
        return False
    article_date = datetime.strptime(published_time, '%Y-%m-%d %H:%M')
    two_days_ago = datetime.now() - timedelta(days=2)
    return article_date >= two_days_ago

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        return set()

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('a.gPFEn, a.JtKRv')
        
        unique_titles = []
        for element in relevant_elements:
            href_link = element.get('href')
            title = element.get_text(strip=True)
            
            if not any(is_similar(title, t) for t in unique_titles):
                if is_relevant_article(title):
                    time_element = element.find_next('time')
                    if time_element and time_element.has_attr('datetime'):
                        time_str = time_element['datetime']
                        published_time = datetime.fromisoformat(time_str[:-1]) + timedelta(hours=9)
                        formatted_time = published_time.strftime('%Y-%m-%dT%H:%M:%S+09:00')
                        
                        if is_within_last_two_days(formatted_time[:16]):
                            full_link = f'https://news.google.com{href_link}'
                            full_link = full_link.replace('https://news.google.com./', 'https://news.google.com/')
                            if full_link not in processed_links:
                                img_element = element.find_previous('img')
                                img_url = img_element.get('src') if img_element else ''
                                unique_titles.append(title)
                                processed_links.add(full_link)
                                articles.append({
                                    'title': title,
                                    'time': formatted_time,
                                    'img': img_url,
                                    'url': full_link,
                                    'original_url': full_link
                                })
                                print(f"추출된 기사: {title} ({formatted_time})")
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
        time.sleep(1)
    
    if all_articles:
        save_to_json(all_articles)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()
