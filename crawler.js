const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const { getKeywords } = require('./keyword.js');

const GLOBAL_ENDPOINTS = [
  'https://news.daum.net/global',
  'https://news.daum.net/china',
  'https://news.daum.net/northamerica',
  'https://news.daum.net/japan',
  'https://news.daum.net/asia',
  'https://news.daum.net/arab',
  'https://news.daum.net/europe',
  'https://news.daum.net/southamerica',
  'https://news.daum.net/africa',
  'https://news.daum.net/topic'
];

const GENERAL_ENDPOINTS = [
  'https://news.daum.net/politics',
  'https://news.daum.net/society',
  'https://news.daum.net/economy',
  'https://news.daum.net/climate'
];

const SPECIAL_ENDPOINT = 'https://issue.daum.net/focus/241203';

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

// 기사 본문에서 이미지 URL을 가져오는 함수
async function fetchImageFromArticle(url) {
  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const imgSrc = $('.thumb_g_article').attr('src');
    if (imgSrc) {
      const match = imgSrc.match(/https:\/\/img[0-9]\.daumcdn\.net\/thumb\/[^?]+/);
      console.log(`Raw image src from ${url}: ${imgSrc}`);
      console.log(`Matched: ${match ? match[0] : 'none'}`);
      return match ? match[0] : imgSrc;
    }
    console.log(`No thumb_g_article found in ${url}`);
    return '';
  } catch (error) {
    console.error(`Error fetching image from article ${url}:`, error.message);
    return '';
  }
}

async function crawlNews() {
  try {
    let existingNews = [];
    if (fs.existsSync('news.json')) {
      existingNews = JSON.parse(fs.readFileSync('news.json', 'utf8'));
    }

    const keywords = getKeywords();
    console.log('Keywords:', keywords); // 키워드 확인
    const newsItems = [];

    for (const url of GLOBAL_ENDPOINTS) {
      const category = url.split('/').pop();
      try {
        const response = await axios.get(url);
        const $ = cheerio.load(response.data);

        $('.list_newsheadline2 .item_newsheadline2, .list_newsbasic .item_newsbasic').each((i, elem) => {
          const title = $(elem).find('.tit_txt').text().trim();
          const link = $(elem).attr('href');
          const time = $(elem).find('.txt_info').last().text().trim();
          const wrapThumb = $(elem).find('.wrap_thumb');
          let imgSrc = '';
          if (wrapThumb.length) {
            imgSrc = wrapThumb.find('source').attr('srcset') || wrapThumb.find('img').attr('src') || '';
            if (imgSrc) {
              const match = imgSrc.match(/https:\/\/img[0-9]\.daumcdn\.net\/thumb\/[^?]+/);
              imgSrc = match ? match[0] : imgSrc;
            }
            console.log(`Found imgSrc in list for "${title}": ${imgSrc}`);
          } else {
            console.log(`No .wrap_thumb found for "${title}" in ${category}`);
          }

          if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
            console.log(`Pushing item: ${title}, imgSrc: ${imgSrc}`);
            newsItems.push({ title, time, link, category, imgSrc });
          } else {
            console.log(`Skipped "${title}" - No keyword match or duplicate`);
          }
        });
        console.log(`Crawled ${category}: ${newsItems.filter(item => item.category === category).length} items`);
      } catch (error) {
        console.error(`Error crawling ${category}:`, error.message);
      }
      await delay(2000);
    }

    for (const url of GENERAL_ENDPOINTS) {
      const category = url.split('/').pop();
      try {
        const response = await axios.get(url);
        const $ = cheerio.load(response.data);

        $('.box_comp.box_news_headline2 .item_newsheadline2, .box_comp.box_news_block .item_newsblock').each((i, elem) => {
          const title = $(elem).find('.tit_txt').text().trim();
          const link = $(elem).attr('href');
          const time = $(elem).find('.txt_info').last().text().trim();
          const wrapThumb = $(elem).find('.wrap_thumb');
          let imgSrc = '';
          if (wrapThumb.length) {
            imgSrc = wrapThumb.find('source').attr('srcset') || wrapThumb.find('img').attr('src') || '';
            if (imgSrc) {
              const match = imgSrc.match(/https:\/\/img[0-9]\.daumcdn\.net\/thumb\/[^?]+/);
              imgSrc = match ? match[0] : imgSrc;
            }
            console.log(`Found imgSrc in list for "${title}": ${imgSrc}`);
          } else {
            console.log(`No .wrap_thumb found for "${title}" in ${category}`);
          }

          if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
            console.log(`Pushing item: ${title}, imgSrc: ${imgSrc}`);
            newsItems.push({ title, time, link, category, imgSrc });
          } else {
            console.log(`Skipped "${title}" - No keyword match or duplicate`);
          }
        });
        console.log(`Crawled ${category}: ${newsItems.filter(item => item.category === category).length} items`);
      } catch (error) {
        console.error(`Error crawling ${category}:`, error.message);
      }
      await delay(2000);
    }

    try {
      const specialResponse = await axios.get(SPECIAL_ENDPOINT);
      const $special = cheerio.load(specialResponse.data);
      $special('.list_newsbasic .item_newsbasic').each((i, elem) => {
        const title = $special(elem).find('.tit_txt').text().trim();
        const link = $special(elem).attr('href');
        const time = $special(elem).find('.txt_info').last().text().trim();
        const wrapThumb = $special(elem).find('.wrap_thumb');
        let imgSrc = '';
        if (wrapThumb.length) {
          imgSrc = wrapThumb.find('source').attr('srcset') || wrapThumb.find('img').attr('src') || '';
          if (imgSrc) {
            const match = imgSrc.match(/https:\/\/img[0-9]\.daumcdn\.net\/thumb\/[^?]+/);
            imgSrc = match ? match[0] : imgSrc;
          }
          console.log(`Found imgSrc in list for "${title}": ${imgSrc}`);
        } else {
          console.log(`No .wrap_thumb found for "${title}" in special`);
        }

        if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
          console.log(`Pushing item: ${title}, imgSrc: ${imgSrc}`);
          newsItems.push({ title, time, link, category: 'special', imgSrc });
        } else {
          console.log(`Skipped "${title}" - No keyword match or duplicate`);
        }
      });
      console.log(`Crawled special: ${newsItems.filter(item => item.category === 'special').length} items`);
    } catch (error) {
      console.log('Special endpoint skipped:', error.message);
    }

    // 이미지 없는 기사에 대해 본문에서 이미지 크롤링
    for (let i = 0; i < newsItems.length; i++) {
      if (!newsItems[i].imgSrc) {
        newsItems[i].imgSrc = await fetchImageFromArticle(newsItems[i].link);
        console.log(`Fetched image for "${newsItems[i].title}": ${newsItems[i].imgSrc}`);
        await delay(1000);
      }
    }

    const newNews = newsItems.filter(item => !existingNews.some(existing => existing.link === item.link));
    const updatedNews = [...newNews, ...existingNews];
    fs.writeFileSync('news.json', JSON.stringify(updatedNews, null, 2));
    console.log(`News updated successfully: ${newNews.length} new items added, Total items: ${updatedNews.length}`);
  } catch (error) {
    console.error('Error crawling news:', error);
  }
}

crawlNews();
