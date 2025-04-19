# Gukje_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import subprocess
from News_keyword import keywords, exclude_keywords  # keyword.py에서 키워드 가져오기

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'Gukje_News.json')

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
    'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N1&view_type=sm',
    'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N3&view_type=sm',
    'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N6&view_type=sm'
]

processed_links = set()

def is_relevant_article(text_content):
    # 기사 제목에서 단어 추출 후 키워드 매칭 확인
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

def process_article(element, base_url):
    title_element = element.select_one('h4.titles a')
    if not title_element:
        return None

    href_link = 'https://www.gukjenews.com' + title_element['href']
    if href_link in processed_links:
        return None
    
    title = title_element.text.strip()
    time_element = element.select_one('span.byline em:nth-of-type(3)')
    time_str = time_element.text.strip() if time_element else ''
    try:
        published_time = datetime.strptime(time_str, '%Y.%m.%d %H:%M')
        formatted_time = published_time.isoformat()
    except ValueError:
        return None
    
    img_element = element.select_one('img')
    img_url = img_element.get('src') if img_element else ''
    if img_url and not img_url.startswith('http'):
        img_url = 'https://www.gukjenews.com' + img_url
    
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

def scrape_page(url, page):
    print(f"Scraping URL: {url}&page={page}")
    articles = []
    try:
        full_url = f"{url}&page={page}"
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('ul.type2 li')
        print(f"Found {len(relevant_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_article, element, url) for element in relevant_elements]
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
    
    for url in urls:
        page = 1
        while page <= 5:
            articles = scrape_page(url, page)
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
