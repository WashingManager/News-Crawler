import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
import time

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'hanmiilbo_News.json')

# 디렉토리 생성
os.makedirs(NEWS_JSON_DIR, exist_ok=True)

# 날짜 포맷팅 (모든 요일을 한국어로 변환)
today_dt = datetime.now()
day_map = {
    'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일', 'Thursday': '목요일',
    'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
}
eng_day = today_dt.strftime('%A')
kor_day = day_map.get(eng_day, eng_day)
today = today_dt.strftime(f'%Y년 %m월 %d일 {kor_day}')


def load_keywords():
    try:
        with open('News_keyword.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        keywords = [item for cat in data['keywords'] for item in cat['items']]
        exclude_keywords = [item for cat in data['exclude_keywords'] for item in cat['items']]
        return keywords, exclude_keywords
    except FileNotFoundError:
        print("News_keyword.json 파일이 없습니다. 모든 기사를 수집합니다.")
        return [], []

keywords, exclude_keywords = load_keywords()

# 한미일보 섹션 URL들
urls = [
    'https://hanmiilbo.kr/news/list.php?mcode=m247tk9',
    'https://hanmiilbo.kr/news/list.php?mcode=m37525y',
    'https://hanmiilbo.kr/news/list.php?mcode=m38dz78',
    'https://hanmiilbo.kr/news/list.php?mcode=m39uqyj',
    'https://hanmiilbo.kr/news/list.php?mcode=m40weh7',
    'https://hanmiilbo.kr/news/list.php?mcode=m64aank',
]

processed_links = set()
processed_titles = set()

def is_within_two_days(article_date_str):
    """기사 날짜가 현재로부터 2일 이내인지 확인"""
    try:
        # "2025-07-31" 형식을 파싱
        article_date = datetime.strptime(article_date_str, "%Y-%m-%d")
        
        # 현재 날짜로부터 2일 전 계산
        two_days_ago = datetime.now() - timedelta(days=2)
        two_days_ago = two_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
        
        return article_date >= two_days_ago
    except ValueError as e:
        print(f"날짜 파싱 오류: {article_date_str}, {e}")
        return False

def is_relevant_article(text_content):
    """키워드 기반 관련성 검사"""
    if not keywords:  # 키워드가 없으면 모든 기사 수집
        return True
        
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword for keyword in keywords if re.search(re.escape(keyword.lower()), text_content.lower())]
    exclude_match = any(keyword.lower() in words for keyword in exclude_keywords)
    
    if text_content in processed_titles or len(matching_keywords) < 2 or exclude_match:
        return False
    return True

def get_existing_links():
    """기존 저장된 링크들을 가져오기"""
    try:
        if not os.path.exists(result_filename) or os.stat(result_filename).st_size == 0:
            print(f"{result_filename} 파일이 없거나 비어 있음. 새로 생성 예정.")
            return set()

        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}

    except (FileNotFoundError, json.JSONDecodeError):
        print(f"{result_filename} 파일이 없거나 손상됨. 새로 생성 예정.")
        return set()

def extract_article_details(url):
    """개별 기사 페이지에서 상세 정보 추출"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 이미지 URL 추출
        img_element = soup.select_one('.article_body img, .view_body img, .content img')
        img_url = img_element.get('src', '') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = f"https://hanmiilbo.kr{img_url}" if img_url.startswith('/') else f"https://hanmiilbo.kr/{img_url}"
        
        # 요약/본문 일부 추출
        content_element = soup.select_one('.article_body, .view_body, .content')
        summary = ''
        if content_element:
            # 첫 번째 문단이나 요약 부분 추출
            text_content = content_element.get_text(strip=True)
            summary = text_content[:200] + "..." if len(text_content) > 200 else text_content
        
        return img_url, summary
    except Exception as e:
        print(f"기사 상세정보 추출 실패 ({url}): {e}")
        return '', ''

def scrape_page(url, page_num=1):
    """페이지별 기사 수집 (페이지네이션 지원)"""
    print(f"Scraping URL: {url} (page {page_num})")
    articles = []
    
    try:
        # 페이지 번호가 있는 경우 URL에 추가
        if page_num > 1:
            separator = '&' if '?' in url else '?'
            page_url = f"{url}{separator}page={page_num}"
        else:
            page_url = url
            
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 기사 목록 찾기
        basic_list = soup.select_one('div.basicList')
        if not basic_list:
            print("basicList div를 찾을 수 없습니다.")
            return articles
            
        article_elements = basic_list.select('dl')
        print(f"페이지 {page_num}에서 {len(article_elements)}개 기사 발견")
        
        found_old_articles = False
        
        for element in article_elements:
            # 제목과 링크 추출
            title_element = element.select_one('dt.title a')
            if not title_element:
                continue
                
            title = title_element.get_text(strip=True)
            href = title_element.get('href', '')
            
            # 상대 경로를 절대 경로로 변환
            if href.startswith('../'):
                full_link = f"https://hanmiilbo.kr/{href[3:]}"
            elif href.startswith('/'):
                full_link = f"https://hanmiilbo.kr{href}"
            elif not href.startswith('http'):
                full_link = f"https://hanmiilbo.kr/{href}"
            else:
                full_link = href
            
            # 날짜 정보 추출
            date_element = element.select_one('dd.registDate')
            if not date_element:
                continue
                
            article_date = date_element.get_text(strip=True)
            
            # 2일 이내 기사인지 확인
            if not is_within_two_days(article_date):
                print(f"2일 이전 기사 발견: {title} ({article_date})")
                found_old_articles = True
                break
            
            # 중복 확인 및 관련성 검사
            if full_link not in processed_links and is_relevant_article(title):
                # 기사 상세정보 추출
                img_url, summary = extract_article_details(full_link)
                
                # 날짜를 ISO 형식으로 변환
                try:
                    dt = datetime.strptime(article_date, "%Y-%m-%d")
                    published_time = dt.isoformat()
                except ValueError:
                    published_time = article_date
                
                processed_links.add(full_link)
                processed_titles.add(title)
                
                article_data = {
                    'title': title,
                    'time': published_time,
                    'img': img_url,
                    'url': full_link,
                    'original_url': full_link,
                    'summary': summary
                }
                
                articles.append(article_data)
                print(f"기사 처리 완료: {title} ({article_date})")
        
        # 2일 이전 기사를 발견하지 않았고, 기사가 있으면 다음 페이지도 확인
        if not found_old_articles and len(articles) > 0:
            time.sleep(1)  # 요청 간격 조절
            next_page_articles = scrape_page(url, page_num + 1)
            articles.extend(next_page_articles)
            
    except Exception as e:
        print(f"페이지 처리 실패 ({url}, page {page_num}): {e}")
    
    return articles

def save_to_json(new_articles):
    """JSON 파일에 저장"""
    existing_data = []
    if os.path.exists(result_filename):
        if os.stat(result_filename).st_size == 0:
            print(f"{result_filename} 파일이 비어 있음. 새 파일로 초기화.")
        else:
            try:
                with open(result_filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                print(f"{result_filename} 파일이 손상됨. 새 파일로 초기화.")
                existing_data = []

    # 오늘 날짜 데이터 찾기
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
        print(f"총 {len(new_articles)}개 기사를 {result_filename}에 저장했습니다.")
    except Exception as e:
        print(f"JSON 저장 실패: {e}")


def main():
    global processed_links
    processed_links = get_existing_links()
    all_articles = []
    
    for url in urls:
        articles = scrape_page(url)
        all_articles.extend(articles)
        time.sleep(2)  # 섹션 간 요청 간격 조절
    
    if all_articles:
        save_to_json(all_articles)
        print(f"수집 완료: 총 {len(all_articles)}개의 새로운 기사")
    else:
        print("새로운 기사를 찾지 못했습니다.")
        if not os.path.exists(result_filename):
            with open(result_filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"빈 {result_filename} 파일을 생성했습니다.")

if __name__ == "__main__":
    main()
