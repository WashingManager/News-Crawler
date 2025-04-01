const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const { getKeywords } = require('./keyword.js');

// 엔드포인트 목록
const GLOBAL_ENDPOINTS = [
  'https://news.daum.net/global', // 국제
  'https://news.daum.net/china', // 중국
  'https://news.daum.net/northamerica', // 북미
  'https://news.daum.net/japan', // 일본
  'https://news.daum.net/asia', // 아시아/오세아니아
  'https://news.daum.net/arab', // 중동/아랍
  'https://news.daum.net/europe', // 유럽
  'https://news.daum.net/southamerica', // 중남미
  'https://news.daum.net/africa', // 아프리카
  'https://news.daum.net/topic' // 해외화제
];

const GENERAL_ENDPOINTS = [
  'https://news.daum.net/politics', // 정치
  'https://news.daum.net/society', // 사회
  'https://news.daum.net/economy', // 경제
  'https://news.daum.net/climate' // 기후
];

const SPECIAL_ENDPOINT = 'https://issue.daum.net/focus/241203'; // 한시적 특집

// 지연 함수 (ms 단위로 대기)
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

// 크롤링 함수
async function crawlNews() {
  try {
    let existingNews = [];
    if (fs.existsSync('news.json')) {
      existingNews = JSON.parse(fs.readFileSync('news.json', 'utf8'));
    }

    const keywords = getKeywords();
    const newsItems = [];

    // 글로벌 엔드포인트 크롤링
    for (const url of GLOBAL_ENDPOINTS) {
      const category = url.split('/').pop();
      try {
        const response = await axios.get(url);
        const $ = cheerio.load(response.data);

        $('.list_newsheadline2 .item_newsheadline2, .list_newsbasic .item_newsbasic').each((i, elem) => {
          const title = $(elem).find('.tit_txt').text().trim();
          const link = $(elem).attr('href');
          const time = $(elem).find('.txt_info').last().text().trim();

          if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
            newsItems.push({ title, time, link, category });
          }
        });
        console.log(`Crawled ${category}: ${newsItems.filter(item => item.category === category).length} items`);
      } catch (error) {
        console.error(`Error crawling ${category}:`, error.message);
      }
      await delay(2000); // 2초 대기
    }

    // 종합 엔드포인트 크롤링
    for (const url of GENERAL_ENDPOINTS) {
      const category = url.split('/').pop();
      try {
        const response = await axios.get(url);
        const $ = cheerio.load(response.data);

        $('.box_comp.box_news_headline2 .item_newsheadline2, .box_comp.box_news_block .item_newsblock').each((i, elem) => {
          const title = $(elem).find('.tit_txt').text().trim();
          const link = $(elem).attr('href');
          const time = $(elem).find('.txt_info').last().text().trim();

          if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
            newsItems.push({ title, time, link, category });
          }
        });
        console.log(`Crawled ${category}: ${newsItems.filter(item => item.category === category).length} items`);
      } catch (error) {
        console.error(`Error crawling ${category}:`, error.message);
      }
      await delay(2000); // 2초 대기
    }

    // 특집 엔드포인트 크롤링
    try {
      const specialResponse = await axios.get(SPECIAL_ENDPOINT);
      const $special = cheerio.load(specialResponse.data);
      $special('.list_newsbasic .item_newsbasic').each((i, elem) => {
        const title = $special(elem).find('.tit_txt').text().trim();
        const link = $special(elem).attr('href');
        const time = $special(elem).find('.txt_info').last().text().trim();

        if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
          newsItems.push({ title, time, link, category: 'special' });
        }
      });
      console.log(`Crawled special: ${newsItems.filter(item => item.category === 'special').length} items`);
    } catch (error) {
      console.log('Special endpoint skipped:', error.message);
    }

    const newNews = newsItems.filter(item => !existingNews.some(existing => existing.link === item.link));
    const updatedNews = [...newNews, ...existingNews]; // 슬라이스 제거 또는 제한 늘리기
    fs.writeFileSync('news.json', JSON.stringify(updatedNews, null, 2));
    console.log(`News updated successfully: ${newNews.length} new items added, Total items: ${updatedNews.length}`);
  } catch (error) {
    console.error('Error crawling news:', error);
  }
}

crawlNews();
