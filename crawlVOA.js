const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = [
  'https://www.voakorea.com/z/2767', // 정치안보
  'https://www.voakorea.com/z/2768', // 경제지원
  'https://www.voakorea.com/z/2769', // 사회인권
  'https://www.voakorea.com/z/2824', // 중동
  'https://www.voakorea.com/z/6936', // 우크라이나
  'https://www.voakorea.com/z/2698', // 세계
];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  return keywords.filter(k => words.has(k.toLowerCase())).length >= 2;
}

// 기사 세부 정보 추출
async function extractArticleDetails(url) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const summary = $('p.perex').text().trim() || '';
    return summary;
  } catch (error) {
    console.error(`요약 추출 실패 (${url}):`, error);
    return '';
  }
}

// 단일 기사 처리
async function processArticle($, element, keywords, existingNews) {
  const hrefLink = $(element).find('a').attr('href') || '';
  const fullLink = hrefLink.startsWith('http') ? hrefLink : `https://www.vo10.com${hrefLink}`;
  if (isDuplicate(fullLink, existingNews)) return null;

  const title = $(element).find('h4.media-block__title').text().trim();
  if (!title || !isRelevantArticle(title, keywords)) return null;

  const time = $(element).find('span.date').text().trim() || '';
  const summary = await extractArticleDetails(fullLink);
  if (!isRelevantArticle(`${title} ${summary}`, keywords)) return null;

  return { title, time, link: fullLink, summary };
}

// 페이지 크롤링
async function crawlPage(url, keywords, existingNews) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const elements = $('li.col-xs-12');
    const newArticles = [];

    for (const elem of elements.toArray()) {
      const article = await processArticle($, elem, keywords, existingNews);
      if (article) newArticles.push(article);
    }

    return newArticles;
  } catch (error) {
    console.error(`페이지 크롤링 실패 (${url}):`, error);
    return [];
  }
}

// 메인 실행 함수
async function crawlVOA() {
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
    console.log('새로운 VOA 기사 없음');
  }
}

if (require.main === module) {
  crawlVOA();
}

module.exports = { crawlVOA };
