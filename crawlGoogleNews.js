const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = [
  'https://news.google.com/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFp4WkRNU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR%3Ako',
  // 나머지 URL들 추가
];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  return keywords.filter(k => words.has(k.toLowerCase())).length >= 2;
}

// 최근 2일 내 기사인지 확인
function isWithinLastTwoDays(timeStr) {
  if (!timeStr) return false;
  const articleDate = new Date(timeStr);
  const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
  return articleDate >= twoDaysAgo;
}

// 기사 크롤링
async function crawlGoogleNews() {
  const keywords = getKeywords();
  const existingNews = await loadExistingNews();
  const newArticles = [];

  for (const url of urls) {
    try {
      const response = await axios.get(url);
      const $ = cheerio.load(response.data);
      const elements = $('a.gPFEn, a.JtKRv');

      elements.each((i, elem) => {
        const title = $(elem).text().trim();
        const hrefLink = $(elem).attr('href');
        const fullLink = `https://news.google.com${hrefLink}`.replace('https://news.google.com./', 'https://news.google.com/');
        if (isDuplicate(fullLink, existingNews)) return;

        const timeElement = $(elem).next('time');
        const timeStr = timeElement.attr('datetime') || '';
        if (isRelevantArticle(title, keywords) && isWithinLastTwoDays(timeStr)) {
          newArticles.push({ title, time: timeStr, link: fullLink });
        }
      });
    } catch (error) {
      console.error(`Google 뉴스 크롤링 실패 (${url}):`, error);
    }
  }

  if (newArticles.length > 0) {
    await saveToNewsJson(newArticles, existingNews);
  } else {
    console.log('새로운 Google 뉴스 기사 없음');
  }
}

if (require.main === module) {
  crawlGoogleNews();
}

module.exports = { crawlGoogleNews };
