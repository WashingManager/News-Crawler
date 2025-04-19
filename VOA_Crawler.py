import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from News_keyword import keywords, exclude_keywords  # keyword.py에서 키워드 가져오기

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'voa_News.json')

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
    'https://www.voakorea.com/z/2767',  # 정치안보
    'https://www.voakorea.com/z/2768',  # 경제지원
    'https://www.voakorea.com/z/2769',  # 사회인권
    'https://www.voakorea.com/z/2824',  # 중동
    'https://www.voakorea.com/z/6936',  # 우크라이나
    'https://www.voakorea.com/z/2698'   # 세계
]

processed_links = set()

def is_relevant_article(text_content):
    if not keywords:
        return True
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword for keyword in keywords if re.search(re.escape(keyword.lower()), text_content.lower())]
    print(f"매칭된 키워드: {matching_keywords}")
    return len(matching_keywords) >= 2

def get_existing_links():
    try:
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        print(f"{result_filename} 파일이 없음. 새로 생성 예정.")
        return set()

def extract_article_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        summary_element = soup.select_one('p.perex, p[class*="perex"]')
        summary = summary_element.text.strip() if summary_element else ''
        print(f"URL: {url}, 요약: {summary}")
        return summary
    except Exception as e:
        print(f"데이터 추출 실패 ({url}): {e}")
        return ''

def process_article(element):
    href_link = element.find('a')['href']
    if not href_link.startswith('http'):
        href_link = 'https://www.voakorea.com' + href_link
    
    if href_link in processed_links:
        print(f"이미 처리된 링크: {href_link}")
        return None
    
    title_element = element.find('h4', class_='media-block__title')
    text_content = title_element.text.strip() if title_element else ''
    
    summary = extract_article_details(href_link)
    full_text = f"{text_content} {summary}"
    
    if not is_relevant_article(full_text):
        print(f"관련 없는 기사: {text_content}")
        return None
    
    time_element = element.find('span', class_='date')
    published_time = time_element.text.strip() if time_element else ''
    try:
        # 한국어 날짜 형식 처리 (예: 2025년 3월 16일)
        parsed_time = datetime.strptime(published_time, '%Y년 %m월 %d일')
        # 시간 정보가 없으므로 00:00으로 설정
        formatted_time = parsed_time.replace(hour=0, minute=0, second=0).isoformat()
    except ValueError as e:
        print(f"잘못된 시간 형식: {published_time}, 에러: {e}")
        return None
    
    img_element = element.find('img')
    img_url = img_element.get('src') if img_element else ''
    if img_url and not img_url.startswith('http'):
        img_url = 'https://www.voakorea.com' + img_url
    
    processed_links.add(href_link)
    print(f"처리된 기사: {text_content} ({formatted_time})")
    return {
        'title': text_content,
        'time': formatted_time,
        'img': img_url,
        'url': href_link,
        'original_url': href_link,
        'summary': summary
    }

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('div.media-block')
        print(f"선택된 요소 수: {len(relevant_elements)}")
        
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
    
    for url in urls:
        articles = scrape_page(url)
        all_articles.extend(articles)
    
    if all_articles:
        save_to_json(all_articles)
    else:
        print("새로운 기사를 찾지 못함")
        if not os.path.exists(result_filename):
            with open(result_filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"빈 {result_filename} 파일 생성")

if __name__ == "__main__":
    main()
