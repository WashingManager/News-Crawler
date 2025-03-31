const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = ['https://www.fnnews.com/newsflash'];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  return keywords.filter(k => words.has(k.toLowerCase())).length >= 2;
}

// 단일 기사 처리
function processArticle($, element, keywords, existingNews) {
  const titleElement = $(element).find('strong.tit_thumb a');
  const hrefLink = titleElement.attr('href') || '';
  const fullLink = hrefLink.startsWith('http') ? hrefLink : `https://www.fnnews.com${hrefLink}`;
  if (isDuplicate(fullLink, existingNews)) return null;

  const title = titleElement.text().trim();
  const timeStr = $(element).find('span.caption').text().trim() || '';
  if (!isRelevantArticle(title, keywords)) return null;

  return { title, time: timeStr, link: fullLink, summary: '' }; // 요약은 빈 문자열로 유지
}

// 페이지 크롤링
async function crawlPage(url, keywords, existingNews) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const elements = $('div.wrap_txt');
    const newArticles = [];

    elements.each((i, elem) => {
      const article = processArticle($, elem, keywords, existingNews);
      if (article) newArticles.push(article);
    });

    return newArticles;
  } catch (error) {
    console.error(`페이지 크롤링 실패 (${url}):`, error);
    return [];
  }
}

// 메인 실행 함수
async function crawlFnNews() {
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
    console.log('새로운 FnNews 기사 없음');
  }
}

if (require.main === module) {
  crawlFnNews();
}

module.exports = { crawlFnNews };
