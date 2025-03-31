const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = [
  'https://www.fntoday.co.kr/news/articleList.html?sc_sub_section_code=S2N107',
];

// 키워드 기반 필터링 (조건 완화)
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  const keywordCount = keywords.filter(k => words.has(k.toLowerCase())).length;
  console.log(`Keyword count for "${textContent}": ${keywordCount}`); // 디버깅 로그
  return keywordCount >= 1; // 2 -> 1로 완화
}

// 단일 기사 처리
function processArticle($, element, keywords, existingNews) {
  const titleElement = $(element).find('div.list-titles a');
  const hrefLink = titleElement.attr('href') || '';
  const fullLink = hrefLink.startsWith('http') ? hrefLink : `https://www.fntoday.co.kr${hrefLink}`;
  if (isDuplicate(fullLink, existingNews)) {
    console.log(`Duplicate found: ${fullLink}`);
    return null;
  }

  const title = titleElement.text().trim();
  const timeStr = $(element).find('div.list-dated').text().split('|').pop().trim();
  console.log(`Processing article: ${title}`); // 디버깅 로그

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
    console.log(`Found ${elements.length} elements in ${url}`); // 선택자 확인
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
