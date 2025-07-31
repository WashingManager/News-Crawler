import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
import time

# JSON 저장 폴더 설정
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'boannews_News.json')

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

# 보안뉴스 기본 URL
base_url = 'https://www.boannews.com/media/t_list.asp'

processed_links = set()
processed_titles = set()

def parse_article_datetime(datetime_str):
    """기사 날짜시간 파싱 ('2025년 07월 31일 13:44' 형식)"""
    try:
        # "2025년 07월 31일 13:44" 형식을 파싱
        dt = datetime.strptime(datetime_str, "%Y년 %m월 %d일 %H:%M")
        return dt
    except ValueError as e:
        print(f"날짜시간 파싱 오류: {datetime_str}, {e}")
        return None

def is_within_two_days(datetime_obj):
    """기사 날짜가 현재로부터 2일 이내인지 확인"""
    if not datetime_obj:
        return False
    
    # 현재 시간으로부터 2일 전 계산
    two_days_ago = datetime.now() - timedelta(days=2)
    
    return datetime_obj >= two_days_ago

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
        img_element = soup.select_one('.news_content img, .view_content img, #news_content img')
        img_url = img_element.get('src', '') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = f"https://www.boannews.com{img_url}" if img_url.startswith('/') else f"https://www.boannews.com/{img_url}"
        
        # 요약/본문 일부 추출
        content_element = soup.select_one('.news_content, .view_content, #news_content')
        summary = ''
        if content_element:
            # 첫 번째 문단이나 요약 부분 추출
            text_content = content_element.get_text(strip=True)
            summary = text_content[:200] + "..." if len(text_content) > 200 else text_content
        
        return img_url, summary
    except Exception as e:
        print(f"기사 상세정보 추출 실패 ({url}): {e}")
        return '', ''

def extract_article_link(news_txt_element):
    """news_txt 요소에서 기사 링크 추출"""
    try:
        # news_txt가 a 태그인 경우
        if news_txt_element.name == 'a':
            return news_txt_element.get('href', '')
        
        # news_txt 내부에 a 태그가 있는 경우
        link_element = news_txt_element.find('a')
        if link_element:
            return link_element.get('href', '')
        
        # 부모 요소에서 링크 찾기
        parent = news_txt_element.parent
        while parent:
            link_element = parent.find('a')
            if link_element:
                return link_element.get('href', '')
            parent = parent.parent
            
        return ''
    except Exception as e:
        print(f"링크 추출 실패: {e}")
        return ''

def scrape_page(page_num=1):
    """페이지별 기사 수집"""
    print(f"Scraping page: {page_num}")
    articles = []
    
    try:
        # 페이지 URL 구성
        if page_num > 1:
            page_url = f"{base_url}?Page={page_num}"
        else:
            page_url = base_url
            
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # media div 찾기
        media_div = soup.select_one('#media')
        if not media_div:
            print("media div를 찾을 수 없습니다.")
            return articles
            
        # 기사 제목 요소들 찾기
        news_txt_elements = media_div.select('span.news_txt')
        print(f"페이지 {page_num}에서 {len(news_txt_elements)}개 기사 발견")
        
        found_old_articles = False
        
        for news_txt_element in news_txt_elements:
            title = news_txt_element.get_text(strip=True)
            if not title:
                continue
            
            # 기사 링크 추출
            article_link = extract_article_link(news_txt_element)
            if not article_link:
                print(f"링크를 찾을 수 없음: {title}")
                continue
                
            # 절대 URL로 변환
            if article_link.startswith('/'):
                full_link = f"https://www.boannews.com{article_link}"
            elif not article_link.startswith('http'):
                full_link = f"https://www.boannews.com/media/{article_link}"
            else:
                full_link = article_link
            
            # 같은 tr 또는 부모 요소에서 작성자와 날짜 정보 찾기
            writer_element = None
            current_element = news_txt_element.parent
            
            # 부모 요소들을 순회하며 news_writer 찾기
            for _ in range(5):  # 최대 5단계까지 올라가며 찾기
                if current_element:
                    writer_element = current_element.find('span', class_='news_writer')
                    if writer_element:
                        break
                    current_element = current_element.parent
                else:
                    break
            
            if not writer_element:
                print(f"작성자 정보를 찾을 수 없음: {title}")
                continue
            
            writer_text = writer_element.get_text(strip=True)
            
            # "성기노 기자 | 2025년 07월 31일 13:44" 형식에서 날짜시간 추출
            if '|' in writer_text:
                parts = writer_text.split('|')
                if len(parts) >= 2:
                    datetime_str = parts[1].strip()
                else:
                    continue
            else:
                continue
            
            # 날짜시간 파싱
            article_datetime = parse_article_datetime(datetime_str)
            if not article_datetime:
                continue
            
            # 2일 이내 기사인지 확인
            if not is_within_two_days(article_datetime):
                print(f"2일 이전 기사 발견: {title} ({datetime_str})")
                found_old_articles = True
                break
            
            # 중복 확인 및 관련성 검사
            if full_link not in processed_links and is_relevant_article(title):
                # 기사 상세정보 추출
                img_url, summary = extract_article_details(full_link)
                
                processed_links.add(full_link)
                processed_titles.add(title)
                
                article_data = {
                    'title': title,
                    'time': article_datetime.isoformat(),
                    'img': img_url,
                    'url': full_link,
                    'original_url': full_link,
                    'summary': summary
                }
                
                articles.append(article_data)
                print(f"기사 처리 완료: {title} ({datetime_str})")
        
        # 2일 이전 기사를 발견하지 않았고, 기사가 있으면 다음 페이지도 확인
        if not found_old_articles and len(articles) > 0:
            time.sleep(2)  # 요청 간격 조절
            next_page_articles = scrape_page(page_num + 1)
            articles.extend(next_page_articles)
            
    except Exception as e:
        print(f"페이지 처리 실패 (page {page_num}): {e}")
    
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
    
    # 첫 번째 페이지부터 시작해서 2일치 기사 수집
    articles = scrape_page(1)
    
    if articles:
        save_to_json(articles)
        print(f"수집 완료: 총 {len(articles)}개의 새로운 기사")
    else:
        print("새로운 기사를 찾지 못했습니다.")
        if not os.path.exists(result_filename):
            with open(result_filename, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            print(f"빈 {result_filename} 파일을 생성했습니다.")

if __name__ == "__main__":
    main()
