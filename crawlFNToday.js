const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = [
  'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N107',
  // 나머지 URL들 추가
];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  const keywordCount = keywords.filter(k => words.has(k.toLowerCase())).length;
  return keywordCount >= 2; // 제외 키워드는 생략 가능
}

// 기사 세부 정보 추출
async function extractArticleDetails(url) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const summary = $('p.list-summary a').text().trim() || '';
    return summary;
  } catch (error) {
    console.error(`요약 추출 실패 (${url}):`, error);
    return '';
  }
}

// 단일 기사 처리
function processArticle($, element, keywords, existingNews) {
  const titleElement = $(element).find('div.list-titles a');
  const hrefLink = titleElement.attr('href') || '';
  const fullLink = hrefLink.startsWith('http') ? hrefLink : `https://www.fntoday.co.kr${hrefLink}`;
  if (isDuplicate(fullLink, existingNews)) return null;

  const title = titleElement.text().trim();
  const timeStr = $(element).find('div.list-dated').text().split('|').pop().trim();

  if (isRelevantArticle(title, keywords)) {
    return { title, time: timeStr, link: fullLink };
  }
  return null;
}

// 페이지 크롤링
async function crawlPage(url, keywords, existingNews) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const elements = $('div.list-block');
    const newArticles = [];

    elements.each((i, elem) => {
      const article = processArticle($, elem, keywords, existingNews);
      if (article) newArticles.push(article);
    });

    console.log(`URL ${url}에서 ${newArticles.length}개 기사 수집`);
    return newArticles;
  } catch (error) {
    console.error(`페이지 크롤링 실패 (${url}):`, error);
    return [];
  }
}

// 메인 실행 함수
async function crawlFNToday() {
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
    console.log('새로운 기사 없음');
  }
}

if (require.main === module) {
  crawlFNToday();
}

module.exports = { crawlFNToday };
