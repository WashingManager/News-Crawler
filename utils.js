const axios = require('axios');
const fs = require('fs').promises;

const NEWS_JSON_URL = 'https://raw.githubusercontent.com/WashingManager/News-Crawler/main/news.json';

// 기존 news.json 읽기
async function loadExistingNews() {
  try {
    const response = await axios.get(NEWS_JSON_URL, { cache: 'no-store' });
    return response.data || [];
  } catch (error) {
    console.error('기존 news.json 로드 실패:', error);
    return [];
  }
}

// news.json 업데이트 (로컬에서만 가능하므로 GitHub Actions에서 커밋 필요)
async function saveToNewsJson(newItems, existingNews) {
  const updatedNews = [...newItems, ...existingNews].slice(0, 50); // 최대 50개 유지
  // GitHub Actions에서는 이 부분을 커밋으로 대체해야 함
  await fs.writeFile('news.json', JSON.stringify(updatedNews, null, 2));
  console.log(`news.json 업데이트 완료: ${newItems.length}개 추가`);
}

// 링크 기반 중복 체크
function isDuplicate(link, existingNews) {
  return existingNews.some(item => item.link === link);
}

module.exports = { loadExistingNews, saveToNewsJson, isDuplicate };
