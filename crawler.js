const axios = require('axios');
const cheerio = require('che```javascript
const fs = require('fs');
const { getKeywords } = require('./keyword.js');

const URL = 'https://news.daum.net/global?nil_profile=mini&nil_src=news';

async function crawlNews() {
  try {
    // 기존 news.json 읽기 (없으면 빈 배열)
    let existingNews = [];
    if (fs.existsSync('news.json')) {
      existingNews = JSON.parse(fs.readFileSync('news.json', 'utf8'));
    }

    // 키워드 가져오기
    const keywords = getKeywords();

    // 페이지 요청
    const response = await axios.get(URL);
    const $ = cheerio.load(response.data);

    // 뉴스 데이터 추출
    const newsItems = [];
    $('.list_newsheadline2 .item_newsheadline2, .list_newsbasic .item_newsbasic').each((i, elem) => {
      const title = $(elem).find('.tit_txt').text().trim();
      const link = $(elem).attr('href');
      const time = $(elem).find('.txt_info').last().text().trim();

      // 키워드 포함 여부 확인
      if (keywords.some(keyword => title.includes(keyword))) {
        newsItems.push({ title, time, link });
      }
    });

    // 새로운 뉴스만 필터링
    const newNews = newsItems.filter(item => 
      !existingNews.some(existing => existing.link === item.link)
    );

    // 기존 데이터에 새로운 뉴스 추가 (최대 50개 제한)
    const updatedNews = [...newNews, ...existingNews].slice(0, 50);

    // news.json에 저장
    fs.writeFileSync('news.json', JSON.stringify(updatedNews, null, 2));
    console.log(`News updated successfully: ${newNews.length} new items added`);
  } catch (error) {
    console.error('Error crawling news:', error);
  }
}

crawlNews();
