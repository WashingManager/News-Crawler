import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# 오늘과 어제 날짜 계산 (KST 기준)
today = datetime.now().strftime('%Y년 %m월 %d일')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y년 %m월 %d일')

# JSON 파일 처리
def process_json_files():
    input_dir = Path('news_json')
    output_file = input_dir / 'ForTwoDay_News.json'
    two_day_articles = []

    # news_json 폴더의 모든 JSON 파일 읽기
    for json_file in input_dir.glob('*.json'):
        if json_file.name == 'ForTwoDay_News.json':
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for group in data:
                    if group.get('date') in [today, yesterday]:
                        articles = group.get('articles', [])
                        for article in articles:
                            article['source'] = json_file.stem.replace('_News', '')  # 소스 추가
                            article['date'] = group['date']  # date 필드 추가
                        two_day_articles.append({
                            'date': group['date'],
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
        if unique_articles:
            unique_groups.append({
                'date': group['date'],
                'articles': unique_articles
            })

    # 날짜순 정렬
    unique_groups.sort(key=lambda x: datetime.strptime(x['date'], '%Y년 %m월 %d일'), reverse=True)

    # 결과 저장
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_groups, f, ensure_ascii=False, indent=2)
        print(f"Saved {output_file} with {sum(len(g['articles']) for g in unique_groups)} articles")
    except Exception as e:
        print(f"Error saving {output_file}: {e}")

if __name__ == '__main__':
    process_json_files()
