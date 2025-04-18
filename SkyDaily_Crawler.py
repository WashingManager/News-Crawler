import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

result_filename = 'skyDaily_News.json'
today = datetime.now().strftime('%Y년 %m월 %d일 %A').replace('Friday', '금요일')

def get_keywords():
    try:
        result = subprocess.run(
            ['node', '-e', 'const k = require("./keyword.js"); console.log(JSON.stringify(k.getKeywords()));'],
            capture_output=True, text=True, check=True
        )
        keywords = json.loads(result.stdout)
        print(f"Loaded {len(keywords)} keywords: {keywords}")
        return keywords
    except Exception as e:
        print(f"키워드 로드 실패: {e}")
        return []

keywords = get_keywords()

urls = [
    'https://www.skyedaily.com/news/articlelist.html?mode=list',  # 최신기사
    'https://www.skyedaily.com/news/news_list21.html',  # 오피니언
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=4',  # 정치
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=5',  # 사회
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=40',  # 경제
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=2',  # 산업
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=51',  # 생활경제
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=30',  # 금융
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=6',  # 문화
]

processed_links = set()

def is_relevant_article(text_content):
    if not keywords:
        return True
    words = set(re.findall(r'\b\w+\b', text_content.lower()))
    matching_keywords = [keyword for keyword in keywords if re.search(re.escape(keyword.lower()), text_content.lower())]
    #print(f"매칭된 키워드: {matching_keywords}")
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
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')
        summary_element = soup.select_one('div.article_txt')
        summary = summary_element.text.strip() if summary_element else ''
        #print(f"URL: {url}, 요약: {summary[:50]}...")
        return summary
    except Exception as e:
        print(f"데이터 추출 실패 ({url}): {e}")
        return ''

def process_article(element):
    href_link = element.get('href')
    if not href_link.startswith('http'):
        href_link = 'https://www.skyedaily.com' + href_link
    
    if href_link in processed_links:
        print(f"이미 처리된 링크: {href_link}")
        return None
    
    title_element = element.find('font', class_='sctionarticletitle')
    time_element = element.find_next('font', class_='picarticletxt')
    
    if not (title_element and time_element):
        print(f"제목 또는 시간 요소 누락: {href_link}")
        return None
    
    title = title_element.text.strip()
    time_str = time_element.text.strip()
    
    try:
        # 기본 시간 형식: 2025.03.16 12:34
        parsed_time = datetime.strptime(time_str, '%Y.%m.%d %H:%M')
        formatted_time = parsed_time.isoformat()
    except ValueError:
        try:
            # 대체 형식: 2025.03.16
            parsed_time = datetime.strptime(time_str, '%Y.%m.%d')
            formatted_time = parsed_time.replace(hour=0, minute=0, second=0).isoformat()
        except ValueError:
            try:
                # 한국어 형식: 2025년 3월 16일
                parsed_time = datetime.strptime(time_str, '%Y년 %m월 %d일')
                formatted_time = parsed_time.replace(hour=0, minute=0, second=0).isoformat()
            except ValueError as e:
                print(f"잘못된 시간 형식: {time_str}, 에러: {e}")
                return None
    
    summary = extract_article_details(href_link)
    text_content = f"{title} {summary}"
    
    if not is_relevant_article(text_content):
        #print(f"관련 없는 기사: {title}")
        return None
    
    img_element = element.find('img')
    img_url = img_element.get('src') if img_element else ''
    if img_url and not img_url.startswith('http'):
        img_url = 'https://www.skyedaily.com' + img_url
    
    processed_links.add(href_link)
    print(f"처리된 기사: {title} ({formatted_time})")
    return {
        'title': title,
        'time': formatted_time,
        'img': img_url,
        'url': href_link,
        'original_url': href_link,
        'summary': summary
    }

def scrape_page(url):
    #print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('div.picarticle a')
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
        time.sleep(1)
    
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
