import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# 오늘과 어제 날짜 계산 (KST 기준)
today = datetime.now().strftime('%Y년 %m월 %d일')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y년 %m월 %d일')
# 요일 포함 형식도 처리
today_with_day = datetime.now().strftime('%Y년 %m월 %d일 %A').replace('Monday', '월요일').replace('Tuesday', '화요일').replace('Wednesday', '수요일').replace('Thursday', '목요일').replace('Friday', '금요일').replace('Saturday', '토요일').replace('Sunday', '일요일')
yesterday_with_day = (datetime.now() - timedelta(days=1)).strftime('%Y년 %m월 %d일 %A').replace('Monday', '월요일').replace('Tuesday', '화요일').replace('Wednesday', '수요일').replace('Thursday', '목요일').replace('Friday', '금요일').replace('Saturday', '토요일').replace('Sunday', '일요일')

# 디버깅 로그
print(f"Today: {today}, Yesterday: {yesterday}")
print(f"Today with day: {today_with_day}, Yesterday with day: {yesterday_with_day}")

# JSON 파일 처리
def process_json_files():
    input_dir = Path('news_json')
    output_file = input_dir / 'ForTwoDay_News.json'
    two_day_articles = []

    # news_json 폴더의 모든 JSON 파일 읽기
    json_files = list(input_dir.glob('*.json'))
    print(f"Found {len(json_files)} JSON files in {input_dir}")

    for json_file in json_files:
        if json_file.name == 'ForTwoDay_News.json':
            continue
        print(f"Processing {json_file}")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    print(f"Invalid JSON structure in {json_file}: Expected a list")
                    continue
                for group in data:
                    group_date = group.get('date', '').strip()
                    # 요일 포함/미포함 모두 처리
                    normalized_group_date = group_date.split(' ')[0:3]
                    normalized_group_date = ' '.join(normalized_group_date) if normalized_group_date else ''
                    print(f"Checking group date: {group_date} (normalized: {normalized_group_date})")
                    if normalized_group_date in [today, yesterday, today_with_day, yesterday_with_day]:
                        articles = group.get('articles', [])
                        print(f"Found {len(articles)} articles for date {group_date}")
                        for article in articles:
                            article['source'] = json_file.stem.replace('_News', '')  # 소스 추가
                            article['date'] = group_date  # date 필드 추가
                        two_day_articles.append({
                            'date': group_date,
                            'articles': articles
                        })
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

    # 중복 제거 (URL 기준)
    seen_urls = set()
    unique_groups = []
    for group in two_day_articles:
        unique_articles = []
        for article in group['articles']:
            url = article.get('url', '')
            if url and url not in seen_urls:
                unique_articles.append(article)
                seen_urls.add(url)
            else:
                print(f"Duplicate URL found: {url}")
        if unique_articles:
            unique_groups.append({
                'date': group['date'],
                'articles': unique_articles
            })

    # 날짜순 정렬
    def parse_date(date_str):
        try:
            return datetime.strptime(' '.join(date_str.split(' ')[0:3]), '%Y년 %m월 %d일')
        except ValueError:
            return datetime.min  # 정렬을 위해 최소 날짜 반환
    unique_groups.sort(key=lambda x: parse_date(x['date']), reverse=True)

    # 결과 저장
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_groups, f, ensure_ascii=False, indent=2)
        print(f"Saved {output_file} with {sum(len(g['articles']) for g in unique_groups)} articles")
    except Exception as e:
        print(f"Error saving {output_file}: {e}")

if __name__ == '__main__':
    process_json_files()
