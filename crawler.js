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

async function crawlNews() {
  try {
    let existingNews = [];
    if (fs.existsSync('news.json')) {
      existingNews = JSON.parse(fs.readFileSync('news.json', 'utf8'));
    }

    const keywords = getKeywords();
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
              const match = imgSrc.match(/https:\/\/img1\.daumcdn\.net\/thumb\/[^?]+/);
              imgSrc = match ? match[0] : imgSrc;
            }
          }

          if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
            newsItems.push({ title, time, link, category, imgSrc });
            if (!imgSrc) console.log(`No image found for "${title}" in ${category}`);
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
              const match = imgSrc.match(/https:\/\/img1\.daumcdn\.net\/thumb\/[^?]+/);
              imgSrc = match ? match[0] : imgSrc;
            }
          }

          if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
            newsItems.push({ title, time, link, category, imgSrc });
            if (!imgSrc) console.log(`No image found for "${title}" in ${category}`);
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
            const match = imgSrc.match(/https:\/\/img1\.daumcdn\.net\/thumb\/[^?]+/);
            imgSrc = match ? match[0] : imgSrc;
          }
        }

        if (keywords.some(keyword => title.includes(keyword)) && !newsItems.some(item => item.link === link)) {
          newsItems.push({ title, time, link, category: 'special', imgSrc });
          if (!imgSrc) console.log(`No image found for "${title}" in special`);
        }
      });
      console.log(`Crawled special: ${newsItems.filter(item => item.category === 'special').length} items`);
    } catch (error) {
      console.log('Special endpoint skipped:', error.message);
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
