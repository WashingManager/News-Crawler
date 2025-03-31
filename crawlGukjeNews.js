const axios = require('axios');
const cheerio = require('cheerio');
const { getKeywords } = require('./keyword.js');
const { loadExistingNews, saveToNewsJson, isDuplicate } = require('./utils.js');

const urls = [
  'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N1&view_type=sm', // 정치
  'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N3&view_type=sm', // 사회
  'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N6&view_type=sm'  // 국제
];

// 키워드 기반 필터링 (완화된 조건)
function isRelevantArticle(textContent, keywords) {
  const words = new Set(textContent.toLowerCase().match(/\b\w+\b/g) || []);
  const keywordCount = keywords.filter(k => words.has(k.toLowerCase())).length;
  console.log(`Keyword count for "${textContent}": ${keywordCount}`); // 디버깅 로그
  return keywordCount >= 1; // 2 -> 1로 완화
}

// 기사 세부 정보 추출
async function extractArticleDetails(url) {
  try {
    const response = await axios.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
      }
    });
    const $ = cheerio.load(response.data);
    const summary = $('div.article-head-summary').text().trim() || '';
    return summary;
  } catch (error) {
    console.error(`요약 추출 실패 (${url}):`, error);
    return '';
  }
}

// 단일 기사 처리
async function processArticle($, element, keywords, existingNews) {
  const titleElement = $(element).find('h4.titles a');
  const hrefLink = `https://www.gukjenews.com${titleElement.attr('href')}`;
  if (isDuplicate(hrefLink, existingNews)) {
    console.log(`Duplicate found: ${hrefLink}`); // 디버깅 로그
    return null;
  }

  const title = titleElement.text().trim();
  const timeStr = $(element).find('span.byline em:nth-of-type(3)').text().trim() || '';
  console.log(`Processing article: ${title}`); // 디버깅 로그
  if (!isRelevantArticle(title, keywords)) return null;

  const summary = await extractArticleDetails(hrefLink);
  if (!isRelevantArticle(`${title} ${summary}`, keywords)) return null;

  return { title, time: timeStr, link: hrefLink, summary };
}

// 페이지 크롤링
async function crawlPage(url, keywords, existingNews, page = 1) {
  try {
    const fullUrl = `${url}&page=${page}`;
    const response = await axios.get(fullUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
      }
    });
    const $ = cheerio.load(response.data);
    const elements = $('ul.type2 li');
    console.log(`Found ${elements.length} elements in ${fullUrl}`); // 디버깅 로그
    const newArticles = [];

    for (const elem of elements.toArray()) {
      const article = await processArticle($, elem, keywords, existingNews);
      if (article) newArticles.push(article);
      else console.log(`Article filtered out on page ${page}`); // 디버깅 로그
    }

    console.log(`URL ${fullUrl}에서 ${newArticles.length}개 기사 수집`);
    return newArticles.length > 0 ? newArticles : null;
  } catch (error) {
    console.error(`페이지 크롤링 실패 (${url}):`, error);
    return null;
  }
}

// 메인 실행 함수
async function crawlGukjeNews() {
  const keywords = getKeywords();
  const existingNews = await loadExistingNews();
  let allNewArticles = [];

  for (const url of urls) {
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
    console.log('새로운 국제뉴스 기사 없음');
  }
}

if (require.main === module) {
  crawlGukjeNews();
}

module.exports = { crawlGukjeNews };
