# FNToday_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import sys
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from keyword import keywords, exclude_keywords  # keyword.py에서 키워드 가져오기

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'fntoday_News.json')

# 날짜 포맷팅 (모든 요일을 한국어로 변환)
today_dt = datetime.now()
day_map = {
    'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일', 'Thursday': '목요일',
    'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
}
eng_day = today_dt.strftime('%A')
kor_day = day_map.get(eng_day, eng_day)  # 영어 요일을 한국어로 변환
today = today_dt.strftime(f'%Y년 %m월 %d일 {kor_day}')
urls = [
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N107',
    'https://www.fntoday.co.kr/news/articleList.html?sc_section_code=S1N19',
    'https://www.fntoday.co.kr/news/articleList.html?sc_section_code=S1N128',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N306',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N310',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N299',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N300',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N301',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N302',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N303',
    'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N308',
    'https://www.fntoday.co.kr/news/articleList.html?sc_section_code=S1N103',
    'https://www.fntoday.co.kr/news/articleList.html?sc_section_code=S1N9',
    'https://www.fntoday.co.kr/news/articleList.html?sc_section_code=S1N50'
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
    title_element = element.find('div', class_='list-titles')
    if not title_element or not title_element.find('a'):
        return None
    
    link_element = title_element.find('a')
    href_link = link_element.get('href')
    if not href_link.startswith('http'):
        href_link = 'https://www.fntoday.co.kr' + href_link
    
    if href_link in processed_links:
        return None
    
    title = link_element.text.strip()
    time_element = element.find('div', class_='list-dated')
    if not time_element:
        return None
    
    time_str = time_element.text.strip().split('|')[-1].strip()
    try:
        published_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        formatted_time = published_time.isoformat()
    except ValueError:
        return None
    
    img_element = element.find('img')
    img_url = img_element.get('src') if img_element else ''
    if img_url and not img_url.startswith('http'):
        img_url = 'https://www.fntoday.co.kr' + img_url
    
    text_content = title
    if is_relevant_article(text_content):
        processed_links.add(href_link)
        return {
            'title': title,
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
        relevant_elements = soup.select('div.list-block')
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
        time.sleep(1)
    
    if all_articles:
        save_to_json(all_articles)
    else:
        print("No new articles found")
    
    # ✅ 마지막에 이 부분 추가!
    if not os.path.exists(result_filename):
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print(f"{result_filename} 파일이 없어서 새로 생성했어요.")

if __name__ == "__main__":
    main()
