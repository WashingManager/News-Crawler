const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = [
  'https://news.daum.net/breakingnews/politics/north',
  // 나머지 URL들 추가
];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  const keywordCount = keywords.filter(k => words.has(k.toLowerCase())).length;
  return keywordCount >= 2;
}

// 단일 페이지 크롤링
async function crawlPage(url, keywords, existingNews) {
  try {
    const response = await axios.get(`${url}?page=1`);
    const $ = cheerio.load(response.data);
    const elements = $('div.box_etc a.link_txt');
    const newArticles = [];

    elements.each((i, elem) => {
      const hrefLink = $(elem).attr('href');
      const fullLink = hrefLink.startsWith('http') ? hrefLink : `https://news.daum.net${hrefLink}`;
      if (isDuplicate(fullLink, existingNews)) return;

      const title = $(elem).text().trim();
      const timeStr = $(elem).next('span.info_time').text().trim() || new Date().toISOString();

      if (isRelevantArticle(title, keywords)) {
        newArticles.push({ title, time: timeStr, link: fullLink });
      }
    });

    return newArticles;
  } catch (error) {
    console.error(`페이지 크롤링 실패 (${url}):`, error);
    return [];
  }
}

// 메인 실행 함수
async function crawlDaum() {
  const keywords = getKeywords();
  const existingNews = await loadExistingNews();
  let allNewArticles = [];

  for (const url of urls) {
    const newArticles = await crawlPage(url, keywords, existingNews);
    allNewArticles = allNewArticles.concat(newArticles);
  }

  if (allNewArticles.length > 0) {
    await saveToNewsJson(allNewArticles, existingNews);
  } else {
    console.log('새로운 Daum 기사 없음');
  }
}

if (require.main === module) {
  crawlDaum();
}

module.exports = { crawlDaum };
