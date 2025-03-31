const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const url = 'https://www.bbc.com/korean';

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  const keywordCount = keywords.filter(k => words.has(k.toLowerCase())).length;
  return keywordCount >= 2;
}

// 최근 2일 내 기사인지 확인
function isWithinLastTwoDays(timeStr) {
  if (!timeStr) return false;
  const articleDate = new Date(timeStr);
  const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
  return articleDate >= twoDaysAgo;
}

// 기사 크롤링
async function crawlBBC() {
  const keywords = getKeywords();
  const existingNews = await loadExistingNews();

  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const elements = $('a.focusIndicatorDisplayBlock.bbc-uk8dsi.e1d658bg0');
    const newArticles = [];

    elements.each((i, elem) => {
      const title = $(elem).text().trim();
      const hrefLink = $(elem).attr('href');
      const fullLink = hrefLink.startsWith('/') ? `https://www.bbc.com${hrefLink}` : hrefLink;
      if (isDuplicate(fullLink, existingNews)) return;

      const timeElement = $(elem).next('time');
      const timeStr = timeElement.attr('datetime') || '';

      if (isRelevantArticle(title, keywords) && isWithinLastTwoDays(timeStr)) {
        newArticles.push({ title, time: timeStr, link: fullLink });
      }
    });

    if (newArticles.length > 0) {
      await saveToNewsJson(newArticles, existingNews);
    } else {
      console.log('새로운 BBC 기사 없음');
    }
  } catch (error) {
    console.error('BBC 크롤링 실패:', error);
  }
}

if (require.main === module) {
  crawlBBC();
}

module.exports = { crawlBBC };
