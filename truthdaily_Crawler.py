import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
import time

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'truthdaily_News.json')

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

# TruthDaily 섹션 URL들
urls = [
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N1',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N2',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N3',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N4',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N5',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N6',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N7',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N8',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N9',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N10',
]

processed_links = set()
processed_titles = set()

def is_within_two_days(article_time_str):
    """기사 시간이 현재로부터 2일 이내인지 확인"""
    try:
        # "07-30 17:43" 형식을 파싱
        current_year = datetime.now().year
        article_datetime = datetime.strptime(f"{current_year}-{article_time_str}", "%Y-%m-%d %H:%M")
        
        # 현재 시간으로부터 2일 전 계산
        two_days_ago = datetime.now() - timedelta(days=2)
        
        return article_datetime >= two_days_ago
    except ValueError as e:
        print(f"시간 파싱 오류: {article_time_str}, {e}")
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
        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {article['url'] for day in data for article in day['articles']}
    except FileNotFoundError:
        print(f"{result_filename} 파일이 없음. 새로 생성 예정.")
        return set()

def extract_article_details(url):
    """개별 기사 페이지에서 상세 정보 추출"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 이미지 URL 추출
        img_element = soup.select_one('.article-body img')
        img_url = img_element.get('src', '') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = f"https://www.truthdaily.co.kr{img_url}"
        
        # 요약/본문 일부 추출
        content_element = soup.select_one('.article-body')
        summary = ''
        if content_element:
            # 첫 번째 문단이나 요약 부분 추출
            paragraphs = content_element.find_all('p')
            if paragraphs:
                summary = paragraphs[0].get_text(strip=True)[:200] + "..." if len(paragraphs[0].get_text(strip=True)) > 200 else paragraphs[0].get_text(strip=True)
        
        return img_url, summary
    except Exception as e:
        print(f"기사 상세정보 추출 실패 ({url}): {e}")
        return '', ''

def load_more_articles(session, url, page_num):
    """더보기 버튼을 통해 추가 기사 로드"""
    try:
        # 더보기 요청을 위한 AJAX URL 구성
        base_url = url.split('?')[0]
        params = url.split('?')[1] if '?' in url else ''
        ajax_url = f"{base_url}?{params}&page={page_num}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': url
        }
        
        response = session.get(ajax_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"더보기 로드 실패 (페이지 {page_num}): {e}")
        return None

def scrape_page(url):
    """페이지별 기사 수집"""
    print(f"Scraping URL: {url}")
    articles = []
    session = requests.Session()
    page_num = 1
    
    try:
        # 첫 페이지 로드
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        while True:
            # 기사 요소들 찾기
            sections_div = soup.select_one('#sections.altlist')
            if not sections_div:
                print("sections div를 찾을 수 없습니다.")
                break
                
            article_elements = sections_div.select('li')
            print(f"페이지 {page_num}에서 {len(article_elements)}개 기사 발견")
            
            found_old_articles = False
            page_articles = []
            
            for element in article_elements:
                # 제목과 링크 추출
                title_element = element.select_one('h2.altlist-subject a')
                if not title_element:
                    continue
                    
                title = title_element.get_text(strip=True)
                href = title_element.get('href', '')
                full_link = href if href.startswith('http') else f'https://www.truthdaily.co.kr{href}'
                
                # 시간 정보 추출
                time_element = element.select_one('.altlist-info .altlist-info-item:last-child')
                if not time_element:
                    continue
                    
                article_time = time_element.get_text(strip=True)
                
                # 2일 이내 기사인지 확인
                if not is_within_two_days(article_time):
                    print(f"2일 이전 기사 발견: {title} ({article_time})")
                    found_old_articles = True
                    break
                
                # 중복 확인 및 관련성 검사
                if full_link not in processed_links and is_relevant_article(title):
                    # 기사 상세정보 추출
                    img_url, summary = extract_article_details(full_link)
                    
                    # 시간을 ISO 형식으로 변환
                    try:
                        current_year = datetime.now().year
                        dt = datetime.strptime(f"{current_year}-{article_time}", "%Y-%m-%d %H:%M")
                        published_time = dt.isoformat()
                    except ValueError:
                        published_time = article_time
                    
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
                    
                    page_articles.append(article_data)
                    print(f"기사 처리 완료: {title} ({article_time})")
            
            articles.extend(page_articles)
            
            # 2일 이전 기사를 발견했거나 더 이상 기사가 없으면 중단
            if found_old_articles or len(page_articles) == 0:
                print(f"수집 중단: {'2일 이전 기사 발견' if found_old_articles else '더 이상 기사 없음'}")
                break
            
            # 다음 페이지 로드
            page_num += 1
            print(f"다음 페이지 {page_num} 로드 중...")
            soup = load_more_articles(session, url, page_num)
            
            if not soup:
                print("더 이상 페이지를 로드할 수 없습니다.")
                break
            
            # 요청 간격 조절
            time.sleep(1)
            
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
    
    return articles

def save_to_json(new_articles):
    """JSON 파일에 저장"""
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
