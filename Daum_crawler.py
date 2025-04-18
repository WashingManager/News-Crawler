# scraper.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib.parse
import json
import subprocess

json_filename = 'daum_News.json'

# keyword.js에서 키워드 가져오기
def get_keywords():
    try:
        # Node.js로 keyword.js 실행
        result = subprocess.run(
            ['node', '-e', 'const k = require("./keyword.js"); console.log(JSON.stringify(k.getKeywords()));'],
            capture_output=True, text=True, check=True
        )
        keywords = json.loads(result.stdout)
        print(f"Loaded {len(keywords)} keywords")
        return keywords
    except Exception as e:
        print(f"키워드 로드 실패: {e}")
        return []

keywords = get_keywords()
exclude_keywords = []  # 제외 키워드 (필요 시 추가)

urls = [
    'https://news.daum.net/global',
    'https://news.daum.net/china',
    'https://news.daum.net/northamerica',
    'https://news.daum.net/japan',
    'https://news.daum.net/asia',
    'https://news.daum.net/arab',
    'https://news.daum.net/europe',
    'https://news.daum.net/southamerica',
    'https://news.daum.net/africa',
    'https://news.daum.net/topic',
    'https://news.daum.net/politics',
    'https://news.daum.net/society',
    'https://news.daum.net/economy',
    'https://news.daum.net/climate',
    'https://issue.daum.net/focus/241203'
]

result_set = set()
processed_links = set()

def extract_article_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        summary_element = soup.select_one('strong.summary_view')
        summary = summary_element.text.strip() if summary_element else ''
        
        img_element = soup.select_one('meta[property="og:image"]')
        img_url = img_element['content'] if img_element else ''
        if not img_url:
            img_element = soup.select_one('img[alt="thumbnail"]')
            img_url = img_element['src'] if img_element else ''
        
        return summary, img_url
    except Exception as e:
        print(f"요약/이미지 추출 실패 ({url}): {e}")
        return '', ''

def is_relevant_article(text_content):
    if not keywords:
        return True
    text_lower = text_content.lower()
    matching_keywords = [keyword.lower() for keyword in keywords if keyword.lower() in text_lower]
    exclude_match = any(keyword.lower() in text_lower for keyword in exclude_keywords)
    if len(matching_keywords) < 2:
        return False
    if exclude_match:
        return False
    return True

def process_article(element, base_url, category):
    href_link = element.get('href')
    if not href_link or 'javascript' in href_link:
        return False
    
    if not href_link.startswith('http'):
        href_link = 'https://news.daum.net' + href_link
    
    title_element = element.find('span', class_='tit_txt')
    text_content = title_element.text.strip() if title_element else ''
    
    if not text_content:
        data_title = element.get('data-title')
        text_content = urllib.parse.unquote(data_title) if data_title else ''
    
    if not text_content:
        return False
    
    if href_link in processed_links:
        return False
    
    if not is_relevant_article(text_content):
        return False
    
    time_element = element.select_one('span.txt_info:last-of-type')
    summary, img_url = extract_article_details(href_link)
    
    formatted_time = ''
    if time_element:
        time_str = time_element.text.strip()
        try:
            published_time = datetime.strptime(time_str, '%Y.%m.%d. %H:%M:%S')
            formatted_time = published_time.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            try:
                current_date = datetime.now().strftime('%Y-%m-%d')
                full_time_str = f'{current_date} {time_str}'
                published_time = datetime.strptime(full_time_str, '%Y-%m-%d %H:%M')
                formatted_time = published_time.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                formatted_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    result_set.add((text_content, formatted_time, href_link, summary, img_url))
    processed_links.add(href_link)
    print(f"추출된 기사: {text_content} ({formatted_time})")
    return True

def get_news_from_page(url, page, category):
    try:
        full_url = f"{url}?page={page}" if 'breakingnews' in url else url
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        if category in ['politics', 'society', 'economy', 'climate']:
            selector = '.box_comp.box_news_headline2 .item_newsheadline2, .box_comp.box_news_block .item_newsblock'
        else:
            selector = '.list_newsheadline2 .item_newsheadline2, .list_newsbasic .item_newsbasic'
        
        relevant_elements = soup.select(selector)
        article_count = len(relevant_elements)

        print(f"URL: {full_url}, 기사 수: {article_count}")

        if article_count == 0:
            return False

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_article, element, url, category) for element in relevant_elements]
            results = [future.result() for future in as_completed(futures)]
        
        return any(results)
    except Exception as e:
        print(f"페이지 처리 실패 ({full_url}): {e}")
        return False

def scrape_category(url):
    category = url.split('/')[-1] if 'daum.net' in url else 'special'
    print(f"카테고리: {url}")
    
    if 'breakingnews' in url:
        page = 1
        while True:
            if not get_news_from_page(url, page, category):
                break
            page += 1
            time.sleep(2)
    else:
        get_news_from_page(url, 1, category)
        time.sleep(2)

# 기존 JSON 파일 읽기
def load_existing_json():
    if os.path.exists(json_filename):
        try:
            with open(json_filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON 파일 읽기 실패: {e}")
    return []

# JSON 저장
def save_to_json():
    print(f"최종 결과 수: {len(result_set)}")
    sorted_result = sorted(result_set, key=lambda x: x[1] if x[1] else '0000-00-00 00:00', reverse=True)

    from collections import defaultdict
    articles_by_date = defaultdict(list)
    for title, time, link, summary, img_url in sorted_result:
        date_str = datetime.strptime(time, '%Y-%m-%d %H:%M').strftime('%Y년 %m월 %d일 %A')
        articles_by_date[date_str].append({
            "title": title,
            "time": datetime.strptime(time, '%Y-%m-%d %H:%M').strftime('%Y-%m-%dT%H:%M:%S+09:00'),
            "img": img_url,
            "url": link,
            "original_url": link
        })

    existing_data = load_existing_json()
    existing_urls = set()
    existing_by_date = defaultdict(list)

    for date_group in existing_data:
        date = date_group['date']
        for article in date_group['articles']:
            existing_urls.add(article['url'])
            existing_by_date[date].append(article)

    for date, articles in articles_by_date.items():
        for article in articles:
            if article['url'] not in existing_urls:
                existing_by_date[date].append(article)
                existing_urls.add(article['url'])

    json_data = [{"date": date, "articles": articles} for date, articles in sorted(existing_by_date.items())]

    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f'Results saved to {json_filename}')

# 크롤링 실행
for url in urls:
    scrape_category(url)

# JSON 저장
save_to_json()
