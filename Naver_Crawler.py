# Naver_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import subprocess
from keyword import keywords, exclude_keywords  # keyword.py에서 키워드 가져오기

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'naver_News.json')

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
    'https://news.naver.com/section/100',  # 정치
    'https://news.naver.com/section/101',  # 경제
    'https://news.naver.com/section/103',  # 생활/문화
    'https://news.naver.com/section/104',  # 세계
    'https://news.naver.com/section/105',  # IT/과학
    'https://news.naver.com/breakingnews/section/104/231',  # 아시아/호주
    'https://news.naver.com/breakingnews/section/104/232',  # 유럽
    'https://news.naver.com/breakingnews/section/104/233',  # 중남미
    'https://news.naver.com/breakingnews/section/104/234',  # 중동/아프리카
    'https://news.naver.com/breakingnews/section/104/322',  # 북미
]

processed_links = set()
processed_titles = set()

def is_relevant_article(text_content):
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword for keyword in keywords if re.search(re.escape(keyword.lower()), text_content.lower())]
    exclude_match = any(keyword.lower() in words for keyword in exclude_keywords)
    if text_content in processed_titles or len(matching_keywords) < 2 or exclude_match:
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

def extract_article_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 시간 정보 추출
        time_element = soup.select_one('span[class*="ARTICLE_DATE_TIME"]')
        published_time = ''
        if time_element:
            published_time_data = time_element.get('data-date-time', '')
            if published_time_data:
                try:
                    dt = datetime.strptime(published_time_data, '%Y-%m-%d %H:%M:%S')
                    published_time = dt.isoformat()
                except ValueError as e:
                    print(f"Invalid time format: {published_time_data}, Error: {e}")
                    return '', '', ''
        
        # 요약 정보 추출
        summary_element = soup.select_one('.media_end_summary')
        summary = ''
        if summary_element:
            summary_html = summary_element.decode_contents()
            summary = summary_html.replace('<br>', '\n').replace('<br/>', '\n').strip()
        
        # 이미지 URL 추출
        img_element = soup.select_one('img#img1')
        img_url = img_element.get('data-src', '') if img_element else ''
        
        return published_time, img_url, summary
    except Exception as e:
        print(f"데이터 추출 실패 ({url}): {e}")
        return '', '', ''

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('div.section_latest_article ul li')
        print(f"Found {len(article_elements)} articles")
        
        for element in article_elements:
            title_element = element.select_one('div.sa_text a strong')
            if title_element:
                text_content = title_element.get_text(strip=True)
                href_link = title_element.parent['href']
                full_link = href_link if href_link.startswith('http') else f'https://news.naver.com{href_link}'
                
                if full_link not in processed_links and is_relevant_article(text_content):
                    published_time, img_url, summary = extract_article_details(full_link)
                    if published_time:
                        processed_links.add(full_link)
                        processed_titles.add(text_content)
                        articles.append({
                            'title': text_content,
                            'time': published_time,
                            'img': img_url,
                            'url': full_link,
                            'original_url': full_link,
                            'summary': summary
                        })
                        print(f"Article processed: {text_content} ({published_time})")
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
    return articles

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
        # 중복 URL 제거
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
        print("No new articles found")
        if not os.path.exists(result_filename):
            with open(result_filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"Empty {result_filename} created")

if __name__ == "__main__":
    main()
