const axios = require('axios');
const cheerio = require('cheerio');
const iconv = require('iconv-lite'); // 추가
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./lib/utils.js');

const urls = [
  'https://www.skyedaily.com/news/articlelist.html?mode=list',
  // 나머지 URL들 추가
];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  return keywords.filter(k => words.has(k.toLowerCase())).length >= 2;
}

// 기사 세부 정보 추출
async function extractArticleDetails(url) {
  try {
    const response = await axios.get(url, { responseType: 'arraybuffer' }); // 바이너리 데이터로 받음
    const decodedData = iconv.decode(Buffer.from(response.data), 'euc-kr'); // euc-kr 디코딩
    const $ = cheerio.load(decodedData);
    const summary = $('div.article_txt').text().trim() || '';
    return summary;
  } catch (error) {
    console.error(`요약 추출 실패 (${url}):`, error);
    return '';
  }
}

// 단일 기사 처리
async function processArticle($, element, keywords, existingNews) {
  const hrefLink = $(element).attr('href');
  const fullLink = hrefLink.startsWith('http') ? hrefLink : `https://www.skyedaily.com${hrefLink}`;
  if (isDuplicate(fullLink, existingNews)) return null;

  const title = $(element).find('font.sctionarticletitle').text().trim();
  const timeStr = $(element).find('font.picarticletxt').text().trim();
  if (!title || !timeStr || !isRelevantArticle(title, keywords)) return null;

  const summary = await extractArticleDetails(fullLink);
  if (!isRelevantArticle(`${title} ${summary}`, keywords)) return null;

  return { title, time: timeStr, link: fullLink, summary };
}

// 페이지 크롤링
async function crawlPage(url, keywords, existingNews) {
  try {
    const response = await axios.get(url, { responseType: 'arraybuffer' });
    const decodedData = iconv.decode(Buffer.from(response.data), 'euc-kr');
    const $ = cheerio.load(decodedData);
    const elements = $('div.picarticle a');
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
async function crawlSkyDaily() {
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
    console.log('새로운 SkyDaily 기사 없음');
  }
}

if (require.main === module) {
  crawlSkyDaily();
}

module.exports = { crawlSkyDaily };
