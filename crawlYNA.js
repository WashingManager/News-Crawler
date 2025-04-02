const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const baseUrls = [
  'https://www.yna.co.kr/nk/news/politics',
  // 나머지 URL들 추가
];

// 키워드 기반 필터링
function isRelevantArticle(textContent, keywords) {
  return keywords.filter(k => textContent.includes(k)).length >= 2;
}

// 최근 2일 내 기사인지 확인
function isWithinLastTwoDays(timeStr) {
  if (!timeStr) return false;
  const articleDate = new Date(timeStr);
  const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
  return articleDate >= twoDaysAgo;
}

// 기사 세부 정보 추출
async function extractArticleDetails(url) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const summary = $('div.tit-sub h2.tit').text().trim() || '';
    const timeStr = $('p.update-time').attr('data-published-time') || '';
    const formattedTime = timeStr ? new Date(timeStr).toISOString() : '';
    return { summary, time: formattedTime };
  } catch (error) {
    console.error(`요약 추출 실패 (${url}):`, error);
    return { summary: '', time: '' };
  }
}

// 단일 기사 처리
async function processArticle($, element, keywords, existingNews) {
  const title = $(element).find('a.tit-wrap strong.tit-news').text().trim();
  const lead = $(element).find('p.lead').text().trim();
  const hrefLink = $(element).find('a.tit-wrap').attr('href');
  const fullLink = hrefLink.startsWith('//') ? `https:${hrefLink}` : hrefLink;
  if (!title || !lead || isDuplicate(fullLink, existingNews)) return null;

  const fullText = `${title} ${lead}`;
  if (!isRelevantArticle(fullText, keywords)) return null;

  const { summary, time } = await extractArticleDetails(fullLink);
  if (!isWithinLastTwoDays(time)) return null;

  return { title, time, link: fullLink, summary };
}

// 페이지 크롤링
async function crawlPage(url, keywords, existingNews, page = 1) {
  try {
    const fullUrl = page > 1 ? `${url}/${page}` : url;
    const response = await axios.get(fullUrl);
    const $ = cheerio.load(response.data);
    const elements = $('ul.list li');
    const newArticles = [];

    for (const elem of elements.toArray()) {
      const article = await processArticle($, elem, keywords, existingNews);
      if (article) newArticles.push(article);
    }

    return newArticles.length > 0 ? newArticles : null;
  } catch (error) {
    console.error(`페이지 크롤링 실패 (${url}):`, error);
    return null;
  }
}

// 메인 실행 함수
async function crawlYNA() {
  const keywords = getKeywords();
  const existingNews = await loadExistingNews();
  let allNewArticles = [];

  for (const url of baseUrls) {
    let page = 1;
    while (true) {
      const newArticles = await crawlPage(url, keywords, existingNews, page);
      if (!newArticles) break;
      allNewArticles = allNewArticles.concat(newArticles);
      page++;
    }
  }

  if (allNewArticles.length > 0) {
    await saveToNewsJson(allNewArticles, existingNews);
  } else {
    console.log('새로운 연합뉴스 기사 없음');
  }
}

if (require.main === module) {
  crawlYNA();
}

module.exports = { crawlYNA };
